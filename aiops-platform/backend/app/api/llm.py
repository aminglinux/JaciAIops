from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin
from app.core.database import User, get_db
from app.services import llm_config_manager

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ProviderPayload(BaseModel):
    name: str
    provider_code: str
    provider_type: str = "openai_compatible"
    base_url: str
    api_key: str
    enabled: bool = True
    extra_config: Dict[str, Any] = Field(default_factory=dict)


class ProviderUpdatePayload(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None
    extra_config: Optional[Dict[str, Any]] = None


class ModelPayload(BaseModel):
    provider_id: int
    model_id: str
    display_name: str
    model_type: str = "chat"
    supports_function_calling: bool = False
    supports_streaming: bool = True
    supports_json_mode: bool = False
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    enabled: bool = True
    is_default_candidate: bool = True
    meta: Dict[str, Any] = Field(default_factory=dict)


class ModelUpdatePayload(BaseModel):
    display_name: Optional[str] = None
    model_type: Optional[str] = None
    supports_function_calling: Optional[bool] = None
    supports_streaming: Optional[bool] = None
    supports_json_mode: Optional[bool] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    enabled: Optional[bool] = None
    is_default_candidate: Optional[bool] = None
    meta: Optional[Dict[str, Any]] = None


class BindingPayload(BaseModel):
    model_id: int
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    enabled: bool = True


class SyncModelsPayload(BaseModel):
    model_ids: Optional[List[str]] = None
    overwrite_existing: bool = False


def _handle_value_error(exc: ValueError):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/providers", response_model=dict)
def list_providers(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"code": 200, "message": "success", "data": llm_config_manager.list_providers(db)}


@router.post("/providers", response_model=dict)
def create_provider(
    payload: ProviderPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        provider = llm_config_manager.create_provider(db, payload.model_dump(), current_user.username)
        return {"code": 200, "message": "创建成功", "data": provider}
    except ValueError as exc:
        _handle_value_error(exc)


@router.put("/providers/{provider_id}", response_model=dict)
def update_provider(
    provider_id: int,
    payload: ProviderUpdatePayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        provider = llm_config_manager.update_provider(
            db,
            provider_id,
            payload.model_dump(exclude_none=True),
            current_user.username,
        )
        return {"code": 200, "message": "更新成功", "data": provider}
    except ValueError as exc:
        _handle_value_error(exc)


@router.delete("/providers/{provider_id}", response_model=dict)
def delete_provider(
    provider_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        llm_config_manager.delete_provider(db, provider_id, current_user.username)
        return {"code": 200, "message": "删除成功", "data": None}
    except ValueError as exc:
        _handle_value_error(exc)


@router.post("/providers/{provider_id}/validate", response_model=dict)
def validate_provider(
    provider_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = llm_config_manager.validate_provider(db, provider_id)
        return {"code": 200, "message": "success", "data": result}
    except ValueError as exc:
        _handle_value_error(exc)


@router.post("/providers/{provider_id}/discover-models", response_model=dict)
def discover_models(
    provider_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = llm_config_manager.discover_models(db, provider_id)
        return {"code": 200, "message": "success", "data": result}
    except ValueError as exc:
        _handle_value_error(exc)


@router.post("/providers/{provider_id}/sync-models", response_model=dict)
def sync_models(
    provider_id: int,
    payload: SyncModelsPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = llm_config_manager.sync_models(
            db,
            provider_id,
            payload.model_ids,
            payload.overwrite_existing,
            current_user.username,
        )
        return {"code": 200, "message": "同步成功", "data": result}
    except ValueError as exc:
        _handle_value_error(exc)


@router.get("/models", response_model=dict)
def list_models(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"code": 200, "message": "success", "data": llm_config_manager.list_models(db)}


@router.post("/models", response_model=dict)
def create_model(
    payload: ModelPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        model = llm_config_manager.create_model(db, payload.model_dump(), current_user.username)
        return {"code": 200, "message": "创建成功", "data": model}
    except ValueError as exc:
        _handle_value_error(exc)


@router.put("/models/{model_id}", response_model=dict)
def update_model(
    model_id: int,
    payload: ModelUpdatePayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        model = llm_config_manager.update_model(
            db,
            model_id,
            payload.model_dump(exclude_none=True),
            current_user.username,
        )
        return {"code": 200, "message": "更新成功", "data": model}
    except ValueError as exc:
        _handle_value_error(exc)


@router.delete("/models/{model_id}", response_model=dict)
def delete_model(
    model_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        llm_config_manager.delete_model(db, model_id, current_user.username)
        return {"code": 200, "message": "删除成功", "data": None}
    except ValueError as exc:
        _handle_value_error(exc)


@router.get("/bindings", response_model=dict)
def list_bindings(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "code": 200,
        "message": "success",
        "data": {
            "scenes": llm_config_manager.get_scene_definitions(),
            "bindings": llm_config_manager.list_bindings(db),
        },
    }


@router.put("/bindings/{scene_key}", response_model=dict)
def update_binding(
    scene_key: str,
    payload: BindingPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        binding = llm_config_manager.update_binding(
            db,
            scene_key,
            payload.model_dump(exclude_none=True),
            current_user.username,
        )
        return {"code": 200, "message": "更新成功", "data": binding}
    except ValueError as exc:
        _handle_value_error(exc)


@router.get("/runtime-config", response_model=dict)
def get_runtime_config(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"code": 200, "message": "success", "data": llm_config_manager.get_runtime_config_summary(db)}

