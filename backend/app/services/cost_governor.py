import datetime
import logging
import secrets
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.models import AICostReservation, SystemSetting, Document

logger = logging.getLogger("writelynx.cost_governor")

# Token rates in integer paise per 1,000 tokens
PROVIDER_TOKEN_RATES_PAISE_PER_1K = {
    "gemini": {"prompt": 1, "completion": 3},
    "openai": {"prompt": 2, "completion": 6},
    "ollama": {"prompt": 0, "completion": 0},
    "no_llm": {"prompt": 0, "completion": 0},
}

DEFAULT_MAX_OUTPUT_TOKENS = 1024
DEFAULT_GLOBAL_DAILY_BUDGET_PAISE = 500_000  # ₹5,000 per day emergency ceiling


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
    def get_spent_for_document(cls, db: Session, document_id: str) -> int:
        """Return total paise spent on AI for this document so far."""
        records = db.query(AICostReservation).filter(AICostReservation.document_id == document_id).all()
        return sum(r.cost_incurred_paise for r in records)

    @classmethod
    def check_global_daily_limit(cls, db: Session) -> bool:
        """Enforce organization-level daily cost ceiling."""
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_records = db.query(AICostReservation).filter(AICostReservation.created_at >= today_start).all()
        daily_total = sum(r.cost_incurred_paise for r in daily_records)

        setting = db.query(SystemSetting).filter(SystemSetting.key == "GLOBAL_DAILY_BUDGET_PAISE").first()
        limit = int(setting.value) if setting and setting.value.isdigit() else DEFAULT_GLOBAL_DAILY_BUDGET_PAISE

        return daily_total < limit

    @classmethod
    def reserve_budget(
        cls,
        db: Session,
        document_id: str,
        plan_tier: str,
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        provider: str = "gemini",
    ) -> Tuple[bool, Optional[str], str]:
        """
        Pre-call atomic budget reservation.
        Returns: (can_proceed, reservation_id, reason)
        """
        if cls.is_ai_api_paused(db):
            return False, None, "AI processing paused by administrator"

        if not cls.check_global_daily_limit(db):
            return False, None, "Global daily AI processing budget reached"

        budget = cls.get_document_budget(plan_tier)
        spent = cls.get_spent_for_document(db, document_id)

        rates = PROVIDER_TOKEN_RATES_PAISE_PER_1K.get(provider.lower(), {"prompt": 1, "completion": 2})
        est_cost_paise = int(
            (estimated_input_tokens / 1000.0) * rates["prompt"] +
            (estimated_output_tokens / 1000.0) * rates["completion"]
        )
        if est_cost_paise == 0 and provider.lower() not in ("ollama", "no_llm"):
            est_cost_paise = 1

        if (spent + est_cost_paise) > budget:
            return False, None, f"Document budget exhausted (spent: ₹{spent/100:.2f}, limit: ₹{budget/100:.2f})"

        reservation_id = f"aic_{secrets.token_hex(12)}"
        res = AICostReservation(
            id=reservation_id,
            document_id=document_id,
            plan_tier=plan_tier.lower(),
            budget_allocated_paise=budget,
            cost_incurred_paise=est_cost_paise,
            prompt_tokens=estimated_input_tokens,
            completion_tokens=estimated_output_tokens,
            provider_used=provider,
            model_name="pre_call_reservation",
        )
        db.add(res)
        db.commit()
        return True, reservation_id, "Budget reserved successfully"

    @classmethod
    def reconcile_reservation(
        cls,
        db: Session,
        reservation_id: str,
        actual_prompt_tokens: int,
        actual_completion_tokens: int,
        provider: str,
        model_name: str,
    ) -> AICostReservation:
        """Post-call exact reconciliation against provider-reported usage."""
        reservation = db.query(AICostReservation).filter(AICostReservation.id == reservation_id).first()
        if not reservation:
            logger.warning(f"Reservation {reservation_id} not found for reconciliation.")
            return None

        rates = PROVIDER_TOKEN_RATES_PAISE_PER_1K.get(provider.lower(), {"prompt": 1, "completion": 2})
        actual_cost_paise = int(
            (actual_prompt_tokens / 1000.0) * rates["prompt"] +
            (actual_completion_tokens / 1000.0) * rates["completion"]
        )
        if actual_cost_paise == 0 and (actual_prompt_tokens > 0 or actual_completion_tokens > 0) and provider.lower() not in ("ollama", "no_llm"):
            actual_cost_paise = 1

        reservation.cost_incurred_paise = actual_cost_paise
        reservation.prompt_tokens = actual_prompt_tokens
        reservation.completion_tokens = actual_completion_tokens
        reservation.provider_used = provider
        reservation.model_name = model_name
        db.commit()
        db.refresh(reservation)
        return reservation

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
        """Atomically record spend directly when pre-reservation was not used."""
        rates = PROVIDER_TOKEN_RATES_PAISE_PER_1K.get(provider.lower(), {"prompt": 1, "completion": 2})
        cost_paise = int(
            (prompt_tokens / 1000.0) * rates["prompt"] + (completion_tokens / 1000.0) * rates["completion"]
        )
        if cost_paise == 0 and (prompt_tokens > 0 or completion_tokens > 0) and provider.lower() not in ("ollama", "no_llm"):
            cost_paise = 1

        budget = cls.get_document_budget(plan_tier)
        reservation = AICostReservation(
            id=f"aic_{secrets.token_hex(12)}" if not hasattr(cls, '_test_id') else cls._test_id,
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
    def can_make_ai_call(
        cls,
        db: Session,
        document_id: str,
        plan_tier: str,
        estimated_tokens: int = 1000,
    ) -> tuple[bool, str]:
        """Circuit breaker: Checks if document is within its budget ceiling."""
        if cls.is_ai_api_paused(db):
            return False, "no_llm"

        budget = cls.get_document_budget(plan_tier)
        spent = cls.get_spent_for_document(db, document_id)

        if spent >= budget:
            return False, "no_llm"

        if spent >= int(budget * 0.85):
            return True, "ollama"

        return True, settings.DEFAULT_LLM_PROVIDER
