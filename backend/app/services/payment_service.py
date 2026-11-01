import datetime
import hashlib
import hmac
import json
import logging
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

logger = logging.getLogger("writelynx.payments")


def get_razorpay_client():
    """Retrieve initialized Razorpay client if configured."""
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET and settings.RAZORPAY_KEY_SECRET != "mock_razorpay_secret":
        try:
            import razorpay
            return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        except Exception as e:
            logger.warning(f"Could not initialize Razorpay client: {e}")
            return None
    return None


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
        """Create an authoritative payment order in integer paise."""
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

        client = get_razorpay_client()
        order_id = None
        if client:
            try:
                rzp_order = client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": receipt_id,
                    "payment_capture": 1,
                    "notes": {
                        "user_id": user.id,
                        "email": user.email,
                        "plan_tier": plan_tier.lower(),
                        "operating_mode": operating_mode,
                    }
                })
                order_id = rzp_order["id"]
            except Exception as e:
                logger.error(f"Razorpay order creation failed: {e}")
                if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_PAYMENTS:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Payment gateway communication error. Please try again."
                    )
        else:
            if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_PAYMENTS:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Payment gateway is unavailable or unconfigured. Cannot initialize checkout."
                )

        if not order_id:
            if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_PAYMENTS:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Payment gateway failed to issue an authoritative order ID."
                )
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

        client = get_razorpay_client()
        if client:
            try:
                client.utility.verify_payment_signature({
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature
                })
                return True
            except Exception:
                return False

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

        # If live client configured, independently verify payment status, amount, and currency with gateway
        client = get_razorpay_client()
        if client and not signature.startswith("mock_sig_"):
            try:
                pay_data = client.payment.fetch(payment_id)
                if pay_data.get("status") != "captured":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Payment status is '{pay_data.get('status')}', but requires 'captured' before fulfillment."
                    )
                if pay_data.get("order_id") and pay_data.get("order_id") != order_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Payment is not associated with this order ID."
                    )
                if pay_data.get("amount") != purchase.amount_paise:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Mismatched payment amount reported by gateway."
                    )
                if pay_data.get("currency") != "INR":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Payment currency must be INR."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Gateway payment fetch failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to independently verify payment status with gateway: {str(e)}"
                )

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
        """Calculate price delta in paise for an upgrade."""
        c_plan = cls.get_plan_config(current_tier)
        t_plan = cls.get_plan_config(target_tier)
        diff = t_plan["price_paise"] - c_plan["price_paise"]
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
        """Create an order for the exact price difference between tiers, strictly bound to the entitlement."""
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
        client = get_razorpay_client()
        order_id = None
        receipt_id = f"upg_{entitlement.id[:8]}_{int(datetime.datetime.utcnow().timestamp())}"

        if client:
            try:
                rzp_order = client.order.create({
                    "amount": diff_paise,
                    "currency": "INR",
                    "receipt": receipt_id,
                    "payment_capture": 1,
                    "notes": {
                        "user_id": user.id,
                        "entitlement_id": entitlement.id,
                        "source_tier": entitlement.plan_tier,
                        "target_tier": target_tier.lower(),
                        "is_upgrade": True,
                    }
                })
                order_id = rzp_order["id"]
            except Exception as e:
                logger.error(f"Razorpay upgrade order creation failed: {e}")
                if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_PAYMENTS:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Payment gateway communication error on upgrade."
                    )
        else:
            if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_PAYMENTS:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Payment gateway is unconfigured in production/staging."
                )

        if not order_id:
            if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_PAYMENTS:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Payment gateway failed to issue an authoritative upgrade order ID."
                )
            order_id = f"order_upg_{secrets.token_hex(10)}"

        # Save upgrade purchase record with strict binding to original purchase and entitlement
        purchase = Purchase(
            id=f"pur_upg_{secrets.token_hex(12)}",
            user_id=user.id,
            plan_tier=target_tier.lower(),
            operating_mode=entitlement.operating_mode,
            amount_paise=diff_paise,
            currency="INR",
            razorpay_order_id=order_id,
            status="PENDING",
            is_upgrade=True,
            parent_purchase_id=entitlement.purchase_id,
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
        """Fulfill upgrade after payment verification with strict binding checks (P2.5)."""
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
                detail="Target entitlement not found."
            )

        purchase = db.query(Purchase).filter(
            Purchase.razorpay_order_id == order_id,
            Purchase.user_id == user.id,
        ).first()

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upgrade purchase order not found or does not belong to student."
            )

        if purchase.status == "COMPLETED":
            # Idempotent return
            return {
                "status": "already_upgraded",
                "entitlement_id": entitlement.id,
                "plan_tier": entitlement.plan_tier,
                "max_pages": entitlement.max_pages,
                "max_characters": entitlement.max_characters,
            }

        # Priority 2.5: Validate that the purchase is strictly bound to this entitlement and target tier
        if not purchase.is_upgrade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction was not registered as a tier upgrade purchase."
            )

        if purchase.parent_purchase_id != entitlement.purchase_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upgrade payment is not bound to this entitlement."
            )

        if purchase.plan_tier != target_tier.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upgrade payment was minted for tier '{purchase.plan_tier}', not '{target_tier}'."
            )

        expected_diff = cls.calculate_upgrade_difference(entitlement.plan_tier, target_tier)
        if purchase.amount_paise != expected_diff:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upgrade payment amount does not match required tier difference."
            )

        # Independently verify upgrade payment with gateway
        client = get_razorpay_client()
        if client and not signature.startswith("mock_sig_"):
            try:
                pay_data = client.payment.fetch(payment_id)
                if pay_data.get("status") != "captured":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Upgrade payment status is '{pay_data.get('status')}', but requires 'captured' before fulfillment."
                    )
                if pay_data.get("order_id") and pay_data.get("order_id") != order_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Upgrade payment is not associated with this order ID."
                    )
                if pay_data.get("amount") != purchase.amount_paise:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Mismatched upgrade payment amount reported by gateway."
                    )
                if pay_data.get("currency") != "INR":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Payment currency must be INR."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Gateway upgrade payment fetch failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to independently verify upgrade payment status with gateway: {str(e)}"
                )

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
        if not signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing webhook signature.")

        secret = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
        expected_sig = hmac.new(secret, raw_payload, hashlib.sha256).hexdigest()

        # Permit mock webhook in test mode
        if not (settings.TEST_MODE_MOCK_AUTH and signature == "mock_webhook_sig"):
            if not hmac.compare_digest(expected_sig, signature):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

        try:
            event_data = json.loads(raw_payload.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON payload.")

        event_id = event_data.get("event_id") or event_data.get("id") or f"evt_{secrets.token_hex(8)}"
        event_type = event_data.get("event", "unknown")

        existing_event = db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.event_id == event_id).first()
        if existing_event:
            return {"status": "already_processed", "event_id": event_id}

        webhook_rec = PaymentWebhookEvent(
            id=f"whe_{secrets.token_hex(12)}",
            event_id=event_id,
            event_type=event_type,
            payload=event_data,
            processed=False,
        )
        db.add(webhook_rec)
        db.commit()

        if event_type in ("payment.captured", "order.paid"):
            payload_payment = event_data.get("payload", {}).get("payment", {}).get("entity", {})
            payload_order = event_data.get("payload", {}).get("order", {}).get("entity", {})

            order_id = payload_payment.get("order_id") or payload_order.get("id")
            payment_id = payload_payment.get("id")
            amount = payload_payment.get("amount") or payload_order.get("amount_paid") or payload_order.get("amount")
            currency = payload_payment.get("currency") or payload_order.get("currency")

            if order_id:
                purchase = db.query(Purchase).filter(Purchase.razorpay_order_id == order_id).first()
                if purchase and purchase.status != "COMPLETED":
                    # Verify amount and currency if provided
                    if amount and amount != purchase.amount_paise:
                        logger.error(f"Webhook amount mismatch for order {order_id}: expected {purchase.amount_paise}, got {amount}")
                        return {"status": "amount_mismatch", "event_id": event_id}
                    if currency and currency != "INR":
                        logger.error(f"Webhook currency mismatch for order {order_id}: expected INR, got {currency}")
                        return {"status": "currency_mismatch", "event_id": event_id}

                    purchase.razorpay_payment_id = payment_id
                    purchase.status = "COMPLETED"

                    if purchase.is_upgrade:
                        # Item 5: Dedicated upgrade fulfillment path — update existing parent entitlement, never create a new one
                        parent_ent = db.query(Entitlement).filter(
                            Entitlement.purchase_id == purchase.parent_purchase_id
                        ).first()
                        if parent_ent:
                            target_plan = cls.get_plan_config(purchase.plan_tier)
                            parent_ent.plan_tier = purchase.plan_tier.lower()
                            parent_ent.max_pages = target_plan["max_pages"]
                            parent_ent.max_characters = target_plan["max_characters"]
                            parent_ent.max_file_size_mb = target_plan["max_file_size_mb"]
                            parent_ent.ai_budget_paise = target_plan["ai_budget_paise"]
                            if parent_ent.status == "OVER_LIMIT_PENDING_UPGRADE":
                                parent_ent.status = "AVAILABLE"
                    else:
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
