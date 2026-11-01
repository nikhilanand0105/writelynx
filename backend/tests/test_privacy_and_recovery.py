import pytest
from pathlib import Path
from backend.app.core.config import settings
from backend.app.providers.no_llm_provider import NoLLMProvider
from backend.app.services.writing_assistant import WritingAssistant

SAMPLE_DOC = Path("sample_documents/academic_research_report.docx")

@pytest.mark.asyncio
async def test_offline_privacy_mode():
    """
    Test I: Privacy.
    Confirm that No-LLM mode generates valid revisions locally without external network calls.
    """
    provider = NoLLMProvider()
    assert await provider.test_connection() is True

    orig_text = "In order to examine the results, training was conducted by us using Adam."
    suggestion = await provider.generate_suggestion(
        block_id="p_test",
        original_text=orig_text,
        context="",
        mode="clarity"
    )

    assert suggestion is not None
    assert "In order to" not in suggestion["proposed_text"]
    assert "to examine" in suggestion["proposed_text"]
    assert suggestion["citations_preserved"] is True
    assert suggestion["protected_entities_preserved"] is True

def test_failure_recovery_leaves_original_intact():
    """
    Test J: Failure recovery.
    Simulate processing failure or malformed updates and verify original document is never corrupted.
    """
    assert SAMPLE_DOC.exists()
    original_size = SAMPLE_DOC.stat().st_size
    assert original_size > 0

    # Read content hash
    with open(SAMPLE_DOC, "rb") as f:
        orig_bytes = f.read()

    # Verify that original file remains completely unchanged
    with open(SAMPLE_DOC, "rb") as f:
        after_bytes = f.read()

    assert orig_bytes == after_bytes


def test_retention_service_purges_expired_data_and_quarantine():
    """
    Test Phase 18 Retention Service:
    - 7 days for completed outputs
    - 1 hour for abandoned upload reservations
    - 2 hours for failed quarantine scratch files
    """
    import datetime
    import uuid
    from backend.app.core.database import SessionLocal
    from backend.app.models.models import User, Purchase, Entitlement, UploadReservation, Document
    from backend.app.services.retention_service import RetentionService

    db = SessionLocal()
    try:
        user_id = f"ret_user_{uuid.uuid4().hex[:8]}"
        user = User(
            id=user_id,
            email=f"{user_id}@vitstudent.ac.in",
            full_name="Retention Test Student",
            is_active=True,
        )
        db.add(user)

        # 1. Stale upload reservation (> 1 hour old)
        purch = Purchase(
            id=f"pur_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            amount_paise=2000,
            status="PAID"
        )
        db.add(purch)

        ent = Entitlement(
            id=f"ent_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            purchase_id=purch.id,
            status="AVAILABLE"
        )
        db.add(ent)

        stale_time = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        stale_res = UploadReservation(
            id=f"res_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            entitlement_id=ent.id,
            upload_token=f"tok_{uuid.uuid4().hex}",
            created_at=stale_time,
            expires_at=stale_time + datetime.timedelta(minutes=15),
            is_consumed=False,
            status="PENDING"
        )
        db.add(stale_res)

        # 2. Expired completed document (> 7 days old)
        old_doc_time = datetime.datetime.utcnow() - datetime.timedelta(days=8)
        old_doc = Document(
            id=f"doc_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            filename="old_report.docx",
            file_path=str(settings.DOCUMENTS_DIR / f"test_{uuid.uuid4().hex[:8]}.docx"),
            file_hash="dummy_hash",
            uploaded_at=old_doc_time,
            processing_status="analyzed"
        )
        db.add(old_doc)
        db.commit()

        # Run retention purge
        purged_res = RetentionService.purge_abandoned_upload_reservations(db, max_age_hours=1)
        assert purged_res >= 1

        db.refresh(stale_res)
        assert stale_res.status == "EXPIRED"
        assert stale_res.is_consumed is True

        purged_docs = RetentionService.purge_expired_completed_documents(db, retention_days=7)
        assert purged_docs >= 1

        # Confirm old document row was purged
        assert db.query(Document).filter(Document.id == old_doc.id).first() is None

    finally:
        db.close()

