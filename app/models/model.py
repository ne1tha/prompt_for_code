from sqlalchemy import Column, Integer, String
from app.db.session import Base


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    
    model_type = Column(String, nullable=False, default="generative")
    api_key = Column(String, nullable=True)     
    endpoint_url = Column(String, nullable=True)  
    
    # (关键修复) 重新添加 dimensions 字段
    dimensions = Column(Integer, nullable=True) # 例如: 384, 768, 1536