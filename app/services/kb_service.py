# app/services/kb_service.py

import logging
import os
import shutil
from pathlib import Path
from fastapi import UploadFile, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams
from typing import List, Optional

from app.crud import crud_knowledgebase, crud_model
from app.models.knowledgebase import KnowledgeBase
from app.schemas.knowledgebase import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services.ingestion_pipeline import run_ingestion_pipeline
from app.core.config import settings

logger = logging.getLogger(__name__)
UPLOADS_DIR = Path("./uploads")


def get_all_kbs(db: Session) -> List[KnowledgeBase]:
    return crud_knowledgebase.get_kbs(db)

def get_kb_by_id(db: Session, kb_id: int) -> Optional[KnowledgeBase]:
    return crud_knowledgebase.get_kb(db, kb_id)

def create_new_kb(db: Session, kb_in: KnowledgeBaseCreate) -> KnowledgeBase:
    """
    创建新知识库，确保包含更新时间戳
    """
    logger.info(f"Creating new knowledge base: {kb_in.name}")

    db_kb = crud_knowledgebase.create_kb(db, kb_in)
    
    logger.info(f"Created knowledge base with ID: {db_kb.id}, updated_at: {db_kb.updated_at}")
    return db_kb

def update_kb_details(db: Session, kb_id: int, kb_in: KnowledgeBaseUpdate) -> Optional[KnowledgeBase]:
    db_kb = crud_knowledgebase.get_kb(db, kb_id)
    if not db_kb:
        return None
    # 调用 crud 函数进行更新，它会返回刷新后的对象
    return crud_knowledgebase.update_kb(db, db_kb=db_kb, kb_in=kb_in)

def delete_kb_by_id(db: Session, qdrant: QdrantClient, kb_id: int) -> Optional[KnowledgeBase]:
    """
    (deleteKnowledgeBase) 删除 KB，包括 Qdrant 集合。
    """
    
    db_kb = crud_knowledgebase.get_kb(db, kb_id) # 1. 先获取KB信息
    if not db_kb: 
        return None

    # (新增) 记录文件路径
    file_to_delete = db_kb.source_file_path
    db_kb = crud_knowledgebase.delete_kb(db, kb_id)
    if not db_kb: return None
    collection_name = f"kb_{db_kb.id}"
    try:
        if qdrant.collection_exists(collection_name):
            qdrant.delete_collection(collection_name)
            logger.info(f"Qdrant collection '{collection_name}' deleted.")
    except Exception as e:
        logger.error(f"Failed to delete Qdrant collection '{collection_name}': {e}")
    if file_to_delete:
        try:
            file_path = Path(file_to_delete)
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"Successfully deleted file: {file_to_delete}")
            else:
                logger.warning(f"File not found, cannot delete: {file_to_delete}")
        except Exception as e:
            logger.error(f"Error deleting file '{file_to_delete}': {e}")
    return db_kb


def save_kb_file(db: Session, kb_id: int, file: UploadFile) -> Optional[KnowledgeBase]:
    """
    保存文件，更新数据库，并通过重新查询确保返回最新对象。
    """
    file_path = UPLOADS_DIR / f"kb_{kb_id}_{file.filename}"
    file_path_str = str(file_path)

    # 1. 保存文件到磁盘
    try:
        logger.debug(f"[KB {kb_id}] Attempting to save file to {file_path_str}")
        with file_path.open("wb") as buffer: shutil.copyfileobj(file.file, buffer)
        logger.info(f"[KB {kb_id}] File successfully saved to {file_path_str}")
    except Exception as e:
        logger.error(f"Save file {file_path_str} failed: {e}", exc_info=True)
        raise ValueError(f"File save failed: {e}")
    finally:
        file.file.close()

    # 2. 获取要更新的对象
    db_kb_to_update = crud_knowledgebase.get_kb(db, kb_id)
    if not db_kb_to_update:
        logger.error(f"KB {kb_id} not found right before updating source_file_path.")
        try: file_path.unlink(missing_ok=True)
        except OSError: pass
        return None

    # 3. 在对象上设置路径和重置状态
    try:
        # 重置知识库状态到初始状态
        db_kb_to_update.source_file_path = file_path_str
        db_kb_to_update.status = "error"  # 重置为 error 状态，表示需要重新解析
        db_kb_to_update.parsing_state = {"stage": "idle", "progress": 0}  # 重置解析状态
        db_kb_to_update.embedding_model_id = None  # 清除之前使用的模型
        
        # # 手动更新更新时间（因为 SQLAlchemy 的 onupdate 可能不会在直接赋值时触发）
        # from datetime import datetime, timezone
        # from sqlalchemy.sql import func
        # db_kb_to_update.updated_at = datetime.now(timezone.utc)
        
        db.add(db_kb_to_update)
        logger.debug(f"[KB {kb_id}] Attempting to commit source_file_path and reset status: {file_path_str}")
        db.commit()
        logger.info(f"[KB {kb_id}] Successfully committed source_file_path and reset status.")
    except Exception as commit_err:
        logger.error(f"Failed to commit source_file_path for KB {kb_id}: {commit_err}", exc_info=True)
        db.rollback()
        try: file_path.unlink(missing_ok=True)
        except OSError: pass
        raise HTTPException(status_code=500, detail="Database error saving file path.")

    # 4. 重新查询数据库获取最新状态
    refetched_db_kb = None
    try:
        logger.debug(f"[KB {kb_id}] Attempting to REFETCH object from DB...")
        refetched_db_kb = crud_knowledgebase.get_kb(db, kb_id)

        if refetched_db_kb:
             logger.debug(f"[KB {kb_id}] REFETCHED object - status: {refetched_db_kb.status}, parsing_state: {refetched_db_kb.parsing_state}, source_file_path: {refetched_db_kb.source_file_path}")
        else:
             logger.error(f"[KB {kb_id}] REFETCH failed! KB not found after commit.")
    except Exception as fetch_err:
         logger.error(f"Failed to refetch KB {kb_id} after commit: {fetch_err}", exc_info=True)
         refetched_db_kb = db_kb_to_update

    # 5. 最终日志和返回
    final_path = getattr(refetched_db_kb, 'source_file_path', 'ERROR_FETCHING')
    final_status = getattr(refetched_db_kb, 'status', 'UNKNOWN')
    logger.info(f"File saved and linked to KB {kb_id}: {final_path}, status reset to: {final_status}")
    return refetched_db_kb



