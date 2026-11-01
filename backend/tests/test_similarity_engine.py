import pytest
from backend.app.services.similarity_engine import SimilarityEngine

def test_exact_overlap_detection():
    """Test E: Exact match against supplied source."""
    engine = SimilarityEngine(ngram_size=5)

    source_text = (
        "Verbatim textual reproduction undermines academic transparency and scholarly merit. "
        "Traditional text comparison systems rely heavily on string distance heuristics and character n-grams. "
        "When passages are duplicated without clear attribution, readers cannot distinguish the author's primary contributions."
    )

    sources = [{
        "id": "src_chen",
        "title": "Chen and Zhao Paper",
        "source_type": "upload_docx",
        "extracted_text": source_text
    }]

    # A report block that reproduces source passage verbatim without citation
    blocks = [{
        "id": "b_overlap",
        "document_id": "doc_eval",
        "block_index": 1,
        "section_id": "Related Work",
        "block_type": "paragraph",
        "current_text": "Traditional text comparison systems rely heavily on string distance heuristics and character n-grams."
    }]

    findings, metrics = engine.analyze_document_against_sources(blocks, sources)
    assert len(findings) > 0
    assert metrics["matching_passages_count"] == 1
    assert metrics["unattributed_overlap_count"] == 1
    assert findings[0]["finding_type"] == "unattributed_overlap"
    assert findings[0]["source_id"] == "src_chen"

def test_common_terminology_not_plagiarized():
    """
    Test F: Ensure common technical expressions are not automatically classified as plagiarism.
    """
    engine = SimilarityEngine(ngram_size=5)
    sources = [{
        "id": "src_any",
        "title": "Any Prior Paper",
        "source_type": "upload_docx",
        "extracted_text": "In this paper we propose an algorithm for computer vision and natural language processing."
    }]

    # Block with common academic convention
    blocks = [{
        "id": "b_common",
        "document_id": "doc_eval",
        "block_index": 0,
        "section_id": "Abstract",
        "block_type": "paragraph",
        "current_text": "In this paper we propose an experimental setup for natural language processing."
    }]

    findings, metrics = engine.analyze_document_against_sources(blocks, sources)
    # If classified, it should be categorized as 'common_terminology' with severity 'info', NOT unattributed overlap
    for f in findings:
        assert f["finding_type"] != "unattributed_overlap"
    assert metrics["unattributed_overlap_count"] == 0
