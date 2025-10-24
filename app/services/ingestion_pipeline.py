# app/services/ingestion_pipeline.py


import logging
import time
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any
import asyncio
import os
import shutil
from sqlalchemy.sql import func
# (导入 OpenAI 库)
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError

from sqlalchemy.orm import Session
from qdrant_client import QdrantClient, models
from llama_index.core import SimpleDirectoryReader

from llama_index.core.node_parser import SentenceSplitter, CodeSplitter, MarkdownNodeParser

from app.crud import crud_knowledgebase

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
CHUNK_SIZE = 1024 # (见建议 3)
CHUNK_OVERLAP = 100 # (见建议 3)
CODE_CHUNK_LINES = 100        # (!!) 从 40 调大到 100 (或 80-150 之间尝试)
CODE_CHUNK_OVERLAP = 20       # (!!) 对应调大
CODE_MAX_CHARS = 4000         # (!!) 对应调大 (从 1500)
BATCH_SIZE = 10# DashScope 向量 API 限制 input 数组大小 <= 25

# --- Helper Function: Update Status ---
def _update_parsing_status(db: Session, kb_id: int, stage: str, progress: Optional[int] = None, message: str = "") -> bool:
    """ Updates the parsing status in the database. Returns False if processing should stop. """
    try:
        db_kb = crud_knowledgebase.get_kb(db, kb_id)
        if db_kb:
            if db_kb.status != 'processing':
                logger.warning(f"[KB {kb_id}] Status changed externally to {db_kb.status}, stopping status update.")
                return False
            new_state = {"stage": stage, "message": message}
            if progress is not None: new_state["progress"] = progress
            db_kb.parsing_state = new_state
            # db_kb.updated_at = func.now()
            db.commit()
            logger.info(f"[KB {kb_id}] Status updated: {stage} - {message} (Progress: {progress}%)")
            return True
        else:
            logger.warning(f"[KB {kb_id}] KnowledgeBase not found during status update.")
            return False
    except Exception as e:
        logger.error(f"[KB {kb_id}] Failed to update parsing status: {e}")
        try: db.rollback()
        except Exception as rb_err: logger.error(f"[KB {kb_id}] Rollback failed: {rb_err}")
        return False

# --- Helper Function: Extract Zip ---
def _extract_zip(zip_path: Path, extract_to: Path):
    """ Extracts a ZIP file. """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        logger.info(f"Successfully extracted '{zip_path}' to '{extract_to}'")
    except zipfile.BadZipFile:
        logger.error(f"Error: '{zip_path}' is not a valid zip file or is corrupted.")
        raise ValueError("Invalid or corrupted zip file.")
    except Exception as e:
        logger.error(f"Error extracting zip file '{zip_path}': {e}")
        raise