def start_kb_parsing(
    db: Session,
    qdrant: QdrantClient,
    kb_id: int,
    embedding_model_id: int,
    background_tasks: BackgroundTasks
) -> Optional[KnowledgeBase]:
    """
    (startParsing) Validates, prepares Qdrant collection, updates status,
    and triggers the background knowledge ingestion pipeline.
    """
    # 1. Get KnowledgeBase object
    db_kb = crud_knowledgebase.get_kb(db, kb_id)
    if not db_kb:
        logger.error(f"[KB {kb_id}] KnowledgeBase not found for starting parsing.")
        return None

    # 2. Validate file path
    if not db_kb.source_file_path:
        raise ValueError("No source file uploaded for this KnowledgeBase. Please upload a file first.")
    file_path_obj = Path(db_kb.source_file_path)
    if not file_path_obj.exists():
        logger.error(f"[KB {kb_id}] Source file not found on server: {db_kb.source_file_path}")
        raise ValueError(f"File not found on server: {db_kb.source_file_path}")

    # 3. Get and validate embedding model info
    db_model = crud_model.get_model(db, embedding_model_id)
    if not db_model:
        raise ValueError("Embedding model not found")
    if db_model.model_type != 'embedding':
        raise ValueError(f"Model '{db_model.name}' is not an 'embedding' model.")
    required_dimension = db_model.dimensions
    if not required_dimension or required_dimension <= 0:
        raise ValueError(f"Model '{db_model.name}' dimensions are not set or invalid ({required_dimension}).")
    if not db_model.endpoint_url:
        raise ValueError(f"Model '{db_model.name}' is missing the 'endpoint_url'.")
    if not db_model.name:
        raise ValueError(f"Model '{db_model.name}' is missing the 'name' identifier.")

    # 4. Prepare Qdrant collection (Corrected Logic)
    collection_name = f"kb_{db_kb.id}"
    try:
        # 4a. Try to get existing collection info
        logger.debug(f"[KB {kb_id}] Checking Qdrant collection '{collection_name}'...")
        coll_info = qdrant.get_collection(collection_name)
        logger.debug(f"[KB {kb_id}] Collection '{collection_name}' found.")

        # 4b. Check vector parameters and dimension using correct attribute path
        current_vectors_params = coll_info.config.params.vectors # Correct path
        current_dimension = None

        if isinstance(current_vectors_params, models.VectorParams): # Default unnamed vector
             current_dimension = current_vectors_params.size
        elif isinstance(current_vectors_params, dict): # Named vectors
             # Try getting default '' or the first one found
             if '' in current_vectors_params:
                 current_dimension = current_vectors_params[''].size
             elif current_vectors_params:
                 first_vector_name = next(iter(current_vectors_params))
                 current_dimension = current_vectors_params[first_vector_name].size
                 logger.warning(f"[KB {kb_id}] Found named vectors, using size from '{first_vector_name}'.")

        # 4c. Compare dimensions and recreate if necessary
        if current_dimension is None:
             logger.warning(f"[KB {kb_id}] Could not determine vector dimension for existing collection '{collection_name}'. Recreating...")
             qdrant.recreate_collection(
                 collection_name=collection_name,
                 vectors_config=VectorParams(size=required_dimension, distance=Distance.COSINE)
             )
        elif current_dimension != required_dimension:
            logger.warning(f"[KB {kb_id}] Qdrant '{collection_name}' dim mismatch ({current_dimension} vs {required_dimension}). Recreating...")
            qdrant.recreate_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=required_dimension, distance=Distance.COSINE)
            )
        else:
             logger.info(f"[KB {kb_id}] Qdrant collection '{collection_name}' exists with correct dimension ({current_dimension}).")

    except Exception as get_coll_err:
        # 4d. Handle errors during get_collection (assume collection needs creation)
        # More specific error checking (e.g., for 404) could be added here if needed
        logger.info(f"[KB {kb_id}] Qdrant collection '{collection_name}' not found or error checking ({type(get_coll_err).__name__}). Attempting creation with dim {required_dimension}...")
        try:
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=required_dimension, distance=Distance.COSINE)
            )
            logger.info(f"[KB {kb_id}] Qdrant collection '{collection_name}' created successfully.")
        except Exception as create_err:
            # Handle creation failure (e.g., the 409 conflict if get_collection failed for other reasons)
            logger.error(f"[KB {kb_id}] Failed to create Qdrant collection '{collection_name}' after check failed: {create_err}", exc_info=True)
            db_kb.status = "error"
            db_kb.parsing_state = {"stage": "error", "message": f"Qdrant Check/Create Error: {create_err}"} # Report create error
            # db_kb.updated_at = datetime.now(timezone.utc)
            try: db.commit()
            except Exception as commit_err: logger.error(f"Commit error status failed: {commit_err}"); db.rollback()
            return db_kb # Return object with error status

    # --- Qdrant collection should now be ready ---

    # 5. Update database status to 'processing'
    db_kb.status = "processing"
    db_kb.parsing_state = {"stage": "pending", "progress": 0, "message": "Queued for processing..."}
    db_kb.embedding_model_id = db_model.id # Record which model is used
    # db_kb.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(db_kb) # Refresh to get potentially updated state from DB triggers/defaults (usually safe here)
    except Exception as commit_err:
        logger.error(f"[KB {kb_id}] Failed commit 'processing' status: {commit_err}", exc_info=True)
        db.rollback()
        # Raise exception to signal API failure (500)
        raise HTTPException(status_code=500, detail=f"Database error setting status for KB {kb_id}")

    # 6. Add the actual ingestion task to background tasks
    try:
        background_tasks.add_task(
            run_ingestion_pipeline,
            kb_id=kb_id,
            embedding_model_details={
                "name": db_model.name,
                "endpoint_url": db_model.endpoint_url,
                "api_key": db_model.api_key,
                "dimensions": db_model.dimensions # Pass dimensions to pipeline
            },
            file_path_str=db_kb.source_file_path, # Pass file path as string
            qdrant_host=settings.QDRANT_HOST,
            qdrant_port=settings.QDRANT_PORT
        )
        logger.info(f"[KB {kb_id}] Background task 'run_ingestion_pipeline' added.")
    except Exception as task_err:
        # Handle failure to add the task (rare, but possible)
        logger.error(f"[KB {kb_id}] Failed to add background task: {task_err}", exc_info=True)
        # Attempt to revert status to error
        db_kb.status = "error"
        db_kb.parsing_state = {"stage": "error", "message": "Failed to queue background task"}
        try:
            db.commit()
        except Exception:
            db.rollback() # Rollback if status update fails
        # Raise exception to signal API failure (500)
        raise HTTPException(status_code=500, detail=f"Failed to queue processing task for KB {kb_id}")

    # 7. Return the KnowledgeBase object (now with status='processing')
    return db_kb


def cancel_kb_parsing(db: Session, kb_id: int) -> Optional[KnowledgeBase]:
    db_kb = crud_knowledgebase.get_kb(db, kb_id)
    if not db_kb: return None
    if db_kb.status == 'processing':
        logger.warning(f"[KB {kb_id}] Requesting cancel parsing... (Updating status only)")
        db_kb.status = "ready" # Or 'cancelled'
        db_kb.parsing_state = {"stage": "cancelled"}
        # db_kb.updated_at = datetime.now(timezone.utc)
        try:
            db.commit(); db.refresh(db_kb)
        except Exception as e:
            logger.error(f"[KB {kb_id}] Failed commit 'cancelled' status: {e}"); db.rollback()
            return crud_knowledgebase.get_kb(db, kb_id)
    else:
         logger.info(f"[KB {kb_id}] Cancel request ignored, status is '{db_kb.status}'.")
    return db_kb