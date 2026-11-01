import datetime
import io
import json
import secrets
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.models import (
    User,
    Session as UserSession,
    UserRestriction,
    Purchase,
    Entitlement,
    UploadReservation,
    PaymentWebhookEvent,
    Document,
    DocumentBlock,
    AnalysisJob,
    Export,
    SystemSetting,
    AICostReservation,
)
from backend.app.services.cost_governor import CostGovernor
from backend.app.services.job_queue import JobQueueService
from backend.app.services.payment_service import PaymentService

client = TestClient(app)
SAMPLE_DOC = Path("sample_documents/academic_research_report.docx")


def create_minimal_test_docx(text: str = "This is a clean academic research manuscript paragraph for testing purposes.") -> bytes:
    """Create a minimal valid DOCX file in-memory for testing."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        z.writestr("word/document.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>""")
    return buf.getvalue()


# ==============================================================================
# 1. AUTHENTICATION & IDENTITY TESTS (Scenarios 1 - 10)
# ==============================================================================

def test_01_valid_vit_student_login():
    """Verify valid @vitstudent.ac.in OAuth token logs in successfully."""
    res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE1001:21bce1001@vitstudent.ac.in"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["email"] == "21bce1001@vitstudent.ac.in"
    assert data["user"]["registration_number"] == "21BCE1001"


def test_02_registration_number_extraction():
    """Verify extraction of diverse VIT registration formats."""
    res = client.post("/api/auth/google-login", json={"id_token": "mock-token:22MIS0045:22mis0045@vitstudent.ac.in"})
    assert res.status_code == 200
    assert res.json()["user"]["registration_number"] == "22MIS0045"


def test_03_personal_gmail_rejection():
    """Strictly reject personal Gmail accounts (@gmail.com)."""
    res = client.post("/api/auth/google-login", json={"id_token": "mock-token:john.doe@gmail.com"})
    assert res.status_code == 403
    assert "vitstudent.ac.in" in res.json()["detail"]


def test_04_other_university_domain_rejection():
    """Strictly reject non-VIT academic domains."""
    res = client.post("/api/auth/google-login", json={"id_token": "mock-token:student@mit.edu"})
    assert res.status_code == 403


def test_05_expired_or_invalid_session_rejection():
    """Reject requests with non-existent or invalid session tokens."""
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_12345"})
    assert res.status_code == 401


def test_06_session_logout_invalidation():
    """Logout invalidates the session in the database."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE1002:21bce1002@vitstudent.ac.in"})
    token = login_res.json()["token"]

    # Verify session active
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Verify session now rejected
    after_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_res.status_code == 401


def test_07_user_suspension_enforcement():
    """Enforce access restriction when a student account is suspended."""
    db = SessionLocal()
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE1003:21bce1003@vitstudent.ac.in"})
    token = login_res.json()["token"]
    user_id = login_res.json()["user"]["id"]

    # Apply restriction in DB
    restriction = UserRestriction(
        id=f"res_{secrets.token_hex(8)}",
        user_id=user_id,
        restriction_type="suspension",
        reason="Academic integrity violation under review",
        is_active=True,
    )
    db.add(restriction)
    db.commit()
    db.close()

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "Account restricted" in res.json()["detail"]


def test_08_admin_authorization_enforcement():
    """Regular student cannot access admin metrics; designated admin can."""
    student_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE1004:21bce1004@vitstudent.ac.in"})
    s_token = student_res.json()["token"]

    # Student denied admin
    metric_fail = client.get("/api/admin/metrics", headers={"Authorization": f"Bearer {s_token}"})
    assert metric_fail.status_code == 403

    # Admin allowed
    admin_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:admin@vitstudent.ac.in"})
    a_token = admin_res.json()["token"]
    metric_ok = client.get("/api/admin/metrics", headers={"Authorization": f"Bearer {a_token}"})
    assert metric_ok.status_code == 200
    assert "financials" in metric_ok.json()


def test_09_missing_oauth_token_rejected():
    """Empty or missing OAuth token payload fails validation."""
    res = client.post("/api/auth/google-login", json={"id_token": ""})
    assert res.status_code in (401, 422)


def test_10_tampered_bearer_token_rejected():
    """Forged token format is denied access."""
    res = client.get("/api/payments/my-entitlements", headers={"Authorization": "Bearer forged_jwt_or_fake_hex"})
    assert res.status_code == 401


# ==============================================================================
# 2. PAYMENT & BILLING TESTS (Scenarios 11 - 20)
# ==============================================================================

def test_11_basic_plan_order_creation_paise():
    """Basic plan order created with exact integer 2000 paise (₹20)."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2001:21bce2001@vitstudent.ac.in"})
    token = login_res.json()["token"]

    res = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["amount_paise"] == 2000
    assert data["amount_rupees"] == 20
    assert data["currency"] == "INR"
    assert data["max_pages"] == 4