# --- Helper Function: Get Embeddings via DashScope OpenAI Compatible API ---
async def get_embeddings_from_api(
    texts: List[str],
    base_url: str, # <-- 使用 base_url
    model_name: str,
    api_key: str, # <-- API Key 设为必需
    dimensions: Optional[int] = None # <-- 接收维度参数
) -> List[List[float]]:
    """ Asynchronously calls DashScope OpenAI Compatible Embedding API. """

    if not api_key: raise ValueError("DashScope API key is required.")
    if not base_url: raise ValueError("DashScope base_url is required.")

    # 初始化 OpenAI 异步客户端，指定 base_url
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # 准备传递给 create 方法的参数
    create_params = {
        "input": texts,
        "model": model_name,
        "encoding_format": "float" # 指定编码格式
    }
    # 仅当 dimensions 有效时才添加该参数
    if dimensions and dimensions > 0:
        create_params["dimensions"] = dimensions

    logger.debug(f"Calling DashScope embedding API with model: {model_name}, dimensions: {dimensions}, num_texts: {len(texts)}")

    try:
        response = await client.embeddings.create(**create_params)
        if response.data and isinstance(response.data, list):
            embeddings = [item.embedding for item in response.data]
            if len(embeddings) != len(texts):
                raise ValueError(f"DashScope API returned {len(embeddings)} embeddings for {len(texts)} texts.")
            if embeddings and len(set(len(e) for e in embeddings)) > 1:
                 dims = set(len(e) for e in embeddings)
                 logger.warning(f"Embeddings received from DashScope have inconsistent dimensions: {dims}")
            logger.debug(f"Received {len(embeddings)} embeddings.")
            return embeddings
        else:
             logger.error(f"Unexpected response structure from DashScope API: {response}")
             raise ValueError(f"Unexpected response structure from DashScope API.")
    except APIError as e:
        logger.error(f"DashScope API Error: {e.status_code} - {e.message} (Code: {e.code}, Type: {e.type})")
        detail = e.message;
        if e.body and 'message' in e.body: detail = e.body['message']
        raise ValueError(f"DashScope API Error: {detail}")
    except APIConnectionError as e:
        logger.error(f"Failed to connect to DashScope API at {base_url}: {e}")
        raise ValueError("Could not connect to DashScope API.")
    except RateLimitError as e:
        logger.error(f"DashScope API rate limit exceeded: {e}")
        raise ValueError("DashScope API rate limit exceeded. Please wait.")
    except Exception as e:
        logger.error(f"Error getting embeddings from DashScope API (model: {model_name}): {e}", exc_info=True)
        raise ValueError(f"Failed to get embeddings from DashScope: {e}")

