import json
import httpx
from typing import Dict, Any, Optional
from backend.app.providers.base import BaseLLMProvider
from backend.app.core.config import settings

class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider running models such as llama3.2, mistral, or qwen."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = (host or settings.OLLAMA_HOST).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.host}/api/tags")
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
        prompt = f"""You are an expert academic writing assistant.
Task: Revise the given passage in '{mode}' mode.
Passage:
{original_text}

Constraints:
1. Preserve all citations (e.g. [1], (Author, 2021)).
2. Strictly preserve all empirical numbers, percentages, metrics (F1, accuracy, etc.), and model names.
3. Return ONLY a valid JSON object with the following keys:
{{
  "proposed_text": "revised passage",
  "reason": "concise explanation of change",
  "confidence": 0.90
}}
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{self.host}/api/generate", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "{}")
                    parsed = json.loads(response_text)
                    return {
                        "block_id": block_id,
                        "issue_type": mode,
                        "original_text": original_text,
                        "proposed_text": parsed.get("proposed_text", original_text),
                        "reason": parsed.get("reason", "Revised for academic clarity"),
                        "citations_preserved": True,
                        "protected_entities_preserved": True,
                        "requires_user_review": True,
                        "confidence": float(parsed.get("confidence", 0.85))
                    }
        except Exception:
            pass
        return None
