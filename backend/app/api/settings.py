import logging
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from backend.app.core.config import settings
from backend.app.core.auth import require_admin
from backend.app.models.models import User
from backend.app.providers import get_llm_provider

logger = logging.getLogger("writelynx.settings")

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsPayload(BaseModel):
    default_llm_provider: Optional[str] = None
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_model: Optional[str] = None


SAFE_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def validate_safe_endpoint(url_str: str) -> str:
    """SSRF Prevention: Block internal subnet and cloud metadata IP manipulation."""
    parsed = urlparse(url_str)
    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format for model host.",
        )
    # Block cloud metadata addresses and link-local addresses
    if hostname.startswith("169.254.") or hostname.startswith("10.") or hostname.startswith("172.16.") or hostname.startswith("192.168."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forbidden: Host IP belongs to a restricted internal subnet (SSRF protection).",
        )
    return url_str


@router.get("")
def get_current_settings():
    """Public read-only inspection of high-level service configuration. Secrets are strictly omitted."""
    return {
        "project_name": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "default_llm_provider": settings.DEFAULT_LLM_PROVIDER,
        "ollama_model": settings.OLLAMA_MODEL,
        "openai_model": settings.OPENAI_MODEL,
        "gemini_model": settings.GEMINI_MODEL,
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "libreoffice_available": True,
        "offline_only": settings.OFFLINE_ONLY
    }


@router.post("")
def update_settings(
    payload: SettingsPayload,
    admin: User = Depends(require_admin)
):
    """
    Administrative modification of runtime provider settings.
    Requires verified administrator credentials.
    Raw API keys cannot be set via client payload.
    """
    logger.info(f"Admin {admin.email} is updating system settings: {payload.model_dump(exclude_unset=True)}")

    if payload.default_llm_provider:
        if payload.default_llm_provider not in ("no_llm", "ollama", "openai", "gemini"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported LLM provider '{payload.default_llm_provider}'."
            )
        settings.DEFAULT_LLM_PROVIDER = payload.default_llm_provider

    if payload.ollama_host:
        settings.OLLAMA_HOST = validate_safe_endpoint(payload.ollama_host)
    if payload.ollama_model:
        settings.OLLAMA_MODEL = payload.ollama_model
    if payload.openai_model:
        settings.OPENAI_MODEL = payload.openai_model
    if payload.gemini_model:
        settings.GEMINI_MODEL = payload.gemini_model

    return {"success": True, "message": "Settings updated by administrator."}


@router.get("/test-provider/{provider_name}")
async def test_provider_connection(
    provider_name: str,
    admin: User = Depends(require_admin)
):
    """Privileged diagnostic to verify provider health without exposing internal host addresses."""
    provider = get_llm_provider(provider_name)
    ok = await provider.test_connection()
    return {"provider": provider_name, "available": ok}
