from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, File, UploadFile
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from typing import List
import logging
from app.schemas.knowledgebase import ( # (!! 修改这个 import !!)
    KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate, 
    StartParsingRequest, GenerateSummaryRequest, 
    GenerateGraphRequest  # <-- (1) 添加 GenerateGraphRequest
)
from app.services import ( # (!! 修改这个 import !!)
    kb_service, generation_service, 
    kg_service  # <-- (2) 添加 kg_service
)
from app.crud import crud_model, crud_knowledgebase
from app.api.endpoints.health import get_db # 重用 get_db
from app.core.lifespan import get_qdrant_client # 重用 get_qdrant_client
from app.db.session import SessionLocal # 导入 SessionLocal 用于后台任务
from app.schemas.knowledgebase import KnowledgeBase as KnowledgeBaseSchema
router = APIRouter()
logger = logging.getLogger(__name__)
def get_db_for_bg_task():
    """ 为后台任务创建独立的数据库会话 """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def convert_sqlalchemy_to_pydantic(db_obj) -> KnowledgeBaseSchema:
    """
    Manually converts SQLAlchemy object to Pydantic Schema.
    (已更新) 确保 'kb_type' 字段被正确传递。
    """
    print("----- DEBUG: Inside convert_sqlalchemy_to_pydantic -----")
    if not db_obj:
        return None
        
    print(f"Received db_obj type: {type(db_obj)}")
    
    # 直接读取属性
    _id = db_obj.id
    _name = db_obj.name
    _description = db_obj.description
    _parentId = db_obj.parentId
    _status = db_obj.status
    _parsing_state = db_obj.parsing_state
    _source_file_path = db_obj.source_file_path
    
    # 从数据库对象中读取新的 'kb_type' 字段
    _kb_type = db_obj.kb_type 
    print(f"Read kb_type: {_kb_type}") # (调试)
    # --- (修改结束) ---

    print("Attempting to create Pydantic object...")
    try:
        # 确保关键字参数与 Pydantic Schema 字段名 (snake_case 或 schema 中定义的) 完全匹配
        pydantic_instance = KnowledgeBaseSchema(
            id=_id,
            name=_name,
            description=_description,
            parentId=_parentId, # Pydantic Schema 定义的是 parentId
            

            # 将 _kb_type 传递给 Pydantic Schema 的 kb_type 字段
            kb_type=_kb_type, 

            
            status=_status,
            parsing_state=_parsing_state,
            source_file_path=_source_file_path
        )
        print("Pydantic object created successfully.")
        print("-------------------------------------------------------")
        return pydantic_instance
        
    except Exception as e:
        print(f"Error creating Pydantic object: {e}")
        # 打印一下传递给构造函数的值
        print("Values passed to constructor:")
        # --- (!! 更新调试信息 !!) ---
        print(f"  id={_id}, name={_name}, description={_description}, parentId={_parentId}, kb_type={_kb_type}")
        print(f"  status={_status}, parsing_state={_parsing_state}, source_file_path={_source_file_path}")
        print("-------------------------------------------------------")
        return None # 创建失败返回 None
    
    
@router.get(
    "/",
    response_model=List[KnowledgeBase],
    summary="[KB Store] 获取所有知识库"
)
def read_kbs(db: Session = Depends(get_db)):
    """
    (fetchKnowledgeBases) 检索所有知识库。
   
    """
    return kb_service.get_all_kbs(db)

@router.post(
    "/",
    response_model=KnowledgeBase,
    status_code=status.HTTP_201_CREATED,
    summary="[KB Store] 创建一个新知识库"
)
def create_kb(
    kb_in: KnowledgeBaseCreate,
    db: Session = Depends(get_db)
):
    """
    (createKnowledgeBase) 创建一个新知识库条目。
   
    """
    return kb_service.create_new_kb(db, kb_in)

@router.get(
    "/{id}",
    response_model=KnowledgeBase,
    summary="[KB Store] 获取单个知识库（用于轮询）"
)
def read_kb(id: int, db: Session = Depends(get_db)):
    """
    (_pollParsingStatus) 获取单个 KB 的状态。
   
    """
    db_kb = kb_service.get_kb_by_id(db, id)
    if db_kb is None:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")
    return db_kb

