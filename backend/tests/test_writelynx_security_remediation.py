import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings

client = TestClient(app)

SAMPLE_DOC = Path("sample_documents/academic_research_report.docx")


# ==============================================================================
# 1. AUTHENTICATION & VIT INSTITUTIONAL DOMAIN ENFORCEMENT
# ==============================================================================

def test_auth_vit_student_domain_enforcement():
    """Verify that only official @vitstudent.ac.in Google accounts are accepted."""
    # 1. Personal Gmail must be rejected with 403 Forbidden
    res_gmail = client.post(
        "/api/auth/google-login",
        json={"id_token": "mock-token:john.doe@gmail.com"}
    )
    assert res_gmail.status_code == 403
    assert "restricted to Vellore Institute of Technology" in res_gmail.json()["detail"]

    # 2. Other universities must be rejected
    res_mit = client.post(
        "/api/auth/google-login",
        json={"id_token": "mock-token:student@mit.edu"}
    )
    assert res_mit.status_code == 403

    # 3. Legitimate VIT student succeeds
    res_vit = client.post(
        "/api/auth/google-login",
        json={"id_token": "mock-token:21bce1001:21bce1001@vitstudent.ac.in"}
    )
    assert res_vit.status_code == 200
    data = res_vit.json()
    assert "token" in data
    assert data["user"]["email"] == "21bce1001@vitstudent.ac.in"
    assert data["user"]["registration_number"] == "21BCE1001"


def test_auth_empty_token_rejection():
    """Missing or empty token must return 401."""
    res = client.post("/api/auth/google-login", json={"id_token": "   "})
    assert res.status_code == 401


# ==============================================================================
# 2. SETTINGS API LOCKDOWN & SSRF PROTECTION (P0.3)
# ==============================================================================

def test_settings_lockdown_anonymous_rejected():
    """Anonymous callers must not be able to mutate AI settings."""
    anon_client = TestClient(app)
    res = anon_client.post("/api/settings", json={"default_llm_provider": "openai"})
    assert res.status_code in (401, 403)


