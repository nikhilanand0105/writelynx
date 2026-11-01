from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.auth import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.models import User, Entitlement, Purchase
from backend.app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Billing & Payments"])


class CreateOrderRequest(BaseModel):
    plan_tier: str  # basic, standard, extended
    operating_mode: str = "academic_revision"  # proofreading, academic_revision, evidence_review


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class UpgradeOrderRequest(BaseModel):
    entitlement_id: str
    target_tier: str


class VerifyUpgradeRequest(BaseModel):
    entitlement_id: str
    target_tier: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class EntitlementResponse(BaseModel):
    id: str
    plan_tier: str
    operating_mode: str
    max_pages: int
    max_characters: int
    max_file_size_mb: int
    status: str
    document_id: Optional[str] = None
    created_at: str


@router.get("/plans")
def get_available_plans():
    """Retrieve all available plan tiers and operating modes."""
    return {
        "plans": settings.PLAN_CONFIGS,
        "operating_modes": settings.OPERATING_MODES,
        "currency": "INR",
    }


@router.post("/create-order")
def create_payment_order(
    payload: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new Razorpay order in integer paise."""
    return PaymentService.create_order(
        db=db,
        user=user,
        plan_tier=payload.plan_tier,
        operating_mode=payload.operating_mode,
    )


@router.post("/verify")
def verify_payment(
    payload: VerifyPaymentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify payment signature and issue single-use entitlement."""
    return PaymentService.verify_and_fulfill_payment(
        db=db,
        user=user,
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )


@router.post("/upgrade-order")
@router.post("/create-upgrade-order")
def create_upgrade_order(
    payload: UpgradeOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create an upgrade order for the exact price difference between tiers."""
    return PaymentService.create_upgrade_order(
        db=db,
        user=user,
        entitlement_id=payload.entitlement_id,
        target_tier=payload.target_tier,
    )


@router.post("/verify-upgrade")
def verify_upgrade(
    payload: VerifyUpgradeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify upgrade payment and update entitlement tier."""
    return PaymentService.verify_and_fulfill_upgrade(
        db=db,
        user=user,
        entitlement_id=payload.entitlement_id,
        target_tier=payload.target_tier,
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    db: Session = Depends(get_db)
):
    """Idempotent Razorpay webhook listener."""
    raw_payload = await request.body()
    return PaymentService.handle_webhook_event(
        db=db,
        raw_payload=raw_payload,
        signature=x_razorpay_signature or "",
    )


@router.get("/my-entitlements", response_model=List[EntitlementResponse])
def get_user_entitlements(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all entitlements owned by the authenticated student."""
    entitlements = db.query(Entitlement).filter(
        Entitlement.user_id == user.id
    ).order_by(Entitlement.created_at.desc()).all()

    return [
        EntitlementResponse(
            id=e.id,
            plan_tier=e.plan_tier,
            operating_mode=e.operating_mode,
            max_pages=e.max_pages,
            max_characters=e.max_characters,
            max_file_size_mb=e.max_file_size_mb,
            status=e.status,
            document_id=e.document_id,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in entitlements
    ]


@router.get("/my-purchases")
def get_user_purchases(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List purchase history for the authenticated student."""
    purchases = db.query(Purchase).filter(
        Purchase.user_id == user.id
    ).order_by(Purchase.created_at.desc()).all()

    return [
        {
            "id": p.id,
            "plan_tier": p.plan_tier,
            "operating_mode": p.operating_mode,
            "amount_paise": p.amount_paise,
            "amount_rupees": p.amount_paise // 100,
            "currency": p.currency,
            "status": p.status,
            "razorpay_order_id": p.razorpay_order_id,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in purchases
    ]
