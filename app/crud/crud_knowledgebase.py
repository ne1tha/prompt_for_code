from sqlalchemy.orm import Session
from app.models.knowledgebase import KnowledgeBase
from app.schemas.knowledgebase import KnowledgeBaseCreate, KnowledgeBaseUpdate
from typing import List, Optional

def get_kb(db: Session, kb_id: int) -> Optional[KnowledgeBase]:
    """ (GET /{id}) 获取单个 KB，用于轮询 """
    # (修正) 使用 expire_on_commit=False 来确保在
    # 其他函数中 commit 后对象仍然可用，
    # 或者我们每次都从 session 中重新获取。
    # 
    # (更简单的修复) 保持原样，但在 service 层中刷新(refresh)。
    return db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

def get_kbs(db: Session, skip: int = 0, limit: int = 100) -> List[KnowledgeBase]:
    """ (GET /) 获取所有 KB 列表 """
    return db.query(KnowledgeBase).offset(skip).limit(limit).all()

def create_kb(db: Session, kb_in: KnowledgeBaseCreate) -> KnowledgeBase:
    """
    创建知识库，确保创建时设置更新时间戳
    """
    from datetime import datetime, timezone
    from sqlalchemy.sql import func
    
    # 创建字典数据，包含更新时间
    db_kb_data = kb_in.model_dump()
    db_kb_data["updated_at"] = datetime.now(timezone.utc)  # 设置创建时的时间戳
    
    db_kb = KnowledgeBase(**db_kb_data)
    db.add(db_kb)
    db.commit()
    db.refresh(db_kb)
    return db_kb

def update_kb(db: Session, db_kb: KnowledgeBase, kb_in: KnowledgeBaseUpdate) -> KnowledgeBase:
    """
    更新知识库，确保更新时间被正确设置
    """
    update_data = kb_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_kb, field, value)
    
    # 手动设置更新时间
    from datetime import datetime, timezone
    # from sqlalchemy.sql import func
    # db_kb.updated_at = datetime.now(timezone.utc)
    
    db.add(db_kb)
    db.commit()
    db.refresh(db_kb)
    return db_kb

def delete_kb(db: Session, kb_id: int) -> Optional[KnowledgeBase]:
    """ (DELETE /{id}) 删除 KB """
    db_kb = get_kb(db, kb_id)
    if db_kb:
        db.delete(db_kb)
        db.commit()
    return db_kb