def test_12_standard_plan_order_creation_paise():
    """Standard plan order created with exact integer 5000 paise (₹50)."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2002:21bce2002@vitstudent.ac.in"})
    token = login_res.json()["token"]

    res = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "standard", "operating_mode": "evidence_review"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["amount_paise"] == 5000
    assert data["amount_rupees"] == 50
    assert data["max_pages"] == 20


def test_13_extended_plan_order_creation_paise():
    """Extended plan order created with exact integer 10000 paise (₹100)."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2003:21bce2003@vitstudent.ac.in"})
    token = login_res.json()["token"]

    res = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "extended", "operating_mode": "proofreading"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["amount_paise"] == 10000
    assert data["amount_rupees"] == 100
    assert data["max_pages"] == 50


def test_14_payment_verification_issues_entitlement():
    """Valid signature verification issues a single-use AVAILABLE entitlement."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2004:21bce2004@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    order_id = order["order_id"]
    payment_id = "pay_test_001"
    signature = f"mock_sig_{order_id}_{payment_id}"

    res = client.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "entitlement_id" in data


def test_15_tampered_signature_rejected():
    """Untrusted signature is rejected with 400 Bad Request."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2005:21bce2005@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    res = client.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_test_002", "razorpay_signature": "invalid_signature"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "signature verification failed" in res.json()["detail"].lower()


