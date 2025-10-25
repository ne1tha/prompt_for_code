# app/services/ingestion_pipeline.py


import logging
import time
import zipfile
import rarfile  # <-- 1. 新增导入
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
CHUNK_SIZE = 1024 
CHUNK_OVERLAP = 100 
CODE_CHUNK_LINES = 100       
CODE_CHUNK_OVERLAP = 20      
CODE_MAX_CHARS = 4000        
BATCH_SIZE = 10

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

# --- Helper Function: Extract Archive (ZIP or RAR) ---
# <-- 2. 函数被重构
def _extract_archive(archive_path: Path, extract_to: Path):
    """ Extracts a ZIP or RAR file. """
    suffix = archive_path.suffix.lower()
    logger.info(f"Attempting to extract '{archive_path}' (format: {suffix}) to '{extract_to}'")

    if suffix == '.zip':
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logger.info(f"Successfully extracted ZIP '{archive_path}'")
        except zipfile.BadZipFile:
            logger.error(f"Error: '{archive_path}' is not a valid zip file or is corrupted.")
            raise ValueError("Invalid or corrupted zip file.")
        except Exception as e:
            logger.error(f"Error extracting zip file '{archive_path}': {e}")
            raise
    
    elif suffix == '.rar':
        try:
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                rar_ref.extractall(extract_to)
            logger.info(f"Successfully extracted RAR '{archive_path}'")
        except rarfile.BadRarFile:
             logger.error(f"Error: '{archive_path}' is not a valid RAR file or is corrupted.")
             raise ValueError("Invalid or corrupted RAR file.")
        except Exception as e:
            logger.error(f"Error extracting RAR file '{archive_path}': {e}")
            raise
    else:
        logger.error(f"Unsupported archive format for extraction: {suffix}")
        raise ValueError(f"Unsupported archive format: {suffix}. Only .zip and .rar are supported.")


# --- Helper Function: Get Embeddings via DashScope OpenAI Compatible API ---
async def get_embeddings_from_api(
    texts: List[str],
    base_url: str, # <-- 使用 base_url
    model_name: str,
    api_key: str, # <-- API Key 设为必需
    dimensions: Optional[int] = None # <-- 接收维度参数
) -> List[List[float]]:
    """ Asynchronously calls DashScope OpenAI Compatible Embedding API. """
    if not base_url: raise ValueError("DashScope base_url is required.")

    if base_url and ("localhost" in base_url or "127.0.0.1" in base_url or '172.31.192.1' in base_url):
        api_key = "DUMMY_KEY"
    if not api_key:
         raise ValueError("DashScope API key is required.")


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
    except APIConnectionError as e:
        logger.error(f"Failed to connect to DashScope API at {base_url}: {e}")
        raise ValueError("Could not connect to DashScope API.")

   # 2. 捕获限速错误
    except RateLimitError as e:
        logger.error(f"DashScope API rate limit exceeded: {e}")
        raise ValueError("DashScope API rate limit exceeded. Please wait.")
       
    except APIError as e:
        logger.error(f"DashScope API Error: {e.status_code} - {e.message} (Code: {e.code}, Type: {e.type})")
        detail = e.message;
        if e.body and 'message' in e.body: detail = e.body['message']
        raise ValueError(f"DashScope API Error: {detail}")
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

 
    if model_base_url and ("localhost" in model_base_url or "127.0.0.1" or '172.31.192.1' in model_base_url):
        model_api_key = "DUMMY_KEY" # 本地模型允许无 API Key
        logger.info(f"[KB {kb_id}] Detected local model endpoint: {model_base_url}. API Key check will be skipped.")

    # 2. 验证模型信息 (!! 已修改 !!)
    if not model_base_url:
        logger.error(f"[KB {kb_id}] Model base_url (endpoint_url) is missing.") #
        _update_parsing_status(db, kb_id, "error", None, "Model config error: Base URL missing.")
        db.close(); return

    if not model_api_key:
        logger.error(f"[KB {kb_id}] Model API Key is missing for a non-local model.") #
        _update_parsing_status(db, kb_id, "error", None, "Model config error: API Key missing.") #
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
        
        # <-- 3. 修改了 IF 检查
        if file_path.suffix.lower() in ['.zip', '.rar']:
            temp_extract_dir = Path(f"./temp_extract_{kb_id}_{int(time.time())}")
            temp_extract_dir.mkdir(parents=True, exist_ok=True)
            if not _update_parsing_status(db, kb_id, "loading", 10, "Extracting archive file..."): return
            
            # <-- 4. 修改了函数调用
            _extract_archive(file_path, temp_extract_dir)
            input_dir = temp_extract_dir
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

        if not all_embeddings:
            raise ValueError("Embedding generation resulted in zero vectors. Cannot proceed.")


        discovered_dimension = len(all_embeddings[0])
        if discovered_dimension <= 0:
            raise ValueError(f"API returned an invalid dimension: {discovered_dimension}")

        # 检查预设维度 (来自 kb_service, 对于 Ollama 是 None)
        if model_dimensions:
            # (情况 A) 维度是预设的 (例如 BAAI, OpenAI)
            # kb_service.py 应该已经创建了集合
            logger.info(f"[KB {kb_id}] Using pre-configured Qdrant collection '{collection_name}' (Expected dim: {model_dimensions}).")
            if model_dimensions != discovered_dimension:
                # 这是一个严重的配置错误
                logger.error(f"[KB {kb_id}] FATAL: Pre-set dimension ({model_dimensions}) does not match API discovered dimension ({discovered_dimension}).")
                raise ValueError(f"Configuration mismatch: DB dimension ({model_dimensions}) != API dimension ({discovered_dimension})")
            
            # (可选的安全检查) 确保集合存在
            try:
                if not qdrant.collection_exists(collection_name):
                    logger.warning(f"[KB {kb_id}] Collection was missing! Recreating with pre-set dim: {model_dimensions}")
                    qdrant.recreate_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(size=model_dimensions, distance=models.Distance.COSINE)
                    )
            except Exception as e:
                logger.error(f"[KB {kb_id}] Failed safety check for collection: {e}")
                raise

        else:
            # (情况 B) 维度是 None (例如 Ollama)
            # 我们 *必须* 在这里创建集合
            logger.warning(f"[KB {kb_id}] Model dimension was None. Creating collection '{collection_name}' with discovered dimension: {discovered_dimension}")
            try:
                # 使用 recreate_collection 来安全地覆盖任何旧的、维度错误的集合
                qdrant.recreate_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=discovered_dimension, distance=models.Distance.COSINE)
                )
                logger.info(f"[KB {kb_id}] Successfully created/recreated collection '{collection_name}' with dim {discovered_dimension}.")
            except Exception as e:
                logger.error(f"[KB {kb_id}] Failed to dynamically create Qdrant collection: {e}", exc_info=True)
                raise ValueError(f"Failed to create Qdrant collection: {e}")

        # (!! --- 修复结束 --- !!)


        # Prepare Qdrant points (保持不变)
        points_to_upload = []
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