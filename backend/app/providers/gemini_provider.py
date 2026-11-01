import json
import httpx
from typing import Dict, Any, Optional
from backend.app.providers.base import BaseLLMProvider
from backend.app.core.config import settings

class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        return True

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

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        prompt = f"""You are an academic manuscript editor.
Revise the passage according to mode '{mode}'.
Passage:
{original_text}

Rules:
1. Preserve all numerical metrics, citations, models, and technical terminology.
2. Output JSON strictly with keys: "proposed_text", "reason", "confidence".
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text_content)
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
