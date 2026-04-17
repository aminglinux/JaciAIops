from openai import OpenAI
from app.core.config import settings


class LLMClientFactory:
    def create_openai_compatible(self, api_key: str, base_url: str) -> OpenAI:
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=max(5, int(settings.OPENAI_TIMEOUT_SECONDS)),
            max_retries=max(0, int(settings.OPENAI_MAX_RETRIES)),
        )

    def create_client(self, provider_type: str, api_key: str, base_url: str):
        if provider_type in {"openai_compatible", "azure_openai"}:
            return self.create_openai_compatible(api_key=api_key, base_url=base_url)
        raise ValueError(f"暂不支持的 provider_type: {provider_type}")


llm_client_factory = LLMClientFactory()