# --- Main Pipeline Function (Accepts detailed model info) ---
def run_ingestion_pipeline(
    kb_id: int,
    embedding_model_details: Dict[str, Any], # 接收包含 name, url, key, dimensions 的字典
    file_path_str: str,
    qdrant_host: str,
    qdrant_port: int
):
    """ The main ingestion pipeline using the DashScope client. """
    db = SessionLocal()
    qdrant = None
    file_path = Path(file_path_str)
    collection_name = f"kb_{kb_id}"
    temp_extract_dir = None

    # 提取所有需要的模型信息
    model_base_url = embedding_model_details.get("endpoint_url") # 即 base_url
    model_api_key = embedding_model_details.get("api_key")
    model_name = embedding_model_details.get("name")
    model_dimensions = embedding_model_details.get("dimensions") # 获取维度

    # 验证模型信息
    if not model_base_url:
        logger.error(f"[KB {kb_id}] Model base_url (endpoint_url) is missing.")
        _update_parsing_status(db, kb_id, "error", None, "Model config error: Base URL missing.")
        db.close(); return
    if not model_api_key:
        logger.error(f"[KB {kb_id}] Model API Key is missing.")
        _update_parsing_status(db, kb_id, "error", None, "Model config error: API Key missing.")
        db.close(); return
    if not model_name:
         logger.error(f"[KB {kb_id}] Model name is missing.")
         _update_parsing_status(db, kb_id, "error", None, "Model config error: Model name missing.")
         db.close(); return
    # 对 dimensions 进行可选性检查
    if model_name in ["text-embedding-v3", "text-embedding-v4"] and not model_dimensions:
        logger.warning(f"[KB {kb_id}] Model {model_name} might require dimensions, but none provided.")

    logger.info(f"[KB {kb_id}] Starting ingestion for '{file_path}' using model '{model_name}' at '{model_base_url}' (dim: {model_dimensions}) into collection '{collection_name}'")

    try:
        qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)

        # --- Stage 1: File Loading & Extraction ---
        if not _update_parsing_status(db, kb_id, "loading", 5, f"Processing file: {file_path.name}"): return
        input_dir = file_path.parent
        if file_path.suffix.lower() == '.zip':
            temp_extract_dir = Path(f"./temp_extract_{kb_id}_{int(time.time())}")
            temp_extract_dir.mkdir(parents=True, exist_ok=True)
            if not _update_parsing_status(db, kb_id, "loading", 10, "Extracting zip file..."): return
            _extract_zip(file_path, temp_extract_dir); input_dir = temp_extract_dir
            logger.info(f"[KB {kb_id}] Reading from extracted directory: {input_dir}")
        else:
             logger.info(f"[KB {kb_id}] Reading from directory: {input_dir}")
             if not input_dir.is_dir(): raise ValueError(f"Input path is not a directory: {input_dir}")

        # --- Stage 2: Document Loading (LlamaIndex) ---
        if not _update_parsing_status(db, kb_id, "loading", 20, "Loading documents..."): return
        reader = SimpleDirectoryReader(input_dir=str(input_dir), recursive=True, exclude_hidden=True)
        documents = reader.load_data()
        if not documents: raise ValueError(f"No documents found or loaded from '{input_dir}'.")
        logger.info(f"[KB {kb_id}] Loaded {len(documents)} document(s).")

        # --- Stage 3: Document Splitting (Dynamic Splitter) ---
        if not _update_parsing_status(db, kb_id, "chunking", 30, f"Splitting {len(documents)} document(s)..."): return
        all_nodes = []
        logger.info(f"[KB {kb_id}] Starting dynamic splitting...")
        markdown_splitter = MarkdownNodeParser()
        for doc_index, doc in enumerate(documents):
            file_path_meta = doc.metadata.get('file_path', '')
            _, file_ext = os.path.splitext(file_path_meta); file_ext = file_ext.lower()
            logger.debug(f"[KB {kb_id}] Processing doc {doc_index+1}/{len(documents)}: '{file_path_meta}' (ext: {file_ext})")
            splitter_to_use = None; language_for_code_splitter = None
            # --- Define language support here ---
            if file_ext in ['.md', '.markdown', '.mdx']: splitter_to_use = markdown_splitter
            elif file_ext == '.py': language_for_code_splitter = "python"
            elif file_ext in ['.js', '.jsx', '.ts', '.tsx']: language_for_code_splitter = "javascript"
            elif file_ext == '.go': language_for_code_splitter = "go"
            elif file_ext == '.java': language_for_code_splitter = "java"
            elif file_ext == '.rs': language_for_code_splitter = "rust"
            elif file_ext in ['.c', '.h']: language_for_code_splitter = "c"
            elif file_ext in ['.cpp', '.hpp', '.cxx', '.hxx']: language_for_code_splitter = "cpp"
            else: # Explicit default for non-code/unknown
                logger.debug(f"[KB {kb_id}] Using SentenceSplitter for {file_path_meta}")
                splitter_to_use = SentenceSplitter( chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
            # --- Language support end ---
            if language_for_code_splitter:
                logger.debug(f"[KB {kb_id}] Using CodeSplitter for {file_path_meta} (lang: {language_for_code_splitter})")
                try:
                    splitter_to_use = CodeSplitter( language=language_for_code_splitter, chunk_lines=CODE_CHUNK_LINES, chunk_lines_overlap=CODE_CHUNK_OVERLAP, max_chars=CODE_MAX_CHARS)
                except Exception as cs_err:
                     logger.warning(f"[KB {kb_id}] Failed CodeSplitter init ({language_for_code_splitter}), fallback: {cs_err}")
                     splitter_to_use = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP) # Fallback

            if splitter_to_use:
                 try:
                     doc_nodes = splitter_to_use.get_nodes_from_documents([doc])
                     all_nodes.extend(doc_nodes)
                     logger.debug(f"[KB {kb_id}] Split '{os.path.basename(file_path_meta)}' into {len(doc_nodes)} nodes.")
                 except ValueError as split_err: logger.warning(f"[KB {kb_id}] Skip split '{file_path_meta}': {split_err}.")
                 except Exception as split_err: logger.error(f"[KB {kb_id}] Error split '{file_path_meta}': {split_err}", exc_info=False)
            else: logger.warning(f"[KB {kb_id}] No splitter for file: {file_path_meta}, skipping.")
        if not all_nodes: raise ValueError("Splitting resulted in zero nodes across all files.")
        logger.info(f"[KB {kb_id}] Finished splitting. Total nodes created: {len(all_nodes)}")

        # --- Stage 4: Embedding Generation (via DashScope API) ---
        if not _update_parsing_status(db, kb_id, "embedding", 40, f"Preparing API call to {model_base_url} with model {model_name}..."): return
        points_to_upload = []
        texts_to_embed = [node.get_content() for node in all_nodes]
        all_embeddings = []
        current_batch_size = min(BATCH_SIZE, 10) # Use DashScope limit
        num_batches = (len(texts_to_embed) + current_batch_size - 1) // current_batch_size
        logger.info(f"[KB {kb_id}] Starting embedding generation in {num_batches} batches (size {current_batch_size}).")
        for i in range(num_batches):
            batch_start = i * current_batch_size
            batch_end = min((i + 1) * current_batch_size, len(texts_to_embed))
            text_batch = texts_to_embed[batch_start:batch_end]
            if not text_batch: continue
            progress = 50 + int(30 * (i + 1) / num_batches)
            if not _update_parsing_status(db, kb_id, "embedding", progress, f"Generating embeddings (batch {i+1}/{num_batches})..."): return
            try:
                 embeddings_batch = asyncio.run(get_embeddings_from_api(
                     texts=text_batch,
                     base_url=model_base_url, # Pass base_url
                     model_name=model_name,
                     api_key=model_api_key,
                     dimensions=model_dimensions # Pass dimensions
                 ))
                 if len(embeddings_batch) != len(text_batch): raise ValueError(f"API embed count mismatch batch {i+1}.")
                 all_embeddings.extend(embeddings_batch)
                 logger.debug(f"[KB {kb_id}] Batch {i+1} embeddings received.")
            except ValueError as api_err: logger.error(f"[KB {kb_id}] API call failed batch {i+1}: {api_err}"); raise

        if len(all_embeddings) != len(all_nodes): raise ValueError(f"Embed count ({len(all_embeddings)}) != chunk count ({len(all_nodes)}).")

        # Prepare Qdrant points (Unchanged)
        for i, node in enumerate(all_nodes):
            points_to_upload.append( models.PointStruct( id=str(node.node_id), vector=all_embeddings[i], payload={"text": node.get_content(), "metadata": node.metadata or {}}))
        logger.info(f"[KB {kb_id}] Prepared {len(points_to_upload)} points for Qdrant.")

        # --- Stage 5: Upload to Qdrant (Unchanged) ---
        if not _update_parsing_status(db, kb_id, "uploading", 80, f"Uploading {len(points_to_upload)} points to Qdrant..."): return
        qdrant.upsert(collection_name=collection_name, points=points_to_upload, wait=True)
        logger.info(f"[KB {kb_id}] Successfully uploaded points to Qdrant collection '{collection_name}'.")

        # --- Stage 6: Finalize (Unchanged) ---
        if not _update_parsing_status(db, kb_id, "complete", 100, "Ingestion pipeline finished successfully."): return
        db_kb_final = crud_knowledgebase.get_kb(db, kb_id)
        
        if db_kb_final and db_kb_final.status == 'processing':
            db_kb_final.status = 'ready'; db.commit()
            logger.info(f"[KB {kb_id}] KnowledgeBase status set to 'ready'.")

    except Exception as e:
        # --- Error Handling (Unchanged) ---
        error_message = f"Pipeline failed: {str(e)}"
        logger.error(f"[KB {kb_id}] Ingestion pipeline failed: {e}", exc_info=True)
        _update_parsing_status(db, kb_id, "error", None, error_message)
        try:
            db_kb_error = crud_knowledgebase.get_kb(db, kb_id)
            if db_kb_error and db_kb_error.status != 'error': db_kb_error.status = 'error'; db.commit()
        except Exception as db_err: logger.error(f"[KB {kb_id}] Failed set status to 'error': {db_err}")

    finally:
        # --- Cleanup (Unchanged) ---
        if temp_extract_dir:
            try: shutil.rmtree(temp_extract_dir); logger.info(f"[KB {kb_id}] Cleaned up temp directory: {temp_extract_dir}")
            except Exception as e: logger.error(f"[KB {kb_id}] Failed cleanup temp dir '{temp_extract_dir}': {e}")
        if db: db.close(); logger.debug(f"[KB {kb_id}] DB session closed.")