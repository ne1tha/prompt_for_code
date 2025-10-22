# app/api/endpoints/rag.py
from fastapi import APIRouter, Depends, HTTPException, logger
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient

from app.schemas.rag import RagQueryRequest, RagQueryResponse, RagRetrieveRequest, RagRetrieveResponse
from app.services.rag_service import generate_rag_response, retrieve_contexts_only
from app.api.endpoints.health import get_db # 复用
from app.core.lifespan import get_qdrant_client # 复用

router = APIRouter()

@router.post(
    "/query",
    response_model=RagQueryResponse,
    summary="[RAG] 执行RAG查询并生成答案"
)
async def execute_rag_query(
    request: RagQueryRequest,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """
    (前端 '生成' 按钮调用)
    接收用户查询、知识库列表和模型ID，
    执行完整的 RAG 流程并返回最终答案。
    """
    try:
        response = await generate_rag_response(
            db=db,
            qdrant=qdrant,
            request=request
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error during RAG query: {e}")

@router.post(
    "/retrieve",
    response_model=RagRetrieveResponse,
    summary="[RAG] 仅检索相关内容并构建增强提示词"
)
async def retrieve_contexts_only_endpoint(
    request: RagRetrieveRequest,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """
    (新增) 只执行检索，不调用生成模型
    返回增强提示词和检索到的上下文
    """
    try:
        response = await retrieve_contexts_only(
            db=db,
            qdrant=qdrant,
            request=request
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error during RAG retrieval: {e}")