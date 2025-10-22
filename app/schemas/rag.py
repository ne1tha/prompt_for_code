# app/schemas/rag.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class RagQueryRequest(BaseModel):
    """
    RAG 查询请求体
    """
    query: str
    knowledgebase_ids: List[int]
    model_id: int # 用于生成答案的 Generative Model ID
    top_k: int = 3

class RagRetrieveRequest(BaseModel):
    """
    RAG 纯检索请求体
    """
    query: str
    knowledgebase_ids: List[int]
    top_k: int = 3

class RetrievedContext(BaseModel):
    """
    (用于响应) 单个检索到的上下文
    """
    source_kb_id: int
    file_path: str
    text: str
    score: float

class RagQueryResponse(BaseModel):
    """
    RAG 查询响应体
    """
    answer: str # LLM 生成的最终答案
    retrieved_contexts: List[RetrievedContext] # 检索到的上下文，用于调试或前端显示

class RagRetrieveResponse(BaseModel):
    """
    RAG 纯检索响应体
    """
    enhanced_prompt: str # 增强后的提示词（包含检索到的上下文）
    retrieved_contexts: List[RetrievedContext] # 检索到的上下文
    metaprompt: Optional[str] = None # 完整的元提示词，用于调试