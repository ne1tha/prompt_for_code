# app/schemas/knowledgebase.py

from pydantic import BaseModel, ConfigDict, Field # (您已导入 Field)
from typing import Optional, Any, Dict
from datetime import datetime


# --- 基础模式 ---
class KnowledgeBaseBase(BaseModel):
    name: str
    description: Optional[str] = None
    parentId: Optional[int] = None # (1) 保持您定义的 parentId 不变

    # (2) --- 新增字段 ---
    # 这对应 models.knowledgebase.py 中的 kb_type (snake_case) 字段
    # 我们使用 Field 来添加 camelCase 序列化别名，
    # 就像您为 parsingState 和 sourceFilePath 所做的那样
    kb_type: Optional[str] = Field(
        default="primary", 
        serialization_alias="kbType" # JSON 输出为 kbType
    )


# --- API Payloads ---
# (保持不变)
class KnowledgeBaseCreate(KnowledgeBaseBase): pass
class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parentId: Optional[int] = None
class StartParsingRequest(BaseModel):
    embedding_model_id: int


# --- API 响应 ---
class KnowledgeBase(KnowledgeBaseBase): # 继承 name, description, parentId, 和 kb_type
    id: int
    status: str
    
    updated_at: Optional[datetime] = Field(
        default=None,
        serialization_alias='updatedAt'
    )
    parsing_state: Optional[Dict[str, Any]] = Field(
        default=None, 
        serialization_alias='parsingState'
    ) 
    source_file_path: Optional[str] = Field(
        default=None, 
        serialization_alias='sourceFilePath'
    )

    model_config = ConfigDict(
        from_attributes=True, 
        populate_by_name=True 
    )



# (!! 在文件末尾添加这个新类 !!)
class GenerateSummaryRequest(BaseModel):
    """
    POST /{id}/generate-summary 的请求体
    """
    # (1) 指定用哪个 LLM 来 *生成* 摘要
    generation_model_id: int
    
    # (2) 指定用哪个模型来 *向量化* 新生成的摘要
    embedding_model_id: int
    
    
class GenerateGraphRequest(BaseModel):
    """
    POST /{id}/generate-graph 的请求体
    """
    generation_model_id: int