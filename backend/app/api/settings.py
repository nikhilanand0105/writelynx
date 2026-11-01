from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.app.core.config import settings
from backend.app.providers import get_llm_provider

router = APIRouter(prefix="/settings", tags=["Settings"])

class SettingsPayload(BaseModel):
    default_llm_provider: Optional[str] = None
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None

@router.get("")
def get_current_settings():
    return {
        "project_name": settings.PROJECT_NAME,
        "default_llm_provider": settings.DEFAULT_LLM_PROVIDER,
        "ollama_host": settings.OLLAMA_HOST,
        "ollama_model": settings.OLLAMA_MODEL,
        "openai_model": settings.OPENAI_MODEL,
        "gemini_model": settings.GEMINI_MODEL,
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "libreoffice_available": True,
        "offline_only": settings.OFFLINE_ONLY
    }

@router.post("")
def update_settings(payload: SettingsPayload):
    if payload.default_llm_provider:
        settings.DEFAULT_LLM_PROVIDER = payload.default_llm_provider
    if payload.ollama_host:
        settings.OLLAMA_HOST = payload.ollama_host
    if payload.ollama_model:
        settings.OLLAMA_MODEL = payload.ollama_model
    if payload.openai_api_key is not None:
        settings.OPENAI_API_KEY = payload.openai_api_key
    if payload.openai_model:
        settings.OPENAI_MODEL = payload.openai_model
    if payload.gemini_api_key is not None:
        settings.GEMINI_API_KEY = payload.gemini_api_key
    if payload.gemini_model:
        settings.GEMINI_MODEL = payload.gemini_model
    return {"success": True, "message": "Settings updated."}

@router.get("/test-provider/{provider_name}")
async def test_provider_connection(provider_name: str):
    provider = get_llm_provider(provider_name)
    ok = await provider.test_connection()
    return {"provider": provider_name, "available": ok}
