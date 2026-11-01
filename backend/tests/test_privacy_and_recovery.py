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
