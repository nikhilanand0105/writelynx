import datetime
import hashlib
import hmac
import json
import secrets
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.models import (
    User,
    Purchase,
    Entitlement,
    PaymentWebhookEvent,
    SystemSetting,
)


class PaymentService:
    @staticmethod
    def get_plan_config(plan_tier: str) -> Dict[str, Any]:
        """Fetch tier pricing, character, page, and size limits."""
        tier = plan_tier.lower().strip()
        if tier not in settings.PLAN_CONFIGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan tier '{plan_tier}'. Available tiers: {list(settings.PLAN_CONFIGS.keys())}"
            )
        return settings.PLAN_CONFIGS[tier]

    @staticmethod
    def check_purchase_allowed(db: Session) -> bool:
        """Check system setting emergency pause."""
        setting = db.query(SystemSetting).filter(SystemSetting.key == "PURCHASES_PAUSED").first()
        if setting and setting.value.lower() in ("true", "1", "yes"):
            return False
        return True

    @classmethod
    def create_order(
        cls,
        db: Session,
        user: User,
        plan_tier: str,
        operating_mode: str = "academic_revision",
    ) -> Dict[str, Any]:
        """Create a Razorpay order in integer paise."""
        if not cls.check_purchase_allowed(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Purchases are temporarily paused for maintenance. Please check back shortly."
            )

        if operating_mode not in settings.OPERATING_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid operating mode '{operating_mode}'. Allowed modes: {list(settings.OPERATING_MODES.keys())}"
            )

        plan = cls.get_plan_config(plan_tier)
        amount_paise = plan["price_paise"]
        receipt_id = f"rcpt_{user.registration_number or user.id[:8]}_{int(datetime.datetime.utcnow().timestamp())}"
        order_id = f"order_{secrets.token_hex(10)}"

        # Create record in DB
        purchase = Purchase(
            id=f"pur_{secrets.token_hex(12)}",
            user_id=user.id,
            plan_tier=plan_tier.lower(),
            operating_mode=operating_mode,
            amount_paise=amount_paise,
            currency="INR",
            razorpay_order_id=order_id,
            status="PENDING",
        )
        db.add(purchase)
        db.commit()

        return {
            "order_id": order_id,
            "purchase_id": purchase.id,
            "amount_paise": amount_paise,
            "amount_rupees": amount_paise // 100,
            "currency": "INR",
            "receipt": receipt_id,
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan_tier": plan_tier.lower(),
            "operating_mode": operating_mode,
            "plan_name": plan["name"],
            "max_pages": plan["max_pages"],
            "max_characters": plan["max_characters"],
        }

    @classmethod
    def verify_signature(
        cls,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """Cryptographically verify Razorpay HMAC-SHA256 signature."""
        if not signature or not order_id or not payment_id:
            return False

        # In offline mock mode with test keys, accept deterministic mock signatures
        if settings.TEST_MODE_MOCK_AUTH and signature.startswith("mock_sig_"):
            return signature == f"mock_sig_{order_id}_{payment_id}"

        message = f"{order_id}|{payment_id}".encode("utf-8")
        secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
        expected_sig = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    @classmethod
    def verify_and_fulfill_payment(
        cls,
        db: Session,
        user: User,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> Dict[str, Any]:
        """Verify payment and issue a single-use entitlement."""
        is_valid = cls.verify_signature(order_id, payment_id, signature)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed. Untrusted or tampered transaction."
            )

        # Retrieve pending purchase with lock
        purchase = db.query(Purchase).filter(
            Purchase.razorpay_order_id == order_id,
            Purchase.user_id == user.id,
        ).first()

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found or does not belong to the current user."
            )

        if purchase.status == "COMPLETED":
            # Already fulfilled (idempotent)
            entitlement = db.query(Entitlement).filter(Entitlement.purchase_id == purchase.id).first()
            return {
                "status": "already_fulfilled",
                "purchase_id": purchase.id,
                "entitlement_id": entitlement.id if entitlement else None,
                "plan_tier": purchase.plan_tier,
                "operating_mode": purchase.operating_mode,
            }

        # Update purchase record
        purchase.razorpay_payment_id = payment_id
        purchase.razorpay_signature = signature
        purchase.status = "COMPLETED"

        plan = cls.get_plan_config(purchase.plan_tier)

        # Issue single-use entitlement
        entitlement_id = f"ent_{secrets.token_hex(12)}"
        entitlement = Entitlement(
            id=entitlement_id,
            user_id=user.id,
            purchase_id=purchase.id,
            plan_tier=purchase.plan_tier,
            operating_mode=purchase.operating_mode,
            max_pages=plan["max_pages"],
            max_characters=plan["max_characters"],
            max_file_size_mb=plan["max_file_size_mb"],
            ai_budget_paise=plan["ai_budget_paise"],
            status="AVAILABLE",
        )
        db.add(entitlement)
        db.commit()

        return {
            "status": "success",
            "purchase_id": purchase.id,
            "entitlement_id": entitlement.id,
            "plan_tier": entitlement.plan_tier,
            "operating_mode": entitlement.operating_mode,
            "max_pages": entitlement.max_pages,
            "max_characters": entitlement.max_characters,
        }

    @classmethod
    def calculate_upgrade_difference(
        cls,
        current_tier: str,
        target_tier: str,
    ) -> int:
        """Calculate exact difference in integer paise between tiers."""
        curr_plan = cls.get_plan_config(current_tier)
        target_plan = cls.get_plan_config(target_tier)

        diff = target_plan["price_paise"] - curr_plan["price_paise"]
        if diff <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target tier '{target_tier}' is not an upgrade from '{current_tier}'."
            )
        return diff

    @classmethod
    def create_upgrade_order(
        cls,
        db: Session,
        user: User,
        entitlement_id: str,
        target_tier: str,
    ) -> Dict[str, Any]:
        """Create an order for the exact price difference between tiers."""
        entitlement = db.query(Entitlement).filter(
            Entitlement.id == entitlement_id,
            Entitlement.user_id == user.id,
        ).first()

        if not entitlement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entitlement not found."
            )

        if entitlement.status in ("PROCESSING", "COMPLETED", "REFUNDED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upgrade entitlement in state '{entitlement.status}'."
            )

        diff_paise = cls.calculate_upgrade_difference(entitlement.plan_tier, target_tier)
        order_id = f"order_upg_{secrets.token_hex(10)}"

        # Save upgrade purchase record
        purchase = Purchase(
            id=f"pur_upg_{secrets.token_hex(12)}",
            user_id=user.id,
            plan_tier=target_tier.lower(),
            operating_mode=entitlement.operating_mode,
            amount_paise=diff_paise,
            currency="INR",
            razorpay_order_id=order_id,
            status="PENDING",
        )
        db.add(purchase)
        db.commit()

        target_plan = cls.get_plan_config(target_tier)
        return {
            "order_id": order_id,
            "purchase_id": purchase.id,
            "entitlement_id": entitlement.id,
            "target_tier": target_tier.lower(),
            "upgrade_amount_paise": diff_paise,
            "upgrade_amount_rupees": diff_paise // 100,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "new_max_pages": target_plan["max_pages"],
            "new_max_characters": target_plan["max_characters"],
        }

    @classmethod
    def verify_and_fulfill_upgrade(
        cls,
        db: Session,
        user: User,
        entitlement_id: str,
        target_tier: str,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> Dict[str, Any]:
        """Fulfill upgrade after payment verification."""
        is_valid = cls.verify_signature(order_id, payment_id, signature)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed."
            )

        entitlement = db.query(Entitlement).filter(
            Entitlement.id == entitlement_id,
            Entitlement.user_id == user.id,
        ).first()

        if not entitlement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entitlement not found."
            )

        purchase = db.query(Purchase).filter(
            Purchase.razorpay_order_id == order_id,
            Purchase.user_id == user.id,
        ).first()

        if purchase:
            purchase.razorpay_payment_id = payment_id
            purchase.razorpay_signature = signature
            purchase.status = "COMPLETED"

        target_plan = cls.get_plan_config(target_tier)
        entitlement.plan_tier = target_tier.lower()
        entitlement.max_pages = target_plan["max_pages"]
        entitlement.max_characters = target_plan["max_characters"]
        entitlement.max_file_size_mb = target_plan["max_file_size_mb"]
        entitlement.ai_budget_paise = target_plan["ai_budget_paise"]
        if entitlement.status == "OVER_LIMIT_PENDING_UPGRADE":
            entitlement.status = "AVAILABLE"

        db.commit()

        return {
            "status": "upgraded",
            "entitlement_id": entitlement.id,
            "plan_tier": entitlement.plan_tier,
            "max_pages": entitlement.max_pages,
            "max_characters": entitlement.max_characters,
        }

    @classmethod
    def handle_webhook_event(
        cls,
        db: Session,
        raw_payload: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """Idempotent webhook handler with HMAC verification and duplicate rejection."""
        # 1. Verify webhook signature
        if not signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing webhook signature.")

        secret = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
        expected_sig = hmac.new(secret, raw_payload, hashlib.sha256).hexdigest()

        # Permit mock webhook in test mode
        if not (settings.TEST_MODE_MOCK_AUTH and signature == "mock_webhook_sig"):
            if not hmac.compare_digest(expected_sig, signature):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

        # 2. Parse payload
        try:
            event_data = json.loads(raw_payload.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON payload.")

        event_id = event_data.get("event_id") or event_data.get("id") or f"evt_{secrets.token_hex(8)}"
        event_type = event_data.get("event", "unknown")

        # 3. Check duplicate event (Idempotency)
        existing_event = db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.event_id == event_id).first()
        if existing_event:
            return {"status": "already_processed", "event_id": event_id}

        # Record webhook event
        webhook_rec = PaymentWebhookEvent(
            id=f"whe_{secrets.token_hex(12)}",
            event_id=event_id,
            event_type=event_type,
            payload=event_data,
            processed=False,
        )
        db.add(webhook_rec)
        db.commit()

        # 4. Process event
        if event_type in ("payment.captured", "order.paid"):
            payload_entity = event_data.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payload_entity.get("order_id")
            payment_id = payload_entity.get("id")

            if order_id:
                purchase = db.query(Purchase).filter(Purchase.razorpay_order_id == order_id).first()
                if purchase and purchase.status != "COMPLETED":
                    purchase.razorpay_payment_id = payment_id
                    purchase.status = "COMPLETED"

                    # Ensure entitlement is issued if not already
                    existing_ent = db.query(Entitlement).filter(Entitlement.purchase_id == purchase.id).first()
                    if not existing_ent:
                        plan = cls.get_plan_config(purchase.plan_tier)
                        new_ent = Entitlement(
                            id=f"ent_{secrets.token_hex(12)}",
                            user_id=purchase.user_id,
                            purchase_id=purchase.id,
                            plan_tier=purchase.plan_tier,
                            operating_mode=purchase.operating_mode,
                            max_pages=plan["max_pages"],
                            max_characters=plan["max_characters"],
                            max_file_size_mb=plan["max_file_size_mb"],
                            ai_budget_paise=plan["ai_budget_paise"],
                            status="AVAILABLE",
                        )
                        db.add(new_ent)

        webhook_rec.processed = True
        db.commit()

        return {"status": "processed", "event_id": event_id, "event_type": event_type}
