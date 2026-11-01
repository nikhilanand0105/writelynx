import datetime
import secrets
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.auth import require_admin
from backend.app.core.database import get_db
from backend.app.models.models import (
    User,
    Purchase,
    Entitlement,
    Document,
    AICostReservation,
    SystemSetting,
    UserRestriction,
    PaymentWebhookEvent,
)

router = APIRouter(prefix="/admin", tags=["Administration & Telemetry"])


class KillSwitchRequest(BaseModel):
    setting_key: str  # PURCHASES_PAUSED, UPLOADS_PAUSED, PROCESSING_PAUSED, AI_API_PAUSED
    enabled: bool
    reason: Optional[str] = "Admin manual override"


class RestrictUserRequest(BaseModel):
    user_id: str
    restriction_type: str = "suspension"  # suspension, ban, upload_block
    reason: str
    duration_days: Optional[int] = None


@router.get("/metrics")
def get_platform_metrics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Aggregate business, cybersecurity, and financial telemetry."""
    # 1. User metrics
    total_students = db.query(User).count()
    active_students = db.query(User).filter(User.is_active == True).count()

    # 2. Financial metrics (Integer Paise)
    completed_purchases = db.query(Purchase).filter(Purchase.status == "COMPLETED").all()
    total_revenue_paise = sum(p.amount_paise for p in completed_purchases)
    total_orders_count = len(completed_purchases)

    # 3. AI Infrastructure Spend (Integer Paise)
    ai_reservations = db.query(AICostReservation).all()
    total_ai_spend_paise = sum(r.cost_incurred_paise for r in ai_reservations)

    # 4. Gross Margin %
    net_margin_paise = total_revenue_paise - total_ai_spend_paise
    margin_percentage = (
        round((net_margin_paise / total_revenue_paise) * 100.0, 2)
        if total_revenue_paise > 0
        else 100.0
    )

    # 5. Entitlement & Document inventory
    available_entitlements = db.query(Entitlement).filter(Entitlement.status == "AVAILABLE").count()
    completed_entitlements = db.query(Entitlement).filter(Entitlement.status == "COMPLETED").count()
    total_documents = db.query(Document).count()

    # 6. Breakdown by plan tier
    tier_counts = {"basic": 0, "standard": 0, "extended": 0}
    for p in completed_purchases:
        if p.plan_tier in tier_counts:
            tier_counts[p.plan_tier] += 1

    # 7. Breakdown by operating mode
    mode_counts = {"proofreading": 0, "academic_revision": 0, "evidence_review": 0}
    for p in completed_purchases:
        if p.operating_mode in mode_counts:
            mode_counts[p.operating_mode] += 1

    return {
        "total_students": total_students,
        "active_students": active_students,
        "financials": {
            "total_orders": total_orders_count,
            "total_revenue_paise": total_revenue_paise,
            "total_revenue_rupees": total_revenue_paise / 100.0,
            "total_ai_spend_paise": total_ai_spend_paise,
            "total_ai_spend_rupees": total_ai_spend_paise / 100.0,
            "net_margin_paise": net_margin_paise,
            "net_margin_rupees": net_margin_paise / 100.0,
            "gross_margin_percent": margin_percentage,
        },
        "entitlements": {
            "available_ready_to_upload": available_entitlements,
            "completed": completed_entitlements,
        },
        "documents_processed": total_documents,
        "plan_breakdown": tier_counts,
        "mode_breakdown": mode_counts,
    }


@router.get("/kill-switches")
def get_kill_switches(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve active status of all emergency controls."""
    switches = ["PURCHASES_PAUSED", "UPLOADS_PAUSED", "PROCESSING_PAUSED", "AI_API_PAUSED"]
    status_map = {}
    for key in switches:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        status_map[key] = (setting.value.lower() in ("true", "1", "yes")) if setting else False
    return status_map


@router.post("/kill-switch")
def toggle_kill_switch(
    payload: KillSwitchRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Actively toggle platform kill switches for incident response."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == payload.setting_key).first()
    if not setting:
        setting = SystemSetting(
            id=f"set_{secrets.token_hex(8)}",
            key=payload.setting_key,
            value=str(payload.enabled).lower(),
            description=payload.reason,
            updated_by=admin.id,
        )
        db.add(setting)
    else:
        setting.value = str(payload.enabled).lower()
        setting.description = payload.reason
        setting.updated_by = admin.id
        setting.updated_at = datetime.datetime.utcnow()

    db.commit()
    return {
        "status": "updated",
        "setting_key": payload.setting_key,
        "enabled": payload.enabled,
        "reason": payload.reason,
    }


@router.post("/restrict-user")
def restrict_user(
    payload: RestrictUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Suspend or ban abusive user accounts."""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    expires_at = None
    if payload.duration_days:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=payload.duration_days)

    restriction = UserRestriction(
        id=f"res_{secrets.token_hex(12)}",
        user_id=user.id,
        restriction_type=payload.restriction_type,
        reason=payload.reason,
        created_by=admin.id,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(restriction)
    db.commit()

    return {
        "status": "restricted",
        "user_id": user.id,
        "email": user.email,
        "restriction_type": payload.restriction_type,
        "reason": payload.reason,
    }


@router.get("/audit-logs")
def get_audit_logs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """View payment webhook logs and emergency setting audits."""
    events = db.query(PaymentWebhookEvent).order_by(
        PaymentWebhookEvent.created_at.desc()
    ).limit(50).all()

    return [
        {
            "id": e.id,
            "event_id": e.event_id,
            "event_type": e.event_type,
            "processed": e.processed,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]
