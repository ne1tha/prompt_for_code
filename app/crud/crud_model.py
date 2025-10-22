from sqlalchemy.orm import Session
from app.models.model import Model
from app.schemas.model import ModelCreate, ModelUpdate
from typing import List, Optional

def get_model(db: Session, model_id: int) -> Optional[Model]:
    """ 按 ID 获取单个模型 """
    return db.query(Model).filter(Model.id == model_id).first()

def get_models(db: Session, skip: int = 0, limit: int = 100) -> List[Model]:
    """ 
    (fetchModels) 获取模型列表 
    对应 modelStore_real.js -> fetchModels
    """
    return db.query(Model).offset(skip).limit(limit).all()

def create_model(db: Session, model: ModelCreate) -> Model:
    """ 
    (addModel) 创建一个新模型
    对应 modelStore_real.js -> addModel
    """
    db_model = Model(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model

def update_model(db: Session, db_model: Model, model_in: ModelUpdate) -> Model:
    """
    (updateModel) 更新一个模型
    对应 modelStore_real.js -> updateModel
    """
    # model_dump(exclude_unset=True) 仅包含在 model_in 中显式设置的字段
    update_data = model_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_model, key, value)
    
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model

def delete_model(db: Session, model_id: int) -> Optional[Model]:
    """
    (deleteModel) 删除一个模型
    对应 modelStore_real.js -> deleteModel
    """
    db_model = db.query(Model).filter(Model.id == model_id).first()
    if db_model:
        db.delete(db_model)
        db.commit()
    return db_model