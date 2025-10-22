from sqlalchemy.orm import Session
from app.crud import crud_model
from app.schemas.model import ModelCreate, ModelUpdate
from typing import List, Optional

# 此服务层在 API 和 CRUD 之间进行调解
#

def get_all_models(db: Session) -> List[crud_model.Model]:
    return crud_model.get_models(db)

def create_new_model(db: Session, model_in: ModelCreate) -> crud_model.Model:
    # (未来) 可以在这里添加业务逻辑，例如：
    # - 检查 model_uri 是否已经存在
    # - 验证 model_uri 是否可以访问
    return crud_model.create_model(db, model=model_in)

def update_existing_model(db: Session, model_id: int, model_in: ModelUpdate) -> Optional[crud_model.Model]:
    db_model = crud_model.get_model(db, model_id=model_id)
    if not db_model:
        return None # 在 API 层将转换为 404
    return crud_model.update_model(db, db_model=db_model, model_in=model_in)

def delete_existing_model(db: Session, model_id: int) -> Optional[crud_model.Model]:
    db_model = crud_model.delete_model(db, model_id=model_id)
    if not db_model:
        return None # 在 API 层将转换为 404
    return db_model