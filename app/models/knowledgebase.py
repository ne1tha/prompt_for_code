from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime, timezone
from sqlalchemy.sql import func


class KnowledgeBase(Base):
    """
    SQLAlchemy 模型，定义 'knowledgebases' 表。
    这是系统的核心元数据表。
    """
    __tablename__ = "knowledgebases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="new")
    parsing_state = Column(JSON, nullable=True)
    source_file_path = Column(String, nullable=True)
    
    updated_at = Column(
        DateTime(timezone=True),  # 推荐使用带时区的 DateTime
        nullable=False,
        server_default=func.now(), # 使用数据库的 NOW() 函数作为默认值
        onupdate=func.now()        # 每次更新时，使用数据库的 NOW() 函数
    )
    
    # (关键修复 1)
    # 添加 parentId 字段，它是一个外键，指向 'knowledgebases' 表自己的 'id' 列
    parentId = Column(Integer, ForeignKey("knowledgebases.id"), nullable=True)
    
    embedding_model_id = Column(Integer, ForeignKey("models.id"), nullable=True)
    
    # (可选但推荐) 定义关系
    embedding_model = relationship("Model")
    
    # (可选但推荐) 建立父子关系
    # 'remote_side=[id]' 告诉 SQLAlchemy parentId 引用的是本表的 id 列
    parent = relationship("KnowledgeBase", remote_side=[id], back_populates="children")
    children = relationship("KnowledgeBase", back_populates="parent")
    kb_type = Column(String, nullable=False, default="primary")