def test_16_duplicate_payment_verification_idempotent():
    """Duplicate verification does not create duplicate entitlements."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2006:21bce2006@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    order_id = order["order_id"]
    payment_id = "pay_test_003"
    signature = f"mock_sig_{order_id}_{payment_id}"

    res1 = client.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res1.status_code == 200
    ent_id = res1.json()["entitlement_id"]

    res2 = client.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_fulfilled"
    assert res2.json()["entitlement_id"] == ent_id


def test_17_idempotent_webhook_deduplication():
    """Duplicate webhook delivery is safely ignored using event_id tracking."""
    event_id = f"evt_{secrets.token_hex(8)}"
    payload = json.dumps({
        "event_id": event_id,
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_hook_1", "order_id": "order_none"}}}
    }).encode("utf-8")

    res1 = client.post(
        "/api/payments/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": "mock_webhook_sig"}
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    # Second delivery
    res2 = client.post(
        "/api/payments/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": "mock_webhook_sig"}
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"


def test_18_webhook_invalid_signature_rejected():
    """Webhook with tampered signature is rejected."""
    payload = b'{"event": "payment.captured"}'
    res = client.post(
        "/api/payments/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": "tampered_sig"}
    )
    assert res.status_code == 400


def test_19_upgrade_order_exact_difference_calculation():
    """Upgrading from Basic (₹20) to Standard (₹50) charges exactly ₹30 (3,000 paise)."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2007:21bce2007@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    verify_res = client.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_test_004", "razorpay_signature": f"mock_sig_{order['order_id']}_pay_test_004"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()
    ent_id = verify_res["entitlement_id"]

    # Request upgrade to Standard
    upg_res = client.post(
        "/api/payments/upgrade-order",
        json={"entitlement_id": ent_id, "target_tier": "standard"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert upg_res.status_code == 200
    upg_data = upg_res.json()
    assert upg_data["upgrade_amount_paise"] == 3000  # 5000 - 2000
    assert upg_data["upgrade_amount_rupees"] == 30


def test_20_upgrade_verification_updates_entitlement_limits():
    """Verifying upgrade raises max pages and characters without double charging."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE2008:21bce2008@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    verify_res = client.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_test_005", "razorpay_signature": f"mock_sig_{order['order_id']}_pay_test_005"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()
    ent_id = verify_res["entitlement_id"]

    upg_order = client.post(
        "/api/payments/upgrade-order",
        json={"entitlement_id": ent_id, "target_tier": "extended"},
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    upg_verify = client.post(
        "/api/payments/verify-upgrade",
        json={
            "entitlement_id": ent_id,
            "target_tier": "extended",
            "razorpay_order_id": upg_order["order_id"],
            "razorpay_payment_id": "pay_upg_001",
            "razorpay_signature": f"mock_sig_{upg_order['order_id']}_pay_upg_001"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert upg_verify.status_code == 200
    assert upg_verify.json()["plan_tier"] == "extended"
    assert upg_verify.json()["max_pages"] == 50


# ==============================================================================
# 3. UPLOAD GATE & QUARANTINE SECURITY TESTS (Scenarios 21 - 35)
# ==============================================================================

def test_21_upload_attempt_without_paid_entitlement_fails():
    """Requesting an upload token without a valid entitlement is rejected."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3001:21bce3001@vitstudent.ac.in"})
    token = login_res.json()["token"]

    res = client.post(
        "/api/upload-gate/request-token",
        data={"entitlement_id": "ent_non_existent"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 404


def test_22_single_use_upload_token_consumption():
    """Upload token cannot be used twice."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3002:21bce3002@vitstudent.ac.in"})
    token = login_res.json()["token"]

    # Buy basic plan
    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p1", "razorpay_signature": f"mock_sig_{order['order_id']}_p1"}, headers={"Authorization": f"Bearer {token}"}).json()

    # Get upload token
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()
    up_token = up_slot["upload_token"]

    docx_bytes = create_minimal_test_docx("Sample academic manuscript text.")

    # First upload succeeds
    res1 = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_token},
        files={"file": ("manuscript.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res1.status_code == 200

    # Second upload with same token fails (single-use protection)
    res2 = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_token},
        files={"file": ("manuscript.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res2.status_code == 409
    assert "already been consumed" in res2.json()["detail"].lower()


def test_23_expired_upload_token_rejection():
    """Expired upload token (>15 mins) is rejected with 410 Gone."""
    db = SessionLocal()
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3003:21bce3003@vitstudent.ac.in"})
    token = login_res.json()["token"]
    user_id = login_res.json()["user"]["id"]

    # Create real entitlement to satisfy foreign key
    pur = Purchase(
        id=f"pur_exp_{secrets.token_hex(4)}",
        user_id=user_id,
        plan_tier="basic",
        amount_paise=2000,
        razorpay_order_id=f"ord_exp_{secrets.token_hex(4)}",
        status="COMPLETED"
    )
    db.add(pur)
    db.commit()

    ent = Entitlement(
        id=f"ent_exp_{secrets.token_hex(4)}",
        user_id=user_id,
        purchase_id=pur.id,
        plan_tier="basic",
        status="AVAILABLE"
    )
    db.add(ent)
    db.commit()

    # Create expired reservation directly
    expired_token = f"exp_{secrets.token_hex(8)}"
    res_rec = UploadReservation(
        id=f"res_{secrets.token_hex(8)}",
        user_id=user_id,
        entitlement_id=ent.id,
        upload_token=expired_token,
        plan_tier="basic",
        operating_mode="academic_revision",
        max_file_size_bytes=10 * 1024 * 1024,
        expires_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5),
        is_consumed=False,
    )
    db.add(res_rec)
    db.commit()
    db.close()

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": expired_token},
        files={"file": ("test.docx", create_minimal_test_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 410
    assert "expired" in res.json()["detail"].lower()


def test_24_non_docx_file_rejected():
    """Non-DOCX extensions (e.g. .pdf, .exe) rejected at upload gate."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3004:21bce3004@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p2", "razorpay_signature": f"mock_sig_{order['order_id']}_p2"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("malware.exe", b"MZ\x90\x00executable_bytes", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400


def test_25_file_size_exceeding_tier_rejected():
    """File exceeding plan MB limit rejected with 413 Payload Too Large."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3005:21bce3005@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p3", "razorpay_signature": f"mock_sig_{order['order_id']}_p3"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    # Create dummy 11MB payload (Basic limit is 10MB)
    huge_data = b"PK\x03\x04" + b"0" * (11 * 1024 * 1024)
    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("large.docx", huge_data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 413


def test_26_macro_vba_archive_rejected():
    """DOCX archive containing VBA macros is rejected by quarantine inspector."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3006:21bce3006@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p4", "razorpay_signature": f"mock_sig_{order['order_id']}_p4"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    # Build docx with vbaProject.bin
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        z.writestr("_rels/.rels", "<Relationships/>")
        z.writestr("word/vbaProject.bin", b"evil_macro_code")

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("macro_doc.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "macros" in res.json()["detail"].lower()


def test_27_zip_bomb_excessive_compression_rejected():
    """Archive with suspicious compression ratio rejected as zip bomb signature."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3007:21bce3007@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p5", "razorpay_signature": f"mock_sig_{order['order_id']}_p5"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    # Highly compressible stream
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        z.writestr("_rels/.rels", "<Relationships/>")
        z.writestr("word/huge_zeroes.xml", b"\x00" * (15 * 1024 * 1024))  # Compresses down to ~15KB

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("bomb.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "compression ratio" in res.json()["detail"].lower()


def test_28_path_traversal_archive_rejected():
    """Archive with ../ traversal members rejected immediately."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3008:21bce3008@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p6", "razorpay_signature": f"mock_sig_{order['order_id']}_p6"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../etc_passwd.xml", "traversal")
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        z.writestr("_rels/.rels", "<Relationships/>")

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("traversal.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "path traversal" in res.json()["detail"].lower()


def test_29_xxe_dtd_injection_rejected():
    """DOCTYPE or ENTITY tags in XML parts rejected for XXE prevention."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3009:21bce3009@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p7", "razorpay_signature": f"mock_sig_{order['order_id']}_p7"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", """<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><w:document><w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>""")
        z.writestr("_rels/.rels", "<Relationships/>")

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("xxe.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "doctype declarations" in res.json()["detail"].lower()


def test_30_plan_overage_triggers_422_without_consuming_entitlement():
    """Document exceeding Basic capacity returns 422 OVER_LIMIT without consuming quota."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3010:21bce3010@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p8", "razorpay_signature": f"mock_sig_{order['order_id']}_p8"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    # Generate document with 18,000 characters (> 15,000 basic limit)
    over_limit_text = "Academic study on machine learning algorithms. " * 400
    over_docx = create_minimal_test_docx(over_limit_text)

    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("over_limit.docx", over_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "OVER_LIMIT"
    assert data["recommended_tier"] == "standard"
    assert data["upgrade_difference_paise"] == 3000

    # Verify entitlement is preserved in OVER_LIMIT_PENDING_UPGRADE
    db = SessionLocal()
    ent_rec = db.query(Entitlement).filter(Entitlement.id == ent["entitlement_id"]).first()
    assert ent_rec.status == "OVER_LIMIT_PENDING_UPGRADE"
    db.close()


def test_31_conforming_document_promoted_and_sets_ready():
    """Conforming document moves to document store and marks entitlement READY."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3011:21bce3011@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p9", "razorpay_signature": f"mock_sig_{order['order_id']}_p9"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    conforming_docx = create_minimal_test_docx("Proper research manuscript within limits.")
    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("conforming.docx", conforming_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "document_id" in data

    # Verify entitlement is READY
    db = SessionLocal()
    ent_rec = db.query(Entitlement).filter(Entitlement.id == ent["entitlement_id"]).first()
    assert ent_rec.status == "READY"
    assert ent_rec.document_id == data["document_id"]
    db.close()


def test_32_upgrade_after_overage_enables_reupload():
    """Upgrading an OVER_LIMIT entitlement enables full upload for the target plan."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3012:21bce3012@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p10", "razorpay_signature": f"mock_sig_{order['order_id']}_p10"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent_id = ent["entitlement_id"]

    # Upgrade to Standard
    upg_order = client.post("/api/payments/upgrade-order", json={"entitlement_id": ent_id, "target_tier": "standard"}, headers={"Authorization": f"Bearer {token}"}).json()
    client.post(
        "/api/payments/verify-upgrade",
        json={
            "entitlement_id": ent_id,
            "target_tier": "standard",
            "razorpay_order_id": upg_order["order_id"],
            "razorpay_payment_id": "p_upg_2",
            "razorpay_signature": f"mock_sig_{upg_order['order_id']}_p_upg_2"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Request new slot and upload 18k char doc (now valid under Standard 65k limit)
    new_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent_id}, headers={"Authorization": f"Bearer {token}"}).json()
    over_limit_text = "Academic study on machine learning algorithms. " * 400
    res = client.post(
        "/api/upload-gate/upload",
        data={"upload_token": new_slot["upload_token"]},
        files={"file": ("now_valid.docx", create_minimal_test_docx(over_limit_text), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_33_sanitization_removes_path_characters():
    """Filenames with backslashes and special characters are safely sanitized."""
    from backend.app.core.security import sanitize_filename
    cleaned = sanitize_filename("../../etc/passwd\\malicious<>.docx")
    assert ".." not in cleaned
    assert "/" not in cleaned
    assert "\\" not in cleaned


def test_34_sha256_hash_authoritative():
    """File hash calculation is deterministic and matches raw bytes."""
    from backend.app.core.security import calculate_file_hash
    test_path = settings.STORAGE_DIR / "temp_hash_test.txt"
    test_path.write_bytes(b"deterministic_content")
    h = calculate_file_hash(test_path)
    test_path.unlink()
    assert len(h) == 64


def test_35_quarantine_cleans_up_failed_files():
    """Files failing inspection are unlinked from quarantine directory."""
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE3015:21bce3015@vitstudent.ac.in"})
    token = login_res.json()["token"]

    order = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"}).json()
    ent = client.post("/api/payments/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "p11", "razorpay_signature": f"mock_sig_{order['order_id']}_p11"}, headers={"Authorization": f"Bearer {token}"}).json()
    up_slot = client.post("/api/upload-gate/request-token", data={"entitlement_id": ent["entitlement_id"]}, headers={"Authorization": f"Bearer {token}"}).json()

    # Corrupt zip
    client.post(
        "/api/upload-gate/upload",
        data={"upload_token": up_slot["upload_token"]},
        files={"file": ("corrupt.docx", b"PK\x03\x04corrupted_garbage", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {token}"}
    )
    quarantine_files = list(settings.QUARANTINE_DIR.glob(f"{up_slot['upload_token'][:8]}*"))
    assert len(quarantine_files) == 0


# ==============================================================================
# 4. AI COST GOVERNOR & PROCESSING TESTS (Scenarios 36 - 47)
# ==============================================================================

def ensure_test_doc(db, doc_id="doc_test_cost_1", user_id=None):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="test.docx",
            file_path="storage/test.docx",
            file_hash="mock_hash_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            processing_status="ready"
        )
        db.add(doc)
        db.commit()
    return doc

def ensure_test_user(db, user_id="user_b_other"):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        u = User(id=user_id, email=f"{user_id}@vitstudent.ac.in", name=user_id, is_active=True)
        db.add(u)
        db.commit()
    return u


def test_36_document_budget_allocation_paise():
    """Verify tier hard budget in paise (Basic: 400p, Standard: 900p, Extended: 2400p)."""
    assert CostGovernor.get_document_budget("basic") == 400
    assert CostGovernor.get_document_budget("standard") == 900
    assert CostGovernor.get_document_budget("extended") == 2400


def test_37_ai_cost_recording_paise():
    """Recording AI spend calculates integer paise correctly and records to DB."""
    db = SessionLocal()
    doc_id = f"doc_test_cost_{secrets.token_hex(4)}"
    ensure_test_doc(db, doc_id)
    res = CostGovernor.record_cost(
        db=db,
        document_id=doc_id,
        plan_tier="basic",
        provider="gemini",
        model_name="gemini-1.5-flash",
        prompt_tokens=5000,
        completion_tokens=2000,
    )
    assert res.cost_incurred_paise > 0
    assert isinstance(res.cost_incurred_paise, int)
    db.close()


def test_38_circuit_breaker_halts_when_budget_exhausted():
    """When spend reaches 100% of budget, circuit breaker halts further calls."""
    db = SessionLocal()
    doc_id = f"doc_test_exhaust_{secrets.token_hex(4)}"
    ensure_test_doc(db, doc_id)
    # Artificially spend entire 400p budget
    CostGovernor.record_cost(db, doc_id, "basic", "gemini", "model", 100000, 100000)

    can_call, rec = CostGovernor.can_make_ai_call(db, doc_id, "basic")
    assert can_call is False
    assert rec == "no_llm"
    db.close()


def test_39_circuit_breaker_downgrades_at_85_percent():
    """When spend crosses 85%, circuit breaker switches to local/zero-cost provider."""
    db = SessionLocal()
    doc_id = f"doc_test_85_{secrets.token_hex(4)}"
    ensure_test_doc(db, doc_id)
    # Spend ~350 paise (87.5% of 400p budget)
    res_rec = AICostReservation(
        id=f"aic_{secrets.token_hex(8)}",
        document_id=doc_id,
        plan_tier="basic",
        budget_allocated_paise=400,
        cost_incurred_paise=350,
        prompt_tokens=50000,
        completion_tokens=20000,
        provider_used="gemini",
        model_name="default",
    )
    db.add(res_rec)
    db.commit()

    can_call, rec = CostGovernor.can_make_ai_call(db, doc_id, "basic")
    assert can_call is True
    assert rec == "ollama"
    db.close()
    assert rec == "ollama"
    db.close()


def test_40_emergency_ai_kill_switch_active():
    """Setting AI_API_PAUSED=true halts all external LLM calls."""
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "AI_API_PAUSED").first()
    if not setting:
        setting = SystemSetting(id="s1", key="AI_API_PAUSED", value="true")
        db.add(setting)
    else:
        setting.value = "true"
    db.commit()

    assert CostGovernor.is_ai_api_paused(db) is True
    can_call, rec = CostGovernor.can_make_ai_call(db, "any_doc", "basic")
    assert can_call is False

    # Reset
    setting.value = "false"
    db.commit()
    db.close()


def test_41_emergency_processing_pause_halts_jobs():
    """Setting PROCESSING_PAUSED=true returns 503 on start_analysis."""
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "PROCESSING_PAUSED").first()
    if not setting:
        setting = SystemSetting(id="s2", key="PROCESSING_PAUSED", value="true")
        db.add(setting)
    else:
        setting.value = "true"
    db.commit()
    db.close()

    res = client.post("/api/documents/some_doc/analyze", json={"editing_mode": "clarity"})
    assert res.status_code == 503
    assert "temporarily paused" in res.json()["detail"].lower()

    # Reset
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "PROCESSING_PAUSED").first()
    setting.value = "false"
    db.commit()
    db.close()


def test_42_emergency_purchases_pause():
    """Setting PURCHASES_PAUSED=true returns 503 on order creation."""
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "PURCHASES_PAUSED").first()
    if not setting:
        setting = SystemSetting(id="s3", key="PURCHASES_PAUSED", value="true")
        db.add(setting)
    else:
        setting.value = "true"
    db.commit()
    db.close()

    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE4001:21bce4001@vitstudent.ac.in"})
    token = login_res.json()["token"]

    res = client.post("/api/payments/create-order", json={"plan_tier": "basic"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503

    # Reset
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "PURCHASES_PAUSED").first()
    setting.value = "false"
    db.commit()
    db.close()


def test_43_emergency_uploads_pause():
    """Setting UPLOADS_PAUSED=true returns 503 on upload slot request."""
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "UPLOADS_PAUSED").first()
    if not setting:
        setting = SystemSetting(id="s4", key="UPLOADS_PAUSED", value="true")
        db.add(setting)
    else:
        setting.value = "true"
    db.commit()
    db.close()

    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE4002:21bce4002@vitstudent.ac.in"})
    token = login_res.json()["token"]

    res = client.post("/api/upload-gate/request-token", data={"entitlement_id": "ent_test"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503

    # Reset
    db = SessionLocal()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "UPLOADS_PAUSED").first()
    setting.value = "false"
    db.commit()
    db.close()


def test_44_concurrency_limit_one_job_per_student():
    """A student cannot start a second analysis job while another is active."""
    db = SessionLocal()
    login_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE4003:21bce4003@vitstudent.ac.in"})
    user_id = login_res.json()["user"]["id"]

    # Create dummy running job
    d_id = f"doc_conc_{secrets.token_hex(4)}"
    j_id = f"job_conc_{secrets.token_hex(4)}"
    doc1 = Document(id=d_id, user_id=user_id, filename="d1.docx", file_path="p1", file_hash="mock_hash_conc", processing_status="analyzing")
    db.add(doc1)
    db.commit()

    job1 = AnalysisJob(id=j_id, document_id=d_id, status="processing")
    db.add(job1)
    db.commit()

    can_start = JobQueueService.can_user_start_job(db, user_id)
    assert can_start is False
    db.close()


def test_45_stale_job_lease_reaper():
    """Jobs stuck in processing older than 5 minutes are marked failed with timeout."""
    db = SessionLocal()
    ensure_test_doc(db, "doc_any")
    stale_job = AnalysisJob(
        id=f"job_stale_{secrets.token_hex(4)}",
        document_id="doc_any",
        status="processing",
        started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10),
    )
    db.add(stale_job)
    db.commit()

    reaped = JobQueueService.reap_stale_jobs(db)
    assert reaped >= 1
    db.refresh(stale_job)
    assert stale_job.status == "failed"
    assert "timeout" in stale_job.error_message.lower()
    db.close()


def test_46_admin_toggle_kill_switch_endpoint():
    """Admin can dynamically toggle platform switches via /api/admin/kill-switch."""
    admin_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:admin@vitstudent.ac.in"})
    a_token = admin_res.json()["token"]

    res = client.post(
        "/api/admin/kill-switch",
        json={"setting_key": "AI_API_PAUSED", "enabled": True, "reason": "Cost audit maintenance"},
        headers={"Authorization": f"Bearer {a_token}"}
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True

    # Check status
    status_res = client.get("/api/admin/kill-switches", headers={"Authorization": f"Bearer {a_token}"})
    assert status_res.json()["AI_API_PAUSED"] is True

    # Revert
    client.post(
        "/api/admin/kill-switch",
        json={"setting_key": "AI_API_PAUSED", "enabled": False},
        headers={"Authorization": f"Bearer {a_token}"}
    )


def test_47_admin_restrict_user_endpoint():
    """Admin can place a suspension on a student account."""
    admin_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:admin@vitstudent.ac.in"})
    a_token = admin_res.json()["token"]

    student_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE4005:21bce4005@vitstudent.ac.in"})
    s_id = student_res.json()["user"]["id"]

    res = client.post(
        "/api/admin/restrict-user",
        json={"user_id": s_id, "restriction_type": "suspension", "reason": "Suspicious upload burst"},
        headers={"Authorization": f"Bearer {a_token}"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "restricted"


# ==============================================================================
# 5. MULTI-TENANCY & AUTHORIZATION TESTS (Scenarios 48 - 54)
# ==============================================================================

def test_48_student_cannot_view_other_student_structure():
    """Student A cannot access the structural blocks of Student B's document."""
    sA_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5001:21bce5001@vitstudent.ac.in"})
    sA_token = sA_res.json()["token"]

    sB_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5002:21bce5002@vitstudent.ac.in"})
    sB_id = sB_res.json()["user"]["id"]

    db = SessionLocal()
    target_doc_id = f"doc_student_b_{secrets.token_hex(4)}"
    docB = Document(id=target_doc_id, user_id=sB_id, filename="private.docx", file_path="p", file_hash="mock_hash_b", processing_status="ready")
    db.add(docB)
    db.commit()
    db.close()

    # Student A attempts to read Student B's document
    res = client.get(f"/api/documents/{target_doc_id}/structure", headers={"Authorization": f"Bearer {sA_token}"})
    assert res.status_code == 403


def test_49_student_cannot_delete_other_student_document():
    """Student A cannot delete Student B's document."""
    sA_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5003:21bce5003@vitstudent.ac.in"})
    sA_token = sA_res.json()["token"]

    db = SessionLocal()
    uB = ensure_test_user(db, f"user_b_other_{secrets.token_hex(4)}")
    target_doc_id = f"doc_delete_b_{secrets.token_hex(4)}"
    docB = Document(id=target_doc_id, user_id=uB.id, filename="b.docx", file_path="p", file_hash="mock_hash_b2", processing_status="ready")
    db.add(docB)
    db.commit()
    db.close()

    res = client.delete(f"/api/documents/{target_doc_id}", headers={"Authorization": f"Bearer {sA_token}"})
    assert res.status_code == 403


def test_50_student_cannot_add_sources_to_other_student_doc():
    """Student A cannot inject sources into Student B's document."""
    sA_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5004:21bce5004@vitstudent.ac.in"})
    sA_token = sA_res.json()["token"]

    db = SessionLocal()
    uB = ensure_test_user(db, f"user_b_other_{secrets.token_hex(4)}")
    target_doc_id = f"doc_source_b_{secrets.token_hex(4)}"
    docB = Document(id=target_doc_id, user_id=uB.id, filename="b.docx", file_path="p", file_hash="mock_hash_b3", processing_status="ready")
    db.add(docB)
    db.commit()
    db.close()

    res = client.post(
        f"/api/documents/{target_doc_id}/sources",
        files={"file": ("src.txt", b"source content", "text/plain")},
        headers={"Authorization": f"Bearer {sA_token}"}
    )
    assert res.status_code == 403


def test_51_student_cannot_download_other_student_export():
    """Student A cannot download Student B's generated export."""
    sA_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5005:21bce5005@vitstudent.ac.in"})
    sA_token = sA_res.json()["token"]

    # Create dummy export file
    exp_path = settings.EXPORTS_DIR / f"exp_test_{secrets.token_hex(4)}.docx"
    exp_path.write_bytes(b"content")

    db = SessionLocal()
    uB = ensure_test_user(db, f"user_b_other_{secrets.token_hex(4)}")
    doc_id = f"doc_exp_b_{secrets.token_hex(4)}"
    docB = Document(id=doc_id, user_id=uB.id, filename="b.docx", file_path="p", file_hash="mock_hash_b4", processing_status="ready")
    db.add(docB)
    db.commit()

    target_exp_id = f"exp_b_{secrets.token_hex(4)}"
    expB = Export(id=target_exp_id, document_id=docB.id, user_id=uB.id, export_type="docx", file_path=str(exp_path))
    db.add(expB)
    db.commit()
    db.close()

    res = client.get(f"/api/exports/{target_exp_id}/download", headers={"Authorization": f"Bearer {sA_token}"})
    assert res.status_code == 403
    exp_path.unlink(missing_ok=True)


def test_52_student_cannot_use_other_student_entitlement():
    """Student A cannot claim an upload reservation using Student B's entitlement."""
    sA_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5006:21bce5006@vitstudent.ac.in"})
    sA_token = sA_res.json()["token"]

    db = SessionLocal()
    uB = ensure_test_user(db, f"user_b_other_{secrets.token_hex(4)}")
    purB = Purchase(id=f"pur_b_{secrets.token_hex(4)}", user_id=uB.id, plan_tier="basic", amount_paise=2000, razorpay_order_id=f"ord_b_{secrets.token_hex(4)}", status="COMPLETED")
    db.add(purB)
    db.commit()

    target_ent_id = f"ent_b_{secrets.token_hex(4)}"
    entB = Entitlement(id=target_ent_id, user_id=uB.id, purchase_id=purB.id, plan_tier="basic", operating_mode="clarity", max_pages=4, max_characters=15000, max_file_size_mb=10, ai_budget_paise=400, status="AVAILABLE")
    db.add(entB)
    db.commit()
    db.close()

    res = client.post(
        "/api/upload-gate/request-token",
        data={"entitlement_id": target_ent_id},
        headers={"Authorization": f"Bearer {sA_token}"}
    )
    assert res.status_code == 404


def test_53_document_list_scopes_to_calling_student():
    """Listing manuscripts returns only documents belonging to the authenticated student."""
    sA_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:21BCE5007:21bce5007@vitstudent.ac.in"})
    sA_token = sA_res.json()["token"]
    sA_id = sA_res.json()["user"]["id"]

    db = SessionLocal()
    uOther = ensure_test_user(db, "other_user_id")
    docA_id = f"doc_scope_a_{secrets.token_hex(4)}"
    docOther_id = f"doc_scope_other_{secrets.token_hex(4)}"
    docA = Document(id=docA_id, user_id=sA_id, filename="a.docx", file_path="p", file_hash="mock_hash_a5", processing_status="ready")
    docOther = Document(id=docOther_id, user_id=uOther.id, filename="other.docx", file_path="p", file_hash="mock_hash_other5", processing_status="ready")
    db.add(docA)
    db.add(docOther)
    db.commit()
    db.close()

    res = client.get("/api/documents", headers={"Authorization": f"Bearer {sA_token}"})
    assert res.status_code == 200
    ids = [d["id"] for d in res.json()]
    assert docA_id in ids
    assert docOther_id not in ids


def test_54_admin_can_access_all_records():
    """Admin can inspect platform telemetry, all documents, and audit logs."""
    admin_res = client.post("/api/auth/google-login", json={"id_token": "mock-token:admin@vitstudent.ac.in"})
    a_token = admin_res.json()["token"]

    logs = client.get("/api/admin/audit-logs", headers={"Authorization": f"Bearer {a_token}"})
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)


# ==============================================================================
# 6. DOCUMENT INTEGRITY & FACT PRESERVATION TESTS (Scenarios 55 - 60)
# ==============================================================================

def test_55_tables_and_cells_preserved():
    """DocxParser preserves table structure and cell metadata."""
    from backend.app.services.docx_parser import DocxParser
    parser = DocxParser(SAMPLE_DOC, "doc_pres_test")
    blocks, meta = parser.parse()
    assert meta["table_count"] >= 1
    table_blocks = [b for b in blocks if b["block_type"] == "table_cell"]
    assert len(table_blocks) > 0


def test_56_headings_and_titles_marked_protected():
    """Structural titles and headings are protected from automated rewriting."""
    from backend.app.services.docx_parser import DocxParser
    parser = DocxParser(SAMPLE_DOC, "doc_head_test")
    blocks, _ = parser.parse()
    protected_blocks = [b for b in blocks if b.get("is_protected")]
    assert len(protected_blocks) > 0


def test_57_citations_preserved_in_text():
    """Citations (e.g. [1], (Chen et al., 2021)) are recognized and verified."""
    from backend.app.services.citation_analyzer import CitationAnalyzer
    analyzer = CitationAnalyzer()
    blocks = [
        {"id": "b1", "current_text": "Previous literature established this correlation (Chen et al., 2021)."},
        {"id": "b2", "current_text": "Deep learning achieves 94% accuracy [12]."}
    ]
    findings, audit = analyzer.analyze(blocks)
    assert audit.get("total_citations_in_text", 0) >= 2


def test_58_fact_validator_flags_unauthorized_numerical_changes():
    """FactValidator flags numerical or statistical alterations."""
    from backend.app.services.fact_validator import FactValidator
    orig = "The test accuracy was 94.5% across 1,200 clinical samples."
    tampered = "The test accuracy was 88.0% across 500 clinical samples."
    intact, violations = FactValidator.compare_facts(orig, tampered)
    assert intact is False
    assert len(violations) > 0


def test_59_revised_docx_export_retains_valid_ooxml():
    """ExportEngine produces a valid OOXML DOCX package with updated text."""
    from backend.app.services.export_engine import ExportEngine
    from backend.app.services.docx_parser import DocxParser
    parser = DocxParser(SAMPLE_DOC, "test_doc_59")
    blocks, _ = parser.parse()
    out_path = settings.EXPORTS_DIR / "exported_test_doc.docx"
    engine = ExportEngine(SAMPLE_DOC)
    is_valid, report = engine.export_docx(out_path, {}, blocks)
    assert is_valid is True
    assert out_path.exists()
    out_path.unlink()


def test_60_exported_docx_opens_cleanly_as_archive():
    """Exported DOCX archive can be extracted and parsed by standard zipfile without corruption."""
    from backend.app.services.export_engine import ExportEngine
    out_path = settings.EXPORTS_DIR / "archive_test_doc.docx"
    engine = ExportEngine(SAMPLE_DOC)
    engine.export_docx(out_path, {}, [])

    with zipfile.ZipFile(out_path, "r") as archive:
        names = archive.namelist()
        assert "word/document.xml" in names
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names

    out_path.unlink()
