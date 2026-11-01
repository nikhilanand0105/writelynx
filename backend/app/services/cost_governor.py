import datetime
import secrets
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.models import AICostReservation, SystemSetting, Document

# Approximate costs in integer paise per 1,000 tokens
# e.g. Gemini 1.5 Flash: ~$0.075 / 1M input tokens (~₹6.25 / 1M = 0.000625 paise/tok = ~0.6 paise / 1k tok)
PROVIDER_TOKEN_RATES_PAISE_PER_1K = {
    "gemini": {"prompt": 1, "completion": 3},
    "openai": {"prompt": 2, "completion": 6},
    "ollama": {"prompt": 0, "completion": 0},
    "no_llm": {"prompt": 0, "completion": 0},
}


class CostGovernor:
    @staticmethod
    def is_ai_api_paused(db: Session) -> bool:
        """Check emergency AI kill switch."""
        setting = db.query(SystemSetting).filter(SystemSetting.key == "AI_API_PAUSED").first()
        if setting and setting.value.lower() in ("true", "1", "yes"):
            return True
        return False

    @classmethod
    def get_document_budget(cls, plan_tier: str) -> int:
        """Get the hard cost ceiling in paise for this plan tier."""
        plan = settings.PLAN_CONFIGS.get(plan_tier.lower(), settings.PLAN_CONFIGS["basic"])
        return plan["ai_budget_paise"]

    @classmethod
    def record_cost(
        cls,
        db: Session,
        document_id: str,
        plan_tier: str,
        provider: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> AICostReservation:
        """Calculate and atomically record LLM API spend in integer paise."""
        rates = PROVIDER_TOKEN_RATES_PAISE_PER_1K.get(provider.lower(), {"prompt": 1, "completion": 2})
        cost_paise = int(
            (prompt_tokens / 1000.0) * rates["prompt"] + (completion_tokens / 1000.0) * rates["completion"]
        )
        if cost_paise == 0 and (prompt_tokens > 0 or completion_tokens > 0) and provider.lower() not in ("ollama", "no_llm"):
            cost_paise = 1  # Minimum 1 paisa for non-free external calls

        budget = cls.get_document_budget(plan_tier)

        reservation = AICostReservation(
            id=f"aic_{secrets.token_hex(12)}",
            document_id=document_id,
            plan_tier=plan_tier.lower(),
            budget_allocated_paise=budget,
            cost_incurred_paise=cost_paise,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            provider_used=provider,
            model_name=model_name,
        )
        db.add(reservation)
        db.commit()
        return reservation

    @classmethod
    def get_spent_for_document(cls, db: Session, document_id: str) -> int:
        """Return total paise spent on AI for this document so far."""
        records = db.query(AICostReservation).filter(AICostReservation.document_id == document_id).all()
        return sum(r.cost_incurred_paise for r in records)

    @classmethod
    def can_make_ai_call(
        cls,
        db: Session,
        document_id: str,
        plan_tier: str,
        estimated_tokens: int = 1000,
    ) -> tuple[bool, str]:
        """
        Circuit breaker: Checks if document is within its budget ceiling.
        Returns: (can_call, recommended_provider)
        """
        if cls.is_ai_api_paused(db):
            return False, "no_llm"

        budget = cls.get_document_budget(plan_tier)
        spent = cls.get_spent_for_document(db, document_id)

        # Hard ceiling check
        if spent >= budget:
            return False, "no_llm"

        # 85% threshold: downgrade to local/zero-cost
        if spent >= int(budget * 0.85):
            return True, "ollama"

        return True, settings.DEFAULT_LLM_PROVIDER
