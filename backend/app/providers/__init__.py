from .base import BaseLLMProvider
from .no_llm_provider import NoLLMProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from backend.app.core.config import settings

def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    name = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower()
    if name == "ollama":
        return OllamaProvider()
    elif name == "openai":
        return OpenAIProvider()
    elif name == "gemini":
        return GeminiProvider()
    elif name == "custom":
        return OpenAIProvider(
            api_key=settings.CUSTOM_API_KEY,
            base_url=settings.CUSTOM_ENDPOINT
        )
    return NoLLMProvider()
