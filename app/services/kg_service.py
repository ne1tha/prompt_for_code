# app/services/kg_service.py

import aiofiles
from pathlib import Path
import openai
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
import httpx
from datetime import datetime, timezone
import json
import zipfile  # <-- 1. 新增
import rarfile  # <-- 1. 新增
import shutil   # <-- 1. 新增
import time     # <-- 1. 新增
from typing import List # <-- 1. 新增

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


# <-- 2. 新增辅助函数
def _extract_archive(archive_path: Path, extract_to: Path):
    """ Extracts a ZIP or RAR file. (Copied from ingestion_pipeline) """
    suffix = archive_path.suffix.lower()
    logger.info(f"Attempting to extract '{archive_path}' (format: {suffix}) to '{extract_to}'")

    if suffix == '.zip':
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logger.info(f"Successfully extracted ZIP '{archive_path}'")
        except zipfile.BadZipFile:
            logger.error(f"Error: '{archive_path}' is not a valid zip file or is corrupted.")
            raise ValueError("Invalid or corrupted zip file.")
        except Exception as e:
            logger.error(f"Error extracting zip file '{archive_path}': {e}")
            raise
    
    elif suffix == '.rar':
        try:
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                rar_ref.extractall(extract_to)
            logger.info(f"Successfully extracted RAR '{archive_path}'")
        except rarfile.BadRarFile:
             logger.error(f"Error: '{archive_path}' is not a valid RAR file or is corrupted.")
             raise ValueError("Invalid or corrupted RAR file.")
        except Exception as e:
            logger.error(f"Error extracting RAR file '{archive_path}': {e}")
            raise
    else:
        logger.error(f"Unsupported archive format for extraction: {suffix}")
        raise ValueError(f"Unsupported archive format: {suffix}. Only .zip and .rar are supported.")

# <-- 3. 新增辅助函数
def _find_code_files(directory: Path) -> List[Path]:
    """ 
    Finds all supported code files in a directory, skipping hidden files/dirs.
    (Based on extensions in ingestion_pipeline.py)
    """
    logger.info(f"Scanning for code files in: {directory}")
    supported_exts = [
        '.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.java', 
        '.rs', '.c', '.h', '.cpp', '.hpp', '.cxx', '.hxx',
        '.md', '.markdown', '.mdx'
    ]
    code_files = []
    
    # 使用 rglob 递归查找所有文件
    for f in directory.rglob('*'):
        if f.is_file():
            # 1. 检查后缀
            if f.suffix.lower() in supported_exts:
                # 2. 检查是否在隐藏目录或 venv/node_modules
                parts = f.parts
                is_hidden = any(p.startswith('.') for p in parts)
                is_vendor = any(p in ['venv', 'node_modules', '__pycache__'] for p in parts)
                
                if not is_hidden and not is_vendor:
                    code_files.append(f)
                else:
                    logger.debug(f"Skipping vendor/hidden file: {f}")
                    
    logger.info(f"Found {len(code_files)} processable code files.")
    return code_files


