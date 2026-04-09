import hashlib
import json
import time
import threading
from typing import Any, Dict, Optional


class LLMCache:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._cache: Dict[str, Dict[str, Any]] = {}
                cls._instance._default_ttl = 300
        return cls._instance

    def _make_key(self, model: str, messages: str, temperature: float) -> str:
        raw = f"{model}:{messages}:{temperature}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, model: str, messages: str, temperature: float) -> Optional[Any]:
        key = self._make_key(model, messages, temperature)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            return None
        return entry["result"]

    def set(self, model: str, messages: str, temperature: float, result: Any, ttl: int = None):
        key = self._make_key(model, messages, temperature)
        self._cache[key] = {
            "result": result,
            "expires_at": time.time() + (ttl or self._default_ttl),
        }

    def clear(self):
        self._cache.clear()

    def cleanup_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v["expires_at"]]
        for k in expired_keys:
            del self._cache[k]

    @property
    def size(self) -> int:
        return len(self._cache)


llm_cache = LLMCache()