@router.put(
    "/{id}",
    response_model=KnowledgeBase,
    summary="[KB Store] 更新知识库（例如：重命名）"
)
def update_kb(
    id: int,
    kb_in: KnowledgeBaseUpdate,
    db: Session = Depends(get_db)
):
    """
    (updateKnowledgeBase) 更新 KB 的元数据。
   
    """
    db_kb = kb_service.update_kb_details(db, id, kb_in)
    if db_kb is None:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")
    return db_kb

@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[KB Store] 删除知识库"
)
def delete_kb(
    id: int,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """
    (deleteKnowledgeBase) 删除 KB，包括其 Qdrant 集合。
   
    """
    deleted_kb = kb_service.delete_kb_by_id(db, qdrant, id)
    if deleted_kb is None:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")
    return None


@router.post(
    "/{id}/upload",
    response_model=KnowledgeBaseSchema,
    summary="[KB Store] 上传知识库的源文件"
)
def upload_kb_file(
    id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        updated_kb_sqlalchemy = kb_service.save_kb_file(db, kb_id=id, file=file)
        if updated_kb_sqlalchemy is None:
            raise HTTPException(status_code=404, detail="KnowledgeBase not found")

        # --- (关键修复) 使用辅助函数手动转换 ---
        pydantic_obj = convert_sqlalchemy_to_pydantic(updated_kb_sqlalchemy)
        if not pydantic_obj:
             # 如果转换失败
             logger.error(f"Failed to convert SQLAlchemy object to Pydantic for KB {id} after upload.")
             raise HTTPException(status_code=500, detail="Internal server error during data conversion.")
             
        # 打印确认一下 (可以删掉)
        print("----- DEBUG: Returning MANUALLY converted Pydantic object -----")
        print(pydantic_obj.model_dump(by_alias=True))
        print("---------------------------------------------")

        # 返回手动创建的 Pydantic 对象
        return pydantic_obj
        # --- 修复结束 ---

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    
    
    
# --- (!! 修正后的 start_parsing 端点 !!) ---
@router.post(
    "/{id}/parse",
    response_model=KnowledgeBaseSchema, # <-- 使用别名 Schema
    summary="[KB Store] 开始解析（摄取）知识库"
)
def start_parsing(
    id: int,
    parse_request: StartParsingRequest,
    background_tasks: BackgroundTasks, # FastAPI 注入
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """
    (startParsing) 触发知识摄取管道。
    """
    try:
        # (!! 关键修复 !!) 调用 service 层函数，并传递 background_tasks
        db_kb = kb_service.start_kb_parsing(
            db=db,
            qdrant=qdrant,
            kb_id=id,
            embedding_model_id=parse_request.embedding_model_id,
            background_tasks=background_tasks # <-- 传递下去
        )
        # Service 层内部已经处理了 background task 的添加和状态更新

        if db_kb is None:
            # Service 层如果返回 None 通常意味着 KB 未找到或准备失败
            raise HTTPException(status_code=404, detail="KnowledgeBase not found or failed to initialize parsing.")

        # (!! 关键修复 !!) 转换并返回 processing 状态的对象
        pydantic_kb = convert_sqlalchemy_to_pydantic(db_kb)
        if not pydantic_kb:
             raise HTTPException(status_code=500, detail="Failed to process knowledge base data after starting parse.")
        return pydantic_kb

    except ValueError as e: # 捕获来自 service 层的验证错误
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as http_exc: # 重新抛出 service 层可能的 HTTP 异常
        raise http_exc
    except Exception as e: # 捕获其他意外错误
        logger.error(f"Failed to start parsing for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error while initiating parsing task: {e}")
# --- 修复结束 ---

@router.post(
    "/{id}/cancel",
    response_model=KnowledgeBase,
    summary="[KB Store] 取消正在进行的解析"
)
def cancel_parsing(
    id: int,
    db: Session = Depends(get_db)
):
    """
    (cancelParsing) 请求停止解析过程。
   
    """
    db_kb = kb_service.cancel_kb_parsing(db, id)
    if db_kb is None:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")
    return db_kb


@router.post(
    "/{id}/generate-summary",
    response_model=KnowledgeBaseSchema,
    summary="[KB Store] (RAG-B) 生成 L2a 摘要子知识库"
)
async def generate_l2a_summary( 
    id: int, 
    request: GenerateSummaryRequest,
    # background_tasks: BackgroundTasks, # <-- (!! 移除 !!) 不再需要后台任务
    db: Session = Depends(get_db),
    # qdrant: QdrantClient = Depends(get_qdrant_client) # <-- (!! 移除 !!) 不再需要 Qdrant 客户端
):
    """
    (RAG 循环 B) (已修复为混合架构)
    (!! 修改 !!) 现在只生成 L2a 条目和文件，不自动开始解析。
    """
    logger.info(f"[KB {id}] 收到生成 L2a 摘要的请求...")

    try:
        # --- 1. 获取父知识库和生成模型 (保持不变) ---
        parent_kb = crud_knowledgebase.get_kb(db, id)
        # ... (检查 parent_kb)
        generation_model = crud_model.get_model(db, request.generation_model_id)
        # ... (检查 generation_model)

        # --- 2. 调用 Generation Service (异步, 保持不变) ---
        logger.info(f"[KB {id}] 正在调用 generation_service 管道...")
        new_sub_kb = await generation_service.generate_summary_pipeline(
            db=db,
            parent_kb=parent_kb,
            generation_model=generation_model
        )
        logger.info(f"[KB {id}] Generation service 完成。新的 L2a KB ID: {new_sub_kb.id}")

        # --- 3. (!! 移除 !!) 不再自动调用 Ingestion Service ---
        # logger.info(f"[KB {new_sub_kb.id}] 正在为新的 L2a 摘要触发摄取...")
        # processing_kb = kb_service.start_kb_parsing(
        #     db=db,
        #     qdrant=qdrant,
        #     kb_id=new_sub_kb.id,
        #     embedding_model_id=request.embedding_model_id,
        #     background_tasks=background_tasks # <-- 移除
        # ) 

        # --- 4. 返回响应 (!! 修改 !!) ---
        # 直接转换并返回新创建的 new_sub_kb (它将是 'new' 状态)
        pydantic_kb = convert_sqlalchemy_to_pydantic(new_sub_kb) # 使用 new_sub_kb
        if not pydantic_kb:
             raise HTTPException(status_code=500, detail="Failed to process new knowledge base data after summary generation.")

        logger.info(f"[KB {new_sub_kb.id}] L2a 摘要已创建 (状态: {new_sub_kb.status})，等待手动解析。")
        return pydantic_kb

    except FileNotFoundError as e:
        logger.error(f"Generate summary failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, RuntimeError) as e:
        logger.error(f"Generate summary failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Generate summary failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    
@router.post(
    "/{id}/generate-graph",
    response_model=KnowledgeBaseSchema,
    summary="[KB Store] (RAG-B) 生成 L2b 知识图谱子知识库"
)
async def generate_l2b_graph( # (1) <-- 关键修复：改回 async def
    id: int,
    request: GenerateGraphRequest,
    db: Session = Depends(get_db)
):
    """
    (RAG 循环 B - L2b) (已修复为混合架构)
    """
    logger.info(f"[KB {id}] 收到生成 L2b 知识图谱的请求...")

    try:
        # --- 1. 获取父知识库和生成模型 (同步) ---
        parent_kb = crud_knowledgebase.get_kb(db, id)
        if not parent_kb:
            raise HTTPException(status_code=404, detail="Parent KnowledgeBase not found")
        
        generation_model = crud_model.get_model(db, request.generation_model_id)
        if not generation_model:
            raise HTTPException(status_code=404, detail="Generation model not found")

        # --- 2. 调用 KG Service (异步) ---
        logger.info(f"[KB {id}] 正在调用 kg_service 管道...")
        # (2) <-- 关键修复：添加 await
        new_sub_kb = await kg_service.generate_graph_pipeline(
            db=db,
            parent_kb=parent_kb,
            generation_model=generation_model
        )
        logger.info(f"[KB {id}] KG service 完成。新的 L2b KB ID: {new_sub_kb.id}")

        # --- 4. 返回响应 (同步) ---
        pydantic_kb = convert_sqlalchemy_to_pydantic(new_sub_kb)
        if not pydantic_kb:
             raise HTTPException(status_code=500, detail="Failed to process new knowledge base data after graph generation.")
        
        logger.info(f"[KB {new_sub_kb.id}] L2b 知识图谱已创建。")
        return pydantic_kb

    except FileNotFoundError as e:
        logger.error(f"Generate graph failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, RuntimeError) as e:
        logger.error(f"Generate graph failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Generate graph failed for KB {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")