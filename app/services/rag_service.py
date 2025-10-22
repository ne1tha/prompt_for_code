# app/services/rag_service.py
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient, models
from openai import AsyncOpenAI

from app.schemas.rag import RagQueryRequest, RagQueryResponse, RetrievedContext, RagRetrieveRequest, RagRetrieveResponse
from app.crud import crud_model, crud_knowledgebase
from app.services.ingestion_pipeline import get_embeddings_from_api 

logger = logging.getLogger(__name__)

async def _call_generative_api(model_details: Dict[str, Any], prompt: str) -> str:
    """
    辅助函数：调用 Generative LLM API
    """
    client = AsyncOpenAI(
        api_key=model_details.get("api_key"),
        base_url=model_details.get("endpoint_url")
    )
    
    try:
        response = await client.chat.completions.create(
            model=model_details.get("name"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling Generative API ({model_details.get('name')}): {e}", exc_info=True)
        raise ValueError(f"Failed to get answer from generative model: {e}")

async def generate_rag_response(
    db: Session, 
    qdrant: QdrantClient, 
    request: RagQueryRequest
) -> RagQueryResponse:
    """
    (核心) 执行完整的 RAG 流程
    """
    if not request.knowledgebase_ids:
        raise ValueError("No knowledge bases selected for query.")

    # --- 1. 获取模型配置 ---
    
    # 1a. 获取用于 *生成* 的模型 (由用户选择)
    gen_model = crud_model.get_model(db, request.model_id)
    if not gen_model or gen_model.model_type != 'generative':
        raise ValueError(f"Invalid or non-generative model selected (ID: {request.model_id}).")
    gen_model_details = {
        "name": gen_model.name,
        "endpoint_url": gen_model.endpoint_url,
        "api_key": gen_model.api_key
    }

    # 1b. 获取用于 *嵌入* 的模型
    first_kb = crud_knowledgebase.get_kb(db, request.knowledgebase_ids[0])
    if not first_kb or not first_kb.embedding_model_id:
        raise ValueError(f"Selected KnowledgeBase (ID: {first_kb.id}) has no embedding model configured.")
        
    embed_model = crud_model.get_model(db, first_kb.embedding_model_id)
    if not embed_model or embed_model.model_type != 'embedding':
        raise ValueError(f"Invalid or non-embedding model found for KB (ID: {embed_model.id}).")

    logger.info(f"RAG Query: Using Embedding Model '{embed_model.name}' and Generative Model '{gen_model.name}'")

    # --- 2. 向量化查询 (Retrieve) ---
    try:
        query_vector = (await get_embeddings_from_api(
            texts=[request.query],
            base_url=embed_model.endpoint_url,
            model_name=embed_model.name,
            api_key=embed_model.api_key,
            dimensions=embed_model.dimensions
        ))[0]
    except Exception as e:
        logger.error(f"Failed to embed query '{request.query}': {e}", exc_info=True)
        raise ValueError(f"Failed to process query vector: {e}")

    # --- 3. 并行检索 Qdrant (Retrieve) ---
    all_contexts = []
    seen_texts = set()

    for kb_id in request.knowledgebase_ids:
        collection_name = f"kb_{kb_id}"
        try:
            search_results = qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=request.top_k,
                with_payload=True
            )
            
            for point in search_results:
                text = point.payload.get("text")
                if text not in seen_texts:
                    all_contexts.append(RetrievedContext(
                        source_kb_id=kb_id,
                        file_path=point.payload.get("metadata", {}).get("file_path", "N/A"),
                        text=text,
                        score=point.score
                    ))
                    seen_texts.add(text)
                    
        except Exception as e:
            logger.warning(f"Failed to search collection '{collection_name}': {e}")

    if not all_contexts:
        return RagQueryResponse(answer="Sorry, I couldn't find any relevant context in the selected knowledge bases.", retrieved_contexts=[])

    # --- 4. 构建 Metaprompt (Augment) ---
    context_string = "\n\n---\n\n".join([ctx.text for ctx in all_contexts])
    
    metaprompt = f"""
Please answer the user's question based *only* on the provided context information.
If the context does not contain the answer, state that you cannot find the information in the provided context.

[CONTEXT INFORMATION]:
{context_string}

[USER'S QUESTION]:
{request.query}

[YOUR ANSWER]:
"""

    # --- 5. 调用 LLM 生成答案 (Generate) ---
    try:
        final_answer = await _call_generative_api(gen_model_details, metaprompt)
        
        return RagQueryResponse(
            answer=final_answer,
            retrieved_contexts=all_contexts
        )
    except Exception as e:
        return RagQueryResponse(
            answer=f"Error during answer generation: {e}",
            retrieved_contexts=all_contexts
        )

async def retrieve_contexts_only(
    db: Session, 
    qdrant: QdrantClient, 
    request: RagRetrieveRequest
) -> RagRetrieveResponse:
    """
    (新增) 只执行检索，不调用生成模型
    返回增强提示词和检索到的上下文
    """
    if not request.knowledgebase_ids:
        raise ValueError("No knowledge bases selected for query.")

    # --- 1. 获取嵌入模型配置 ---
    first_kb = crud_knowledgebase.get_kb(db, request.knowledgebase_ids[0])
    if not first_kb or not first_kb.embedding_model_id:
        raise ValueError(f"Selected KnowledgeBase (ID: {first_kb.id}) has no embedding model configured.")
        
    embed_model = crud_model.get_model(db, first_kb.embedding_model_id)
    if not embed_model or embed_model.model_type != 'embedding':
        raise ValueError(f"Invalid or non-embedding model found for KB (ID: {embed_model.id}).")

    logger.info(f"RAG Retrieve: Using Embedding Model '{embed_model.name}' for retrieval only")

    # --- 2. 向量化查询 (Retrieve) ---
    try:
        query_vector = (await get_embeddings_from_api(
            texts=[request.query],
            base_url=embed_model.endpoint_url,
            model_name=embed_model.name,
            api_key=embed_model.api_key,
            dimensions=embed_model.dimensions
        ))[0]
    except Exception as e:
        logger.error(f"Failed to embed query '{request.query}': {e}", exc_info=True)
        raise ValueError(f"Failed to process query vector: {e}")

    # --- 3. 并行检索 Qdrant (Retrieve) ---
    all_contexts = []
    seen_texts = set()

    for kb_id in request.knowledgebase_ids:
        collection_name = f"kb_{kb_id}"
        try:
            search_results = qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=request.top_k,
                with_payload=True
            )
            
            for point in search_results:
                text = point.payload.get("text")
                if text not in seen_texts:
                    all_contexts.append(RetrievedContext(
                        source_kb_id=kb_id,
                        file_path=point.payload.get("metadata", {}).get("file_path", "N/A"),
                        text=text,
                        score=point.score
                    ))
                    seen_texts.add(text)
                    
        except Exception as e:
            logger.warning(f"Failed to search collection '{collection_name}': {e}")

    # --- 4. 构建增强提示词 (Augment) ---
    if all_contexts:
        context_string = "\n\n---\n\n".join([ctx.text for ctx in all_contexts])
        
        # 构建完整的元提示词（用于调试）
        metaprompt = f"""
请基于以下参考信息回答问题。如果参考信息中没有相关内容，请说明无法找到相关信息。

[参考信息]:
{context_string}

[用户问题]:
{request.query}

[请回答]:
"""
        
        # 构建简化的增强提示词（用于实际使用）
        enhanced_prompt = f"""基于以下参考信息回答问题：

参考信息：
{context_string}

问题：{request.query}

请根据上述参考信息回答："""
    else:
        # 如果没有检索到相关内容
        metaprompt = f"问题：{request.query}\n\n（未找到相关参考信息）"
        enhanced_prompt = request.query

    return RagRetrieveResponse(
        enhanced_prompt=enhanced_prompt,
        retrieved_contexts=all_contexts,
        metaprompt=metaprompt if all_contexts else None
    )