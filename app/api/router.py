from fastapi import APIRouter
from app.api.endpoints import health, knowledgebases, models
# (!! 新增 !!)
from app.api.endpoints import rag
# 这是 API 的主路由
# 我们将在这里注册所有其他的功能性路由
api_router = APIRouter()

# 包含健康检查路由
api_router.include_router(health.router)
api_router.include_router(rag.router, prefix="/rag", tags=["RAG"])
api_router.include_router(
    models.router, 
    prefix="/models", 
    tags=["Models"]
)
api_router.include_router(
    knowledgebases.router,
    prefix="/knowledgebases",
    tags=["KnowledgeBases"]
)

