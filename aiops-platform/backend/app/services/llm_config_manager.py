import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import (
    AuditLog,
    LLMModel,
    LLMProvider,
    LLMSceneBinding,
    SessionLocal,
)
from .llm_client_factory import llm_client_factory


DEFAULT_SCENES: List[Dict[str, Any]] = [
    {"scene_key": "intent_parse", "display_name": "意图识别", "temperature": 0.1, "supports_function_calling": False},
    {"scene_key": "master_planner", "display_name": "主控规划", "temperature": 0.2, "supports_function_calling": True},
    {"scene_key": "knowledge_analysis", "display_name": "知识分析", "temperature": 0.3, "supports_function_calling": False},
    {"scene_key": "observability_summary", "display_name": "可观测性分析", "temperature": 0.2, "supports_function_calling": False},
    {"scene_key": "action_execute", "display_name": "执行方案生成", "temperature": 0.1, "supports_function_calling": False},
    {"scene_key": "general_chat", "display_name": "通用问答", "temperature": 0.2, "supports_function_calling": False},
]


@dataclass
class ResolvedLLMConfig:
    scene_key: str
    provider_name: str
    provider_type: str
    base_url: str
    api_key: str
    model: str
    temperature: float
    max_tokens: Optional[int]
    top_p: Optional[float]
    supports_function_calling: bool
    source: str


