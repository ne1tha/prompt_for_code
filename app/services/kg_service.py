# app/services/kg_service.py

import aiofiles
from pathlib import Path
import openai
from sqlalchemy.orm import Session # (1) <-- 关键修复：使用同步 Session
from openai import AsyncOpenAI # (2) 保持 AsyncOpenAI
import httpx
from datetime import datetime, timezone
import json

from llama_index.core.graph_stores import SimpleGraphStore

# 导入数据库模型和 CRUD
import app.crud.crud_knowledgebase as crud_kb
from app.models.knowledgebase import KnowledgeBase as models_kb
from app.models.model import Model as models_model

# 导入 Pydantic 模式
from app.schemas.knowledgebase import KnowledgeBaseCreate

# 导入日志
import logging
logger = logging.getLogger(__name__)


async def generate_graph_pipeline( 
    db: Session, 
    parent_kb: models_kb, 
    generation_model: models_model 
) -> models_kb:
    """
    RAG 循环 B (L2b) 的核心管道。 (已修复为混合架构)
    """
    
    logger.info(f"开始为 KB ID: {parent_kb.id} 生成 L2b 知识图谱...")

    # --- 1. 验证输入 (保持不变) ---
    if not parent_kb.source_file_path:
        raise ValueError("Parent knowledge base has no source file path.")
    if generation_model.model_type != "generative":
        raise ValueError(f"Model '{generation_model.name}' is not a 'generation' model.")
    source_file_path = Path(parent_kb.source_file_path)
    if not source_file_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_file_path}")

    # --- 2. 读取源文件内容 (保持 async) ---
    logger.info(f"正在读取源文件: {source_file_path}")
    async with aiofiles.open(source_file_path, mode='r', encoding='utf-8') as f:
        code_content = await f.read()

    # --- 3. 准备 Prompt (保持不变) ---
    prompt = f"""
    You are an expert code analyst. Your task is to analyze the following source code and extract key relationships as (Subject, Predicate, Object) triplets.
    Focus on:
    - Class Inheritance (e.g., [ClassName, "INHERITS_FROM", ParentClassName])
    - Function Calls (e.g., [FunctionName, "CALLS", CalledFunctionName])
    - Class Instantiation (e.g., [FunctionName, "INSTANTIATES", ClassName])
    Return your response as a valid JSON list of lists.
    Example: [["ClassA", "INHERITS_FROM", "BaseClass"], ["func_x", "CALLS", "util_func"]]
    Return ONLY the JSON list.
    ---
    Source Code ({source_file_path.name}):
    ---
    {code_content}
    """

    # --- 4. 调用 LLM API (保持 async) ---
    logger.info(f"正在调用 LLM: {generation_model.name} at {generation_model.endpoint_url}")
    client = AsyncOpenAI(
        api_key=generation_model.api_key or "DUMMY_KEY",
        base_url=generation_model.endpoint_url
    )
    
    triplets = []
    try:
        # (5) 保持 await
        completion = await client.chat.completions.create(
            model=generation_model.name,
            messages=[
                {"role": "system", "content": "You are an expert code analyst that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0, 
        )
        
        json_response = completion.choices[0].message.content
        if not json_response:
            raise ValueError("LLM returned an empty response.")
        
        triplets = json.loads(json_response)
        if not isinstance(triplets, list):
             raise ValueError("LLM did not return a valid JSON list.")
        
        logger.info(f"LLM 成功提取了 {len(triplets)} 个三元组。")
            
    except (httpx.ConnectError, openai.APIError) as e:
        raise RuntimeError(f"Failed to call generation API: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"LLM 返回了无效的 JSON: {e}. Response: {json_response[:200]}...")
        raise ValueError(f"LLM returned invalid JSON: {e}")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {str(e)}")

    # --- 5. 构建图谱并持久化为 JSON (保持不变) ---
    graph_dir = Path("uploads/graphs")
    graph_dir.mkdir(parents=True, exist_ok=True) 
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    graph_filename = f"{source_file_path.stem}_graph_kb_{parent_kb.id}_{ts}.json"
    graph_file_path = graph_dir / graph_filename
    
    try:
        # (!! 关键修复 !!)
        # 1. 直接初始化 SimpleGraphStore
        graph_store = SimpleGraphStore()
        
        # 2. 遍历三元组，直接添加到 graph_store 中
        for tup in triplets:
            if isinstance(tup, list) and len(tup) == 3:
                # SimpleGraphStore 自己就有 upsert_triplet 方法
                graph_store.upsert_triplet(*tup)
            else:
                logger.warning(f"从 LLM 收到格式不佳的三元组，已跳过: {tup}")

        # 3. 持久化 graph_store (这会将其保存为 JSON 文件)
        graph_store.persist(persist_path=str(graph_file_path.resolve()))
        
        logger.info(f"知识图谱成功保存到: {graph_file_path}")
        
    except Exception as e:
        logger.error(f"LlamaIndex (SimpleGraphStore) 保存图谱失败: {e}", exc_info=True)
        raise RuntimeError(f"Failed to save Knowledge Graph: {e}")

    # --- 6. 在数据库中创建新的子知识库条目 ---
    # (!! 确保这部分代码在 try 块*之后*，并且您已经修复了)
    logger.info(f"正在数据库中创建 L2b 子知识库条目...")
    sub_kb_schema = KnowledgeBaseCreate(
        name=f"{parent_kb.name} - Knowledge Graph",
        description=f"AI-generated Knowledge Graph for {parent_kb.name}. Model: {generation_model.name}",
        parentId=parent_kb.id,
        kb_type="l2b_graph"
    )
    
    new_sub_kb = crud_kb.create_kb(
        db=db,
        kb_in=sub_kb_schema,
        source_file_path=str(graph_file_path.resolve())
    )
    
    if new_sub_kb:
        logger.info(f"将新创建的 L2b KB (ID: {new_sub_kb.id}) 状态设置为 'ready'...")
        new_sub_kb.status = 'ready'
        try:
            db.commit()
            db.refresh(new_sub_kb)
            logger.info(f"L2b KB (ID: {new_sub_kb.id}) 状态成功更新为 'ready'")
        except Exception as commit_err:
            logger.error(f"更新 L2b KB (ID: {new_sub_kb.id}) 状态失败: {commit_err}", exc_info=True)
            db.rollback()
            # 即使更新失败，也继续返回对象，前端会看到 'new' 状态

    logger.info(f"成功创建 L2b 子知识库, ID: {new_sub_kb.id}")
    return new_sub_kb