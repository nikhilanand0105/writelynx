from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""
    name: str = "base"

    @abstractmethod
    async def generate_suggestion(
        self,
        block_id: str,
        original_text: str,
        context: str,
        mode: str,
        matched_source_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate structured revision suggestion for a text block."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test whether provider is available."""
        pass