class LLMConfigManager:
    def _get_fernet(self) -> Fernet:
        seed = settings.SECRET_KEY or "aiops-platform-dev-secret"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def encrypt_api_key(self, raw_value: str) -> str:
        return self._get_fernet().encrypt(raw_value.encode("utf-8")).decode("utf-8")

    def decrypt_api_key(self, encrypted_value: str) -> str:
        try:
            return self._get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return encrypted_value

    def mask_api_key(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * max(4, len(value) - 8)}{value[-4:]}"

    def get_scene_definitions(self) -> List[Dict[str, Any]]:
        return DEFAULT_SCENES

    def bootstrap_defaults(self):
        db = SessionLocal()
        try:
            provider = db.query(LLMProvider).filter(LLMProvider.provider_code == "default_env_provider").first()
            if provider is None and settings.OPENAI_API_KEY:
                provider = LLMProvider(
                    name="Default Environment Provider",
                    provider_code="default_env_provider",
                    provider_type="openai_compatible",
                    base_url=settings.OPENAI_BASE_URL,
                    api_key_encrypted=self.encrypt_api_key(settings.OPENAI_API_KEY),
                    api_key_masked=self.mask_api_key(settings.OPENAI_API_KEY),
                    enabled=True,
                    is_builtin=True,
                    extra_config_json=json.dumps({"source": "env"}, ensure_ascii=False),
                )
                db.add(provider)
                db.flush()

            model = None
            if provider is not None:
                model = (
                    db.query(LLMModel)
                    .filter(LLMModel.provider_id == provider.id, LLMModel.model_id == settings.OPENAI_MODEL)
                    .first()
                )
                if model is None:
                    model = LLMModel(
                        provider_id=provider.id,
                        model_id=settings.OPENAI_MODEL,
                        display_name=settings.OPENAI_MODEL,
                        model_type="chat",
                        supports_function_calling=True,
                        supports_streaming=True,
                        supports_json_mode=True,
                        enabled=True,
                        is_default_candidate=True,
                        meta_json=json.dumps({"source": "env"}, ensure_ascii=False),
                    )
                    db.add(model)
                    db.flush()

            if model is not None:
                for scene in DEFAULT_SCENES:
                    binding = (
                        db.query(LLMSceneBinding)
                        .filter(LLMSceneBinding.scene_key == scene["scene_key"])
                        .first()
                    )
                    if binding is None:
                        db.add(
                            LLMSceneBinding(
                                scene_key=scene["scene_key"],
                                model_id=model.id,
                                temperature=scene["temperature"],
                                enabled=True,
                                updated_by="system",
                            )
                        )

            db.commit()
        finally:
            db.close()

    def resolve_scene(self, scene_key: str, db: Optional[Session] = None) -> ResolvedLLMConfig:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            binding = db.query(LLMSceneBinding).filter(
                LLMSceneBinding.scene_key == scene_key,
                LLMSceneBinding.enabled.is_(True),
            ).first()
            if binding:
                model = db.query(LLMModel).filter(LLMModel.id == binding.model_id, LLMModel.enabled.is_(True)).first()
                if model:
                    provider = db.query(LLMProvider).filter(
                        LLMProvider.id == model.provider_id,
                        LLMProvider.enabled.is_(True),
                    ).first()
                    if provider:
                        return ResolvedLLMConfig(
                            scene_key=scene_key,
                            provider_name=provider.name,
                            provider_type=provider.provider_type,
                            base_url=provider.base_url,
                            api_key=self.decrypt_api_key(provider.api_key_encrypted),
                            model=model.model_id,
                            temperature=binding.temperature if binding.temperature is not None else 0.2,
                            max_tokens=binding.max_tokens,
                            top_p=binding.top_p,
                            supports_function_calling=model.supports_function_calling,
                            source="database",
                        )

            return ResolvedLLMConfig(
                scene_key=scene_key,
                provider_name="Environment Fallback",
                provider_type="openai_compatible",
                base_url=settings.OPENAI_BASE_URL,
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
                temperature=0.2,
                max_tokens=None,
                top_p=None,
                supports_function_calling=True,
                source="env",
            )
        finally:
            if close_db:
                db.close()

    def get_client_for_scene(self, scene_key: str, db: Optional[Session] = None):
        resolved = self.resolve_scene(scene_key, db=db)
        client = llm_client_factory.create_client(
            provider_type=resolved.provider_type,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )
        return client, resolved

    def get_runtime_config_summary(self, db: Session) -> Dict[str, Any]:
        bindings = []
        for scene in DEFAULT_SCENES:
            resolved = self.resolve_scene(scene["scene_key"], db=db)
            bindings.append(
                {
                    "sceneKey": scene["scene_key"],
                    "displayName": scene["display_name"],
                    "providerName": resolved.provider_name,
                    "model": resolved.model,
                    "source": resolved.source,
                    "temperature": resolved.temperature,
                    "supportsFunctionCalling": resolved.supports_function_calling,
                }
            )
        return {
            "bindings": bindings,
            "fallback": {
                "baseUrl": settings.OPENAI_BASE_URL,
                "model": settings.OPENAI_MODEL,
            },
        }

    def _serialize_provider(self, provider: LLMProvider) -> Dict[str, Any]:
        return {
            "id": provider.id,
            "name": provider.name,
            "providerCode": provider.provider_code,
            "providerType": provider.provider_type,
            "baseUrl": provider.base_url,
            "apiKeyMasked": provider.api_key_masked,
            "enabled": provider.enabled,
            "isBuiltin": provider.is_builtin,
            "extraConfig": json.loads(provider.extra_config_json or "{}"),
            "createdAt": provider.created_at.isoformat() if provider.created_at else None,
            "updatedAt": provider.updated_at.isoformat() if provider.updated_at else None,
        }

    def _serialize_model(self, model: LLMModel, provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
        provider_obj = provider or model.provider
        return {
            "id": model.id,
            "providerId": model.provider_id,
            "providerName": provider_obj.name if provider_obj else "",
            "modelId": model.model_id,
            "displayName": model.display_name,
            "modelType": model.model_type,
            "supportsFunctionCalling": model.supports_function_calling,
            "supportsStreaming": model.supports_streaming,
            "supportsJsonMode": model.supports_json_mode,
            "contextWindow": model.context_window,
            "maxOutputTokens": model.max_output_tokens,
            "enabled": model.enabled,
            "isDefaultCandidate": model.is_default_candidate,
            "meta": json.loads(model.meta_json or "{}"),
            "createdAt": model.created_at.isoformat() if model.created_at else None,
            "updatedAt": model.updated_at.isoformat() if model.updated_at else None,
        }

    def list_providers(self, db: Session) -> List[Dict[str, Any]]:
        providers = db.query(LLMProvider).order_by(LLMProvider.id.desc()).all()
        return [self._serialize_provider(provider) for provider in providers]

    def list_models(self, db: Session) -> List[Dict[str, Any]]:
        models = db.query(LLMModel).order_by(LLMModel.id.desc()).all()
        providers = {provider.id: provider for provider in db.query(LLMProvider).all()}
        return [self._serialize_model(model, providers.get(model.provider_id)) for model in models]

    def list_bindings(self, db: Session) -> List[Dict[str, Any]]:
        results = []
        for scene in DEFAULT_SCENES:
            binding = db.query(LLMSceneBinding).filter(LLMSceneBinding.scene_key == scene["scene_key"]).first()
            model = db.query(LLMModel).filter(LLMModel.id == binding.model_id).first() if binding else None
            provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first() if model else None
            results.append(
                {
                    "sceneKey": scene["scene_key"],
                    "displayName": scene["display_name"],
                    "temperature": binding.temperature if binding else scene["temperature"],
                    "maxTokens": binding.max_tokens if binding else None,
                    "topP": binding.top_p if binding else None,
                    "enabled": binding.enabled if binding else False,
                    "modelId": model.id if model else None,
                    "modelName": model.display_name if model else settings.OPENAI_MODEL,
                    "providerId": provider.id if provider else None,
                    "providerName": provider.name if provider else "Environment Fallback",
                    "supportsFunctionCalling": model.supports_function_calling if model else True,
                    "source": "database" if binding and model and provider else "env",
                }
            )
        return results

    def create_provider(self, db: Session, payload: Dict[str, Any], operator: str) -> Dict[str, Any]:
        provider = LLMProvider(
            name=payload["name"],
            provider_code=payload["provider_code"],
            provider_type=payload.get("provider_type", "openai_compatible"),
            base_url=payload["base_url"],
            api_key_encrypted=self.encrypt_api_key(payload["api_key"]),
            api_key_masked=self.mask_api_key(payload["api_key"]),
            enabled=payload.get("enabled", True),
            is_builtin=payload.get("is_builtin", False),
            extra_config_json=json.dumps(payload.get("extra_config", {}), ensure_ascii=False),
        )
        db.add(provider)
        db.flush()
        self._write_audit_log(db, operator, "create_provider", "provider", str(provider.id), payload)
        db.commit()
        db.refresh(provider)
        return self._serialize_provider(provider)

    def update_provider(self, db: Session, provider_id: int, payload: Dict[str, Any], operator: str) -> Dict[str, Any]:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if provider is None:
            raise ValueError("Provider 不存在")
        provider.name = payload.get("name", provider.name)
        provider.provider_type = payload.get("provider_type", provider.provider_type)
        provider.base_url = payload.get("base_url", provider.base_url)
        provider.enabled = payload.get("enabled", provider.enabled)
        provider.extra_config_json = json.dumps(payload.get("extra_config", json.loads(provider.extra_config_json or "{}")), ensure_ascii=False)
        api_key = payload.get("api_key")
        if api_key:
            provider.api_key_encrypted = self.encrypt_api_key(api_key)
            provider.api_key_masked = self.mask_api_key(api_key)
        self._write_audit_log(db, operator, "update_provider", "provider", str(provider.id), payload)
        db.commit()
        db.refresh(provider)
        return self._serialize_provider(provider)

    def delete_provider(self, db: Session, provider_id: int, operator: str):
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if provider is None:
            raise ValueError("Provider 不存在")
        if provider.is_builtin:
            raise ValueError("内置 Provider 不允许删除")
        self._write_audit_log(db, operator, "delete_provider", "provider", str(provider.id), {"name": provider.name})
        db.delete(provider)
        db.commit()

    def create_model(self, db: Session, payload: Dict[str, Any], operator: str) -> Dict[str, Any]:
        provider = db.query(LLMProvider).filter(LLMProvider.id == payload["provider_id"]).first()
        if provider is None:
            raise ValueError("Provider 不存在")
        model = LLMModel(
            provider_id=payload["provider_id"],
            model_id=payload["model_id"],
            display_name=payload["display_name"],
            model_type=payload.get("model_type", "chat"),
            supports_function_calling=payload.get("supports_function_calling", False),
            supports_streaming=payload.get("supports_streaming", True),
            supports_json_mode=payload.get("supports_json_mode", False),
            context_window=payload.get("context_window"),
            max_output_tokens=payload.get("max_output_tokens"),
            enabled=payload.get("enabled", True),
            is_default_candidate=payload.get("is_default_candidate", True),
            meta_json=json.dumps(payload.get("meta", {}), ensure_ascii=False),
        )
        db.add(model)
        db.flush()
        self._write_audit_log(db, operator, "create_model", "model", str(model.id), payload)
        db.commit()
        db.refresh(model)
        return self._serialize_model(model, provider)

    def update_model(self, db: Session, model_id: int, payload: Dict[str, Any], operator: str) -> Dict[str, Any]:
        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if model is None:
            raise ValueError("Model 不存在")
        for field, attr in {
            "display_name": "display_name",
            "model_type": "model_type",
            "supports_function_calling": "supports_function_calling",
            "supports_streaming": "supports_streaming",
            "supports_json_mode": "supports_json_mode",
            "context_window": "context_window",
            "max_output_tokens": "max_output_tokens",
            "enabled": "enabled",
            "is_default_candidate": "is_default_candidate",
        }.items():
            if field in payload:
                setattr(model, attr, payload[field])
        if "meta" in payload:
            model.meta_json = json.dumps(payload["meta"], ensure_ascii=False)
        self._write_audit_log(db, operator, "update_model", "model", str(model.id), payload)
        db.commit()
        db.refresh(model)
        provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
        return self._serialize_model(model, provider)

    def delete_model(self, db: Session, model_id: int, operator: str):
        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if model is None:
            raise ValueError("Model 不存在")
        in_use = db.query(LLMSceneBinding).filter(LLMSceneBinding.model_id == model.id).first()
        if in_use:
            raise ValueError("当前模型已被场景绑定，无法删除")
        self._write_audit_log(db, operator, "delete_model", "model", str(model.id), {"display_name": model.display_name})
        db.delete(model)
        db.commit()

    def update_binding(self, db: Session, scene_key: str, payload: Dict[str, Any], operator: str) -> Dict[str, Any]:
        if scene_key not in {scene["scene_key"] for scene in DEFAULT_SCENES}:
            raise ValueError("未知的场景")
        model = db.query(LLMModel).filter(LLMModel.id == payload["model_id"], LLMModel.enabled.is_(True)).first()
        if model is None:
            raise ValueError("Model 不存在或未启用")
        provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id, LLMProvider.enabled.is_(True)).first()
        if provider is None:
            raise ValueError("Provider 不存在或未启用")

        binding = db.query(LLMSceneBinding).filter(LLMSceneBinding.scene_key == scene_key).first()
        if binding is None:
            binding = LLMSceneBinding(scene_key=scene_key, model_id=model.id)
            db.add(binding)

        binding.model_id = model.id
        binding.temperature = payload.get("temperature", binding.temperature if binding.temperature is not None else 0.2)
        binding.max_tokens = payload.get("max_tokens")
        binding.top_p = payload.get("top_p")
        binding.enabled = payload.get("enabled", True)
        binding.updated_by = operator

        self._write_audit_log(db, operator, "update_binding", "binding", scene_key, payload)
        db.commit()
        db.refresh(binding)

        scene_info = next(scene for scene in DEFAULT_SCENES if scene["scene_key"] == scene_key)
        return {
            "sceneKey": scene_key,
            "displayName": scene_info["display_name"],
            "temperature": binding.temperature,
            "maxTokens": binding.max_tokens,
            "topP": binding.top_p,
            "enabled": binding.enabled,
            "modelId": model.id,
            "modelName": model.display_name,
            "providerId": provider.id,
            "providerName": provider.name,
            "supportsFunctionCalling": model.supports_function_calling,
            "source": "database",
        }

    def validate_provider(self, db: Session, provider_id: int) -> Dict[str, Any]:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if provider is None:
            raise ValueError("Provider 不存在")
        client = llm_client_factory.create_client(
            provider_type=provider.provider_type,
            api_key=self.decrypt_api_key(provider.api_key_encrypted),
            base_url=provider.base_url,
        )
        try:
            models_response = client.models.list()
            model_names = [item.id for item in getattr(models_response, "data", [])[:10]]
            return {
                "success": True,
                "message": "连接测试成功",
                "detectedCapabilities": {
                    "providerType": provider.provider_type,
                    "models": model_names,
                },
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"连接测试失败: {exc}",
                "detectedCapabilities": {
                    "providerType": provider.provider_type,
                    "models": [],
                },
            }

    def discover_models(self, db: Session, provider_id: int) -> Dict[str, Any]:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if provider is None:
            raise ValueError("Provider 不存在")

        client = llm_client_factory.create_client(
            provider_type=provider.provider_type,
            api_key=self.decrypt_api_key(provider.api_key_encrypted),
            base_url=provider.base_url,
        )

        try:
            models_response = client.models.list()
            remote_models = []
            existing = {
                model.model_id: model
                for model in db.query(LLMModel).filter(LLMModel.provider_id == provider.id).all()
            }

            for item in getattr(models_response, "data", []):
                model_id = getattr(item, "id", "")
                if not model_id:
                    continue
                existing_model = existing.get(model_id)
                remote_models.append(
                    {
                        "modelId": model_id,
                        "displayName": existing_model.display_name if existing_model else model_id,
                        "alreadyImported": existing_model is not None,
                        "enabled": existing_model.enabled if existing_model else True,
                        "supportsFunctionCalling": existing_model.supports_function_calling if existing_model else False,
                        "supportsStreaming": existing_model.supports_streaming if existing_model else True,
                        "supportsJsonMode": existing_model.supports_json_mode if existing_model else False,
                        "modelType": existing_model.model_type if existing_model else "chat",
                    }
                )

            return {
                "providerId": provider.id,
                "providerName": provider.name,
                "models": remote_models,
            }
        except Exception as exc:
            raise ValueError(f"拉取模型列表失败: {exc}") from exc

    def sync_models(
        self,
        db: Session,
        provider_id: int,
        model_ids: Optional[List[str]],
        overwrite_existing: bool,
        operator: str,
    ) -> Dict[str, Any]:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if provider is None:
            raise ValueError("Provider 不存在")

        discovered = self.discover_models(db, provider_id)
        discovered_models = discovered["models"]
        if model_ids:
            selected_ids = set(model_ids)
            discovered_models = [item for item in discovered_models if item["modelId"] in selected_ids]

        existing = {
            model.model_id: model
            for model in db.query(LLMModel).filter(LLMModel.provider_id == provider.id).all()
        }

        created = 0
        updated = 0
        skipped = 0

        for item in discovered_models:
            model = existing.get(item["modelId"])
            if model is None:
                db.add(
                    LLMModel(
                        provider_id=provider.id,
                        model_id=item["modelId"],
                        display_name=item["displayName"],
                        model_type=item["modelType"],
                        supports_function_calling=item["supportsFunctionCalling"],
                        supports_streaming=item["supportsStreaming"],
                        supports_json_mode=item["supportsJsonMode"],
                        enabled=item["enabled"],
                        is_default_candidate=item["modelType"] == "chat",
                        meta_json=json.dumps({"source": "provider_discovery"}, ensure_ascii=False),
                    )
                )
                created += 1
                continue

            if overwrite_existing:
                model.display_name = item["displayName"]
                model.model_type = item["modelType"]
                model.supports_function_calling = item["supportsFunctionCalling"]
                model.supports_streaming = item["supportsStreaming"]
                model.supports_json_mode = item["supportsJsonMode"]
                model.enabled = item["enabled"]
                updated += 1
            else:
                skipped += 1

        self._write_audit_log(
            db,
            operator,
            "sync_models",
            "provider",
            str(provider.id),
            {
                "model_ids": model_ids or [],
                "overwrite_existing": overwrite_existing,
                "created": created,
                "updated": updated,
                "skipped": skipped,
            },
        )
        db.commit()

        return {
            "providerId": provider.id,
            "providerName": provider.name,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "totalSelected": len(discovered_models),
        }

    def _write_audit_log(self, db: Session, operator: str, action: str, target_type: str, target_id: str, detail: Dict[str, Any]):
        db.add(
            AuditLog(
                operator=operator,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail_json=json.dumps(detail, ensure_ascii=False),
            )
        )


llm_config_manager = LLMConfigManager()