# <-- 4. 重构主函数
async def generate_graph_pipeline( 
    db: Session, 
    parent_kb: models_kb, 
    generation_model: models_model 
) -> models_kb:
    """
    RAG 循环 B (L2b) 的核心管道。
    (已重构为可处理压缩包和目录)
    """
    
    logger.info(f"开始为 KB ID: {parent_kb.id} 生成 L2b 知识图谱...")
    
    temp_extract_dir = None
    all_triplets = [] # 用于收集所有文件的三元组

    try:
        # --- 1. 验证输入 (保持不变) ---
        if not parent_kb.source_file_path:
            raise ValueError("Parent knowledge base has no source file path.")
        if generation_model.model_type != "generative":
            raise ValueError(f"Model '{generation_model.name}' is not a 'generation' model.")
        source_file_path = Path(parent_kb.source_file_path)
        if not source_file_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_file_path}")

        # --- 2. 处理文件/目录输入 (新逻辑) ---
        files_to_process: List[Path] = []
        
        if source_file_path.is_dir():
            logger.info(f"源是目录。正在查找代码文件: {source_file_path}")
            files_to_process = _find_code_files(source_file_path)
        
        elif source_file_path.suffix.lower() in ['.zip', '.rar']:
            logger.info(f"源是压缩包。正在解压: {source_file_path}")
            temp_extract_dir = Path(f"./temp_extract_kg_{parent_kb.id}_{int(time.time())}")
            temp_extract_dir.mkdir(parents=True, exist_ok=True)
            _extract_archive(source_file_path, temp_extract_dir) # 使用辅助函数
            files_to_process = _find_code_files(temp_extract_dir)
            
        elif source_file_path.is_file():
            logger.info(f"源是单个文件: {source_file_path}")
            # 假设单个文件总是我们想要处理的
            files_to_process = [source_file_path]
            
        else:
            raise ValueError(f"Source path is not a file, directory, or supported archive: {source_file_path}")

        if not files_to_process:
            raise ValueError(f"在 {source_file_path} 中未找到可处理的源代码文件。")

        logger.info(f"找到 {len(files_to_process)} 个代码文件进行分析。")

        # --- 3. 初始化 LLM 客户端 (一次性) ---
        client = AsyncOpenAI(
            api_key=generation_model.api_key or "DUMMY_KEY",
            base_url=generation_model.endpoint_url
        )

        # --- 4. 循环、读取并调用 LLM (新逻辑) ---
        for i, file_path in enumerate(files_to_process):
            logger.info(f"正在处理文件 {i+1}/{len(files_to_process)}: {file_path.name}")
            
            code_content = ""
            try:
                # --- 4a. 读取源文件 (async) ---
                async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                    code_content = await f.read()
            except UnicodeDecodeError:
                logger.warning(f"跳过文件 {file_path.name}: 不是有效的 UTF-8 编码。")
                continue # 跳过这个文件，继续下一个
            except Exception as e:
                 logger.warning(f"跳过文件 {file_path.name}: 读取文件时出错: {e}")
                 continue

            if not code_content.strip():
                logger.warning(f"跳过文件 {file_path.name}: 文件为空。")
                continue

            # --- 4b. 准备 Prompt ---
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
            Source Code ({file_path.name}):
            ---
            {code_content}
            """

            # --- 4c. 调用 LLM API (async) ---
            try:
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
                    logger.warning(f"LLM 为 {file_path.name} 返回了空响应")
                    continue
                
                # 清理可能的 markdown 代码块
                if json_response.strip().startswith("```json"):
                    json_response = json_response.strip()[7:-3].strip()
                elif json_response.strip().startswith("```"):
                     json_response = json_response.strip()[3:-3].strip()

                file_triplets = json.loads(json_response)
                
                if isinstance(file_triplets, list):
                    all_triplets.extend(file_triplets) # <-- 添加到总列表
                    logger.info(f"从 {file_path.name} 中提取了 {len(file_triplets)} 个三元组。")
                else:
                     logger.warning(f"LLM 没有为 {file_path.name} 返回有效的列表。已跳过。")

            except (httpx.ConnectError, openai.APIError) as e:
                logger.error(f"对 {file_path.name} 的 API 调用失败: {e}。正在停止管道。")
                raise RuntimeError(f"Failed to call generation API: {str(e)}") # 停止整个过程
            except json.JSONDecodeError as e:
                logger.warning(f"LLM 为 {file_path.name} 返回了无效的 JSON: {e}。响应: {json_response[:100]}... 已跳过此文件。")
                continue # 跳过这个文件
            except Exception as e:
                logger.error(f"对 {file_path.name} 的 LLM 调用失败: {e}。已跳过此文件。")
                continue # 跳过这个文件
        
        # --- 循环结束 ---

        if not all_triplets:
            raise ValueError("未能从任何文件中提取三元组。无法构建图谱。")
        
        logger.info(f"从所有文件中共提取了 {len(all_triplets)} 个三元组。")

        # --- 5. 构建图谱并持久化为 JSON (使用 all_triplets) ---
        graph_dir = Path("uploads/graphs")
        graph_dir.mkdir(parents=True, exist_ok=True) 
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        
        # 使用原始文件名（可能是压缩包名）作为图谱名
        graph_filename = f"{source_file_path.stem}_graph_kb_{parent_kb.id}_{ts}.json"
        graph_file_path = graph_dir / graph_filename
        
        try:
            graph_store = SimpleGraphStore()
            
            # 遍历合并后的总列表
            for tup in all_triplets:
                if isinstance(tup, list) and len(tup) == 3:
                    graph_store.upsert_triplet(*tup)
                else:
                    logger.warning(f"从 LLM 收到格式不佳的三元组，已跳过: {tup}")

            graph_store.persist(persist_path=str(graph_file_path.resolve()))
            
            logger.info(f"知识图谱成功保存到: {graph_file_path}")
            
        except Exception as e:
            logger.error(f"LlamaIndex (SimpleGraphStore) 保存图谱失败: {e}", exc_info=True)
            raise RuntimeError(f"Failed to save Knowledge Graph: {e}")

        # --- 6. 在数据库中创建新的子知识库条目 (保持不变) ---
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

        logger.info(f"成功创建 L2b 子知识库, ID: {new_sub_kb.id}")
        return new_sub_kb

    finally:
        # --- 7. 清理 (新增) ---
        if temp_extract_dir:
            try:
                shutil.rmtree(temp_extract_dir)
                logger.info(f"已清理临时 KG 目录: {temp_extract_dir}")
            except Exception as e:
                logger.error(f"清理临时 KG 目录 '{temp_extract_dir}' 失败: {e}")
