import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base
from backend.app.models.models import Document, DocumentBlock, EditSuggestion, RevisionEvent
from backend.app.services.revision_manager import RevisionManager

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_revision_controls_lifecycle(test_db):
    """
    Test G: Revision controls.
    Accept, reject, manual revise, and restore edits.
    """
    # Create test document and block
    doc = Document(id="doc_rev_test", filename="report.docx", file_path="dummy.docx", file_hash="hash123")
    block = DocumentBlock(
        id="blk_01",
        document_id="doc_rev_test",
        block_index=0,
        original_text="Due to the fact that prior systems failed, we proposed a new model.",
        current_text="Due to the fact that prior systems failed, we proposed a new model."
    )
    sug = EditSuggestion(
        id="sug_01",
        document_id="doc_rev_test",
        block_id="blk_01",
        issue_type="clarity",
        original_text="Due to the fact that prior systems failed, we proposed a new model.",
        proposed_text="Because prior systems failed, we proposed a new model.",
        reason="Streamlined wordiness",
        review_status="pending"
    )
    test_db.add(doc)
    test_db.add(block)
    test_db.add(sug)
    test_db.commit()

    # 1. Accept suggestion
    res = RevisionManager.accept_suggestion(test_db, "sug_01")
    assert res["success"] is True
    assert block.current_text == "Because prior systems failed, we proposed a new model."
    assert sug.review_status == "accepted"

    # Verify event logged
    events = test_db.query(RevisionEvent).filter(RevisionEvent.block_id == "blk_01").all()
    assert len(events) == 1
    assert events[0].event_type == "accept_suggestion"

    # 2. Restore to original
    res_restore = RevisionManager.restore_block_original(test_db, "blk_01")
    assert res_restore["success"] is True
    assert block.current_text == "Due to the fact that prior systems failed, we proposed a new model."

    # 3. Manual edit
    res_manual = RevisionManager.revise_block_manually(test_db, "blk_01", "Since prior architectures failed, we devised a novel model.")
    assert res_manual["success"] is True
    assert block.current_text == "Since prior architectures failed, we devised a novel model."

    all_events = test_db.query(RevisionEvent).all()
    assert len(all_events) == 3
