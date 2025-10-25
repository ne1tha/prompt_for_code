# app/services/generation_service.py

import aiofiles
from pathlib import Path
import openai
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
import httpx
from datetime import datetime, timezone
from typing import Dict, Any
import os

# (1) --- LlamaIndex/RAG (已移除) ---
# (移除了 chromadb, llama_index.* 的所有导入)

# (2) --- 新增 RAG 服务导入 ---
from qdrant_client import QdrantClient
from app.services.rag_service import retrieve_contexts_only
from app.schemas.rag import RagRetrieveRequest

# 导入数据库模型和 CRUD
import app.crud.crud_knowledgebase as crud_kb
from app.models.knowledgebase import KnowledgeBase as models_kb
from app.models.model import Model as models_model

# 导入 Pydantic 模式
from app.schemas.knowledgebase import KnowledgeBaseCreate

# 导入日志
import logging
logger = logging.getLogger(__name__)

# (保持不变)
FILE_SIZE_THRESHOLD_BYTES = 300 * 1024 


async def _perform_rag_retrieval(
    db: Session,                # (3) <-- 新增 db
    qdrant: QdrantClient,       # (4) <-- 新增 qdrant
    parent_kb: models_kb
) -> str:
    """
    (!! 已重构 !!)
    使用 app.services.rag_service 执行 RAG 检索以获取相关代码块。
    不再使用 LlamaIndex/ChromaDB。
    """
    logger.info(f"[KB {parent_kb.id}] 文件过大，启动 RAG 检索 (使用 rag_service)...")

    # --- 4a. 定义专业查询 (满足要求 2) ---
    query_text = """
    分析此代码文件的软件架构和核心逻辑。
    请重点关注以下方面：
    1.  文件级别的主要职责：此文件的核心目的是什么？
    2.  关键组件定义：提取主要的类、接口、函数、类型或数据结构。
    3.  设计模式与结构：识别任何明显的设计模式（如工厂、单例、观察者、依赖注入）或核心算法。
    4.  组件交互与依赖：描述关键组件之间如何交互，包括主要的方法调用、继承关系、组合关系或事件流。
    5.  公共 API 接口：如果适用，识别暴露给系统其他部分的公共函数或类方法。
    """

    # --- 4b. 准备 RAG 检索请求 (使用您提供的 schema) ---
    # "条件放的宽一点"，检索更多块以保证不遗漏关键信息
    rag_request = RagRetrieveRequest(
        query=query_text,
        knowledgebase_ids=[parent_kb.id], # 仅检索父知识库
        top_k=20 # (满足要求 3)
    )

    # --- 4c. 调用您框架内的 RAG 服务 ---
    try:
        logger.info(f"正在调用 retrieve_contexts_only (k=20) for KB {parent_kb.id}...")
        
        # (!! 核心替换 !!)
        # 调用 rag_service.py 中的函数
        rag_response = await retrieve_contexts_only(
            db=db,
            qdrant=qdrant,
            request=rag_request
        )
        
        retrieved_contexts = rag_response.retrieved_contexts
        
        if not retrieved_contexts:
            raise ValueError("RAG 检索未返回任何代码块，无法生成摘要。")

        logger.info(f"RAG 服务成功检索到 {len(retrieved_contexts)} 个代码块。")

    except Exception as e:
        logger.error(f"调用 RAG 检索服务 (retrieve_contexts_only) 失败: {e}", exc_info=True)
        raise RuntimeError(f"Failed to retrieve contexts for KB {parent_kb.id}: {e}")

    # --- 4d. 格式化上下文 (使用 rag.py 中的 RetrievedContext 格式) ---
    context_chunks = []
    for i, ctx in enumerate(retrieved_contexts):
        chunk_header = f"--- 相关代码块 {i+1} (相似度: {ctx.score:.4f}) (来源: {ctx.file_path}) ---"
        context_chunks.append(f"{chunk_header}\n{ctx.text}")
        
    return "\n\n".join(context_chunks)


