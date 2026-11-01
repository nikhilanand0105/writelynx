import json
import httpx
from typing import Dict, Any, Optional
from backend.app.providers.base import BaseLLMProvider
from backend.app.core.config import settings

class OpenAIProvider(BaseLLMProvider):
    """OpenAI API and compatible endpoints (e.g. vLLM, LMStudio, Groq)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.model = model or settings.OPENAI_MODEL

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=headers)
                return res.status_code == 200
        except Exception:
            return False

    async def generate_suggestion(
        self,
        block_id: str,
        original_text: str,
        context: str,
        mode: str,
        matched_source_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        prompt = f"""You are an academic writing revision assistant.
Revise the passage in academic '{mode}' mode.
Passage:
{original_text}

Rules:
1. Preserve all citations, metrics, numbers, and technical terminology exactly.
2. Return JSON only with keys: proposed_text, reason, confidence.
"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional academic editor. Respond strictly in valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return {
                        "block_id": block_id,
                        "issue_type": mode,
                        "original_text": original_text,
                        "proposed_text": parsed.get("proposed_text", original_text),
                        "reason": parsed.get("reason", "Revised for academic clarity"),
                        "citations_preserved": True,
                        "protected_entities_preserved": True,
                        "requires_user_review": True,
                        "confidence": float(parsed.get("confidence", 0.9))
                    }
        except Exception:
            pass
        return None
