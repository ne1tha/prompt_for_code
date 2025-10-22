from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.model import Model, ModelCreate, ModelUpdate
from app.services import model_service
from app.api.endpoints.health import get_db # 重用来自 health.py 的 get_db 依赖项

router = APIRouter()

@router.get(
    "/", 
    response_model=List[Model],
    summary="[modelStore] 获取所有模型"
)
def read_models(db: Session = Depends(get_db)):
    """
    (fetchModels) 检索所有模型。
    对应 modelStore_real.js -> fetchModels()
    """
    return model_service.get_all_models(db)

@router.post(
    "/", 
    response_model=Model, 
    status_code=status.HTTP_201_CREATED,
    summary="[modelStore] 添加一个新模型"
)
def create_model(
    model_in: ModelCreate, 
    db: Session = Depends(get_db)
):
    """
    (addModel) 创建一个新模型。
    对应 modelStore_real.js -> addModel(newModel)
    """
    return model_service.create_new_model(db, model_in=model_in)

@router.put(
    "/{id}", 
    response_model=Model,
    summary="[modelStore] 更新一个模型"
)
def update_model(
    id: int, 
    model_in: ModelUpdate, 
    db: Session = Depends(get_db)
):
    """
    (updateModel) 按 ID 更新现有模型。
    对应 modelStore_real.js -> updateModel(updatedModel)
    """
    updated_model = model_service.update_existing_model(db, model_id=id, model_in=model_in)
    if updated_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return updated_model

@router.delete(
    "/{id}", 
    status_code=status.HTTP_204_NO_CONTENT, # 204: 成功，但无内容返回
    summary="[modelStore] 删除一个模型"
)
def delete_model(
    id: int, 
    db: Session = Depends(get_db)
):
    """
    (deleteModel) 按 ID 删除现有模型。
    对应 modelStore_real.js -> deleteModel(id)
    """
    deleted_model = model_service.delete_existing_model(db, model_id=id)
    if deleted_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 成功删除，返回 204 No Content，前端的 response.ok 将为 true
    return None