async def generate_summary_pipeline(
    db: Session,
    qdrant: QdrantClient, # (5) <-- 关键: 新增 Qdrant 客户端依赖
    parent_kb: models_kb,
    generation_model: models_model
    # embedding_model: models_model # (6) (保持) L1 解析时使用的模型
) -> models_kb:
    """
    RAG 循环 B (L2a) 核心管道。
    (已更新) 采用混合策略。
    (已更新) RAG 检索现在调用 rag_service。
    """
    
    logger.info(f"开始为 KB ID: {parent_kb.id} 生成 L2a 摘要...")

    # --- 1. 验证输入 (保持不变) ---
    if not parent_kb.source_file_path:
        raise ValueError("Parent knowledge base has no source file path.")
    if generation_model.model_type != "generative":
        raise ValueError(f"Model '{generation_model.name}' is not a 'generation' model.")
    if not generation_model.endpoint_url:
        raise ValueError(f"Model '{generation_model.name}' missing 'endpoint_url'.")

    source_file_path_str = parent_kb.source_file_path
    source_file_path = Path(source_file_path_str)
    if not source_file_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_file_path}")

    # --- 2. “机会主义” L2b 检查 (保持不变) ---
    logger.info(f"[KB {parent_kb.id}] 正在检查是否存在 L2b 知识图谱...")
    knowledge_graph_content = ""
    
    l2b_graph_kb = crud_kb.find_child_by_type(
        db=db, 
        parent_id=parent_kb.id, 
        kb_type="l2b_graph"
    )

    if l2b_graph_kb and l2b_graph_kb.source_file_path:
        logger.info(f"[KB {parent_kb.id}] 找到了 L2b 图谱: {l2b_graph_kb.source_file_path}")
        graph_path = Path(l2b_graph_kb.source_file_path)
        if graph_path.exists():
            async with aiofiles.open(graph_path, mode='r', encoding='utf-8') as f:
                knowledge_graph_content = await f.read()
    else:
        logger.info(f"[KB {parent_kb.id}] 未找到 L2b 图谱，将生成标准摘要。")

    # --- 3. (!! 核心变更 !!) 混合策略：读取完整文件 vs RAG ---
    code_content: str
    context_source: str # 用于提示词
    
    try:
        file_size = os.path.getsize(source_file_path_str)
        logger.info(f"源文件大小: {file_size} 字节. (阈值: {FILE_SIZE_THRESHOLD_BYTES} 字节)")
        
        if file_size < FILE_SIZE_THRESHOLD_BYTES:
            # (策略 1: 文件较小，读取全部内容)
            logger.info("文件小于阈值，正在读取完整文件内容...")
            async with aiofiles.open(source_file_path, mode='r', encoding='utf-8') as f:
                code_content = await f.read()
            context_source = "完整源代码"
        else:
            # (策略 2: 文件较大，执行 RAG)
            logger.info("文件大于阈值，启动 RAG 检索 (调用 _perform_rag_retrieval)...")
            code_content = await _perform_rag_retrieval(
                db=db,                    # <-- 传入 db
                qdrant=qdrant,            # <-- 传入 qdrant
                parent_kb=parent_kb
                # (注意: 不再需要传入 embedding_model, 
                #  因为 rag_service 会自己处理)
            )
            context_source = "RAG 检索到的相关代码块"
            
    except Exception as e:
        logger.error(f"获取上下文内容失败 (KB ID: {parent_kb.id}): {e}", exc_info=True)
        raise RuntimeError(f"Failed to get context for summary: {e}")


    # --- 4. 准备动态 Prompt (保持不变) ---
    prompt: str
    
    # 基础提示词
    base_prompt = f"""
    您是一位资深软件架构专家。
    您的任务是撰写一份简洁的高层次 Markdown 总结。
    总结应描述：
    1.  该文件的主要目的或职责。
    2.  定义的关键类、函数或组件。
    3.  它们之间如何交互（如果适用）。
    请仅返回 Markdown 格式的总结。
    """
    
    # 根据上下文来源和 L2b 图谱动态构建
    if knowledge_graph_content:
        # (高级 Prompt - RAG/全文 + 图谱)
        prompt = f"""
        {base_prompt}
        
        为了帮助您理解，这里有两份上下文：
        
        [上下文 1: 关键结构关系知识图谱 (JSON 格式)]:
        {knowledge_graph_content}

        [上下文 2: {context_source}]:
        {code_content}
        
        请**结合**上述的知识图谱和{context_source}，撰写您的总结。
        """
    else:
        # (标准 Prompt - 仅 RAG/全文)
        prompt = f"""
        {base_prompt}
        
        请分析以下提供的 "{context_source}" 并撰写您的总结。
        
        ---
        {context_source} ({source_file_path.name}):
        ---
        {code_content}
        """

    # --- 5. 调用 LLM API (保持不变) ---
    logger.info(f"正在调用 LLM: {generation_model.name} (上下文来源: {context_source})")
    client = AsyncOpenAI(
        api_key=generation_model.api_key or "DUMMY_KEY",
        base_url=generation_model.endpoint_url
    )
    
    try:
        completion = await client.chat.completions.create(
            model=generation_model.name,
            messages=[
                {"role": "system", "content": "You are an expert senior software architect."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2, 
        )
        
        summary_content = completion.choices[0].message.content
        if not summary_content:
            raise ValueError("LLM returned an empty summary.")
            
    except (httpx.ConnectError, openai.APIError) as e:
        raise RuntimeError(f"Failed to call generation API: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {str(e)}")

    # --- 6. 将摘要保存为新文件 (保持不变) ---
    summary_dir = Path("uploads/summaries")
    summary_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    summary_filename = f"{source_file_path.stem}_summary_kb_{parent_kb.id}_{ts}.md"
    summary_file_path = summary_dir / summary_filename
    
    logger.info(f"正在将摘要保存到: {summary_file_path}")
    async with aiofiles.open(summary_file_path, mode='w', encoding='utf-8') as f:
        await f.write(summary_content)

    # --- 7. 在数据库中创建新的子知识库条目 (保持不变) ---
    logger.info(f"正在数据库中创建 L2a 子知识库条目...")
    sub_kb_schema = KnowledgeBaseCreate(
        name=f"{parent_kb.name} - AI Summary",
        description=f"AI-generated summary for {parent_kb.name}. Model: {generation_model.name}. Context: {context_source}",
        parentId=parent_kb.id,
        kb_type="l2a_summary"
    )
    
    new_sub_kb = crud_kb.create_kb(
        db=db,
        kb_in=sub_kb_schema,
        source_file_path=str(summary_file_path.resolve())
    )
    
    logger.info(f"成功创建 L2a 子知识库, ID: {new_sub_kb.id}")
    return new_sub_kb
