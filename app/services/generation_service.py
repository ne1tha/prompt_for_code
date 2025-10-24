# app/services/generation_service.py

import aiofiles # (1) 保持 aiofiles，您已安装
from pathlib import Path
import openai
from sqlalchemy.orm import Session # (2) <-- 关键修复：使用同步 Session
from openai import AsyncOpenAI # (3) 保持 AsyncOpenAI
import httpx
from datetime import datetime
from typing import Dict, Any

# 导入数据库模型和 CRUD
import app.crud.crud_knowledgebase as crud_kb
from app.models.knowledgebase import KnowledgeBase as models_kb
from app.models.model import Model as models_model

# 导入 Pydantic 模式
from app.schemas.knowledgebase import KnowledgeBaseCreate

# 导入日志
import logging
logger = logging.getLogger(__name__)


async def generate_summary_pipeline( # (4) 保持 async def
    db: Session, # (5) <-- 关键修复：使用同步 Session
    parent_kb: models_kb,  # (!! 已修复 !!)
    generation_model: models_model # (!! 此次修复 !!) 移除 .Model
) -> models_kb:
    """
    RAG 循环 B (L2a) 核心管道。
    (已更新) 采用“机会主义”逻辑，如果找到 L2b 图谱，将使用它。
    """
    
    logger.info(f"开始为 KB ID: {parent_kb.id} 生成 L2a 摘要...")

    # --- 1. 验证输入 (保持不变) ---
    if not parent_kb.source_file_path:
        raise ValueError("Parent knowledge base has no source file path.")
    if generation_model.model_type != "generative":
        raise ValueError(f"Model '{generation_model.name}' is not a 'generation' model.")
    if not generation_model.endpoint_url:
        raise ValueError(f"Model '{generation_model.name}' missing 'endpoint_url'.")

    source_file_path = Path(parent_kb.source_file_path)
    if not source_file_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_file_path}")

    # --- 2. (新增) “机会主义” L2b 检查 ---
    logger.info(f"[KB {parent_kb.id}] 正在检查是否存在 L2b 知识图谱...")
    knowledge_graph_content = ""
    
    # (6) <-- 关键修复：同步调用新的 CRUD 函数
    l2b_graph_kb = crud_kb.find_child_by_type(
        db=db, 
        parent_id=parent_kb.id, 
        kb_type="l2b_graph"
    )

    if l2b_graph_kb and l2b_graph_kb.source_file_path:
        logger.info(f"[KB {parent_kb.id}] 找到了 L2b 图谱: {l2b_graph_kb.source_file_path}")
        graph_path = Path(l2b_graph_kb.source_file_path)
        if graph_path.exists():
            # (7) 保持 async 读取
            async with aiofiles.open(graph_path, mode='r', encoding='utf-8') as f:
                knowledge_graph_content = await f.read()
    else:
        logger.info(f"[KB {parent_kb.id}] 未找到 L2b 图谱，将生成标准摘要。")

    # --- 3. 读取源文件内容 ---
    logger.info(f"正在读取源文件: {source_file_path}")
    async with aiofiles.open(source_file_path, mode='r', encoding='utf-8') as f:
        code_content = await f.read()

    # --- 4. 准备动态 Prompt ---
    prompt: str
    if knowledge_graph_content:
        # (高级 Prompt)
        prompt = f"""
        您是一位资深软件架构专家。
        
        为了帮助您理解，这里有一份从代码中提取的**关键结构关系知识图谱 (JSON 格式)**：
        [知识图谱]:
        {knowledge_graph_content}

        请**结合**上述的知识图谱和下面的完整源代码，撰写一份简洁的高层次 Markdown 总结。
        总结应描述：
        1.  该文件的主要目的或职责。
        2.  定义的关键类、函数或组件。
        3.  它们之间如何交互（如果适用）。
        请仅返回 Markdown 格式的总结。
            
        ---
        源代码 ({source_file_path.name}):
        ---
        {code_content}
        """
    else:
        # (标准 Prompt - 与您现有的代码相同)
        prompt = f"""
        您是一位资深软件架构专家。您的任务是分析以下源代码，并以 Markdown 格式提供一份简洁的高层次总结。
        总结应描述：
        1.  该文件的主要目的或职责。
        2.  定义的关键类、函数或组件。
        3.  它们之间如何交互（如果适用）。
        请仅返回 Markdown 格式的总结。
        ---
        源代码 ({source_file_path.name}):
        ---
        {code_content}
        """

    # --- 5. 调用 LLM API (保持 async) ---
    logger.info(f"正在调用 LLM: {generation_model.name} at {generation_model.endpoint_url}")
    client = AsyncOpenAI(
        api_key=generation_model.api_key or "DUMMY_KEY",
        base_url=generation_model.endpoint_url
    )
    
    try:
        # (8) 保持 await
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

    # --- 6. 将摘要保存为新文件 (保持 async) ---
    summary_dir = Path("uploads/summaries")
    summary_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    summary_filename = f"{source_file_path.stem}_summary_kb_{parent_kb.id}_{ts}.md"
    summary_file_path = summary_dir / summary_filename
    
    logger.info(f"正在将摘要保存到: {summary_file_path}")
    async with aiofiles.open(summary_file_path, mode='w', encoding='utf-8') as f:
        await f.write(summary_content)

    # --- 7. 在数据库中创建新的子知识库条目 ---
    logger.info(f"正在数据库中创建 L2a 子知识库条目...")
    sub_kb_schema = KnowledgeBaseCreate(
        name=f"{parent_kb.name} - AI Summary",
        description=f"AI-generated summary for {parent_kb.name}. Model: {generation_model.name}",
        parentId=parent_kb.id,
        kb_type="l2a_summary"
    )
    
    # (9) <-- 关键修复：同步调用 CRUD，移除 await
    new_sub_kb = crud_kb.create_kb(
        db=db,
        kb_in=sub_kb_schema,
        source_file_path=str(summary_file_path.resolve())
    )
    
    logger.info(f"成功创建 L2a 子知识库, ID: {new_sub_kb.id}")
    return new_sub_kb