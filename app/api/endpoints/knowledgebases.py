from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, File, UploadFile
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from typing import List
import logging
from app.schemas.knowledgebase import KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate, StartParsingRequest
from app.services import kb_service, model_service
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
    Ensures keyword arguments match Pydantic field names (snake_case).
    """
    print("----- DEBUG: Inside convert_sqlalchemy_to_pydantic -----")
    if not db_obj:
        print("Received None db_obj, returning None.")
        print("-------------------------------------------------------")
        return None
        
    print(f"Received db_obj type: {type(db_obj)}")
    
    # 直接读取属性 (我们知道它们存在)
    _id = db_obj.id
    _name = db_obj.name
    _description = db_obj.description
    _parentId = db_obj.parentId
    _status = db_obj.status
    _parsing_state = db_obj.parsing_state
    _source_file_path = db_obj.source_file_path # 直接访问
    
    print(f"Read id: {_id}")
    print(f"Read name: {_name}")
    print(f"Read description: {_description}")
    print(f"Read parentId: {_parentId}")
    print(f"Read status: {_status}")
    print(f"Read parsing_state: {_parsing_state}")
    print(f"Read source_file_path: {_source_file_path}") # <-- 再次确认这里的值

    print("Attempting to create Pydantic object...")
    try:
        # 确保关键字参数与 Pydantic Schema 字段名 (snake_case) 完全匹配
        pydantic_instance = KnowledgeBaseSchema(
            id=_id,
            name=_name,
            description=_description,
            parentId=_parentId, # Pydantic Schema 定义的是 parentId
            status=_status,
            parsing_state=_parsing_state,
            source_file_path=_source_file_path # 传递读取到的值
        )
        print("Pydantic object created successfully.")
        print("-------------------------------------------------------")
        return pydantic_instance
        
    except Exception as e:
        print(f"Error creating Pydantic object: {e}")
        # 打印一下传递给构造函数的值，看看是否有问题
        print("Values passed to constructor:")
        print(f"  id={_id}, name={_name}, description={_description}, parentId={_parentId}")
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