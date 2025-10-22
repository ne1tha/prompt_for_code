from pydantic import BaseModel, ConfigDict
from typing import Optional

class ModelBase(BaseModel):
    name: str
    model_type: str = "generative"
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None  
    
    # (关键修复) 重新添加 dimensions 字段
    dimensions: Optional[int] = None

class ModelCreate(ModelBase):
    pass

class ModelUpdate(BaseModel):
    name: Optional[str] = None
    model_type: Optional[str] = None
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    dimensions: Optional[int] = None # (关键修复)

class Model(ModelBase):
    id: int
    model_config = ConfigDict(from_attributes=True)