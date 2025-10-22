from pydantic import BaseModel, ConfigDict, Field # (新增) 导入 Field
from typing import Optional, Any, Dict
from datetime import datetime


# --- 基础模式 ---
class KnowledgeBaseBase(BaseModel):
    name: str
    description: Optional[str] = None
    parentId: Optional[int] = None

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
class KnowledgeBase(KnowledgeBaseBase): # 继承 name, description, parentId
    id: int
    status: str
    
    updated_at: Optional[datetime] = Field(
        default=None,
        serialization_alias='updatedAt'
    )
    # (关键修复) 使用 Field 和 serialization_alias
    parsing_state: Optional[Dict[str, Any]] = Field(
        default=None, 
        serialization_alias='parsingState' # 指定 JSON 输出名为 parsingState
    ) 
    source_file_path: Optional[str] = Field(
        default=None, 
        serialization_alias='sourceFilePath' # 指定 JSON 输出名为 sourceFilePath
    )

    model_config = ConfigDict(
        from_attributes=True, 
        # (关键修复) 移除 alias_generator，因为它现在由 Field 处理
        # alias_generator=lambda x: { ... }.get(x, x) # <-- 删除或注释掉
        
        # (可选但推荐) 确保 Pydantic 知道别名用于输出
        populate_by_name=True # 允许按别名或字段名填充 (虽然我们主要关心序列化)
    )