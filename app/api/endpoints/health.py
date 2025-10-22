from fastapi import APIRouter, Depends
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.lifespan import get_qdrant_client

router = APIRouter()

def get_db():
    """ 依赖项: 获取 SQLAlchemy 会话 """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", tags=["Health"])
async def read_root():
    return {"message": "知识智能平台 API 正在运行"}

@router.get("/health", tags=["Health"])
async def health_check(
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """
    执行健康检查，验证与数据库的连接。
    """
    try:
        # 1. 检查 PostgreSQL
        db.execute_script("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    try:
        # 2. 检查 Qdrant
        qdrant.get_collections()
        qdrant_status = "ok"
    except Exception as e:
        qdrant_status = f"error: {e}"

    return {
        "status": "ok" if db_status == "ok" and qdrant_status == "ok" else "error",
        "dependencies": {
            "postgresql_db": db_status,
            "qdrant_vector_db": qdrant_status
        }
    }