def test_settings_lockdown_student_rejected():
    """Ordinary students must not be able to mutate server-wide AI settings."""
    res_login = client.post(
        "/api/auth/google-login",
        json={"id_token": "mock-token:21bce1002:21bce1002@vitstudent.ac.in"}
    )
    token = res_login.json()["token"]

    res_post = client.post(
        "/api/settings",
        json={"default_llm_provider": "openai"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_post.status_code == 403
    assert "Administrative privileges required" in res_post.json()["detail"]

    # Student cannot run provider diagnostic
    res_diag = client.get(
        "/api/settings/test-provider/gemini",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_diag.status_code == 403


def test_settings_ssrf_protection():
    """Admin updating ollama_host with restricted cloud metadata or internal IP is blocked."""
    # Login as admin
    res_login = client.post(
        "/api/auth/google-login",
        json={"id_token": "mock-token:admin@vitstudent.ac.in"}
    )
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt SSRF to AWS/GCP cloud metadata IP
    res_ssrf = client.post(
        "/api/settings",
        json={"ollama_host": "http://169.254.169.254/latest/meta-data/"},
        headers=headers
    )
    assert res_ssrf.status_code == 400
    assert "restricted internal subnet" in res_ssrf.json()["detail"]


# ==============================================================================
# 3. MULTI-TENANCY ISOLATION (STUDENT A VS. STUDENT B) (P0.2)
# ==============================================================================

def test_multi_tenancy_document_isolation():
    """
    Student A creates a document.
    Student B must NOT be able to view, analyze, export, delete, or modify Student A's document.
    """
    # 1. Login Student A
    res_a = client.post("/api/auth/google-login", json={"id_token": "mock-token:21bce1010@vitstudent.ac.in"})
    token_a = res_a.json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Login Student B
    res_b = client.post("/api/auth/google-login", json={"id_token": "mock-token:21bce1020@vitstudent.ac.in"})
    token_b = res_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Student A uploads Document
    with open(SAMPLE_DOC, "rb") as f:
        upload_res = client.post(
            "/api/documents/upload",
            files={"file": ("report_a.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=headers_a
        )
    assert upload_res.status_code == 200
    doc_id_a = upload_res.json()["id"]

    # 4. Student B attempts to access Document A metadata -> 403
    res_get = client.get(f"/api/documents/{doc_id_a}", headers=headers_b)
    assert res_get.status_code == 403
    assert "permission to access or modify" in res_get.json()["detail"]

    # 5. Student B attempts to read structure -> 403
    res_struct = client.get(f"/api/documents/{doc_id_a}/structure", headers=headers_b)
    assert res_struct.status_code == 403

    # 6. Student B attempts to trigger analysis -> 403
    res_analyze = client.post(
        f"/api/documents/{doc_id_a}/analyze",
        json={"editing_mode": "academic_revision"},
        headers=headers_b
    )
    assert res_analyze.status_code == 403

    # 7. Student B attempts to read analysis -> 403
    res_analysis = client.get(f"/api/documents/{doc_id_a}/analysis", headers=headers_b)
    assert res_analysis.status_code == 403

    # 8. Student B attempts to export DOCX -> 403
    res_exp_docx = client.post(f"/api/documents/{doc_id_a}/export/docx", headers=headers_b)
    assert res_exp_docx.status_code == 403

    # 9. Student B attempts to export PDF -> 403
    res_exp_pdf = client.post(f"/api/documents/{doc_id_a}/export/pdf", headers=headers_b)
    assert res_exp_pdf.status_code == 403

    # 10. Student B attempts to delete Document A -> 403
    res_del = client.delete(f"/api/documents/{doc_id_a}", headers=headers_b)
    assert res_del.status_code == 403

    # 11. Anonymous access is strictly rejected with 401
    anon_client = TestClient(app)
    assert anon_client.get(f"/api/documents/{doc_id_a}").status_code == 401
    assert anon_client.get("/api/documents").status_code == 401


# ==============================================================================
# 4. PAYMENT & SINGLE-USE ENTITLEMENT LIFECYCLE (P2.1 - P2.5)
# ==============================================================================

def test_payment_entitlement_and_upload_gate_lifecycle():
    """Verify purchase -> entitlement minting -> upload authorization -> single-use consumption."""
    # 1. Login Student
    res_login = client.post("/api/auth/google-login", json={"id_token": "mock-token:21bce1030@vitstudent.ac.in"})
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Order for Basic Plan (₹20 = 2000 paise)
    res_order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers=headers
    )
    assert res_order.status_code == 200
    order = res_order.json()
    assert order["amount_paise"] == 2000
    assert order["amount_rupees"] == 20

    # 3. Verify Payment
    res_verify = client.post(
        "/api/payments/verify",
        json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": "pay_test_12345",
            "razorpay_signature": f"mock_sig_{order['order_id']}_pay_test_12345",
        },
        headers=headers
    )
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    entitlement_id = verify_data["entitlement_id"]
    assert entitlement_id is not None
    assert verify_data["plan_tier"] == "basic"

    # 4. Request Upload Reservation Token
    res_slot = client.post(
        "/api/upload-gate/request-token",
        data={"entitlement_id": entitlement_id},
        headers=headers
    )
    assert res_slot.status_code == 200
    upload_token = res_slot.json()["upload_token"]

    # 5. Upload Document through Quarantine Gate
    with open(SAMPLE_DOC, "rb") as f:
        res_upload = client.post(
            "/api/upload-gate/upload",
            data={"upload_token": upload_token},
            files={"file": ("quarantine_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=headers
        )
    assert res_upload.status_code == 200
    assert res_upload.json()["status"] == "success"

    # 6. Reusing the same upload token must fail with 409 Conflict
    with open(SAMPLE_DOC, "rb") as f:
        res_reuse = client.post(
            "/api/upload-gate/upload",
            data={"upload_token": upload_token},
            files={"file": ("quarantine_test2.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=headers
        )
    assert res_reuse.status_code == 409
    assert "already been consumed" in res_reuse.json()["detail"]


def test_upgrade_binding_validation():
    """Verify that an upgrade purchase strictly binds to the entitlement and requires exact delta."""
    res_login = client.post("/api/auth/google-login", json={"id_token": "mock-token:21bce1040@vitstudent.ac.in"})
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Buy Basic Plan (₹20 = 2000 paise)
    res_order = client.post(
        "/api/payments/create-order",
        json={"plan_tier": "basic", "operating_mode": "academic_revision"},
        headers=headers
    )
    order = res_order.json()
    res_verify = client.post(
        "/api/payments/verify",
        json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": "pay_test_bas",
            "razorpay_signature": f"mock_sig_{order['order_id']}_pay_test_bas",
        },
        headers=headers
    )
    ent_id = res_verify.json()["entitlement_id"]

    # Create Upgrade Order to Standard (Basic ₹20 -> Standard ₹50: diff = ₹30 / 3000 paise)
    res_upg = client.post(
        "/api/payments/create-upgrade-order",
        json={"entitlement_id": ent_id, "target_tier": "standard"},
        headers=headers
    )
    assert res_upg.status_code == 200
    upg_order = res_upg.json()
    assert upg_order["upgrade_amount_paise"] == 3000
    assert upg_order["upgrade_amount_rupees"] == 30

    # Verify Upgrade
    res_fulfill = client.post(
        "/api/payments/verify-upgrade",
        json={
            "entitlement_id": ent_id,
            "target_tier": "standard",
            "razorpay_order_id": upg_order["order_id"],
            "razorpay_payment_id": "pay_upg_test",
            "razorpay_signature": f"mock_sig_{upg_order['order_id']}_pay_upg_test",
        },
        headers=headers
    )
    assert res_fulfill.status_code == 200
    assert res_fulfill.json()["status"] == "upgraded"
    assert res_fulfill.json()["plan_tier"] == "standard"


# ==============================================================================
# 5. DOCUMENT PRESERVATION VALIDATION (PRIORITY 9)
# ==============================================================================

def test_preservation_validation_revised_artifact():
    """Verify that validation compares the original DOCX with the actual revised artifact."""
    res_login = client.post("/api/auth/google-login", json={"id_token": "mock-token:21bce1050@vitstudent.ac.in"})
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with open(SAMPLE_DOC, "rb") as f:
        res_upload = client.post(
            "/api/documents/upload",
            files={"file": ("val_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=headers
        )
    doc_id = res_upload.json()["id"]

    res_val = client.post(f"/api/documents/{doc_id}/validate", headers=headers)
    assert res_val.status_code == 200
    report = res_val.json()
    assert report["archive_valid"] is True
    assert report["protected_facts_intact"] is True
    assert report["citation_integrity_intact"] is True
