import pytest
from backend.app.services.citation_analyzer import CitationAnalyzer

def test_citation_integrity_and_broken_links():
    analyzer = CitationAnalyzer()
    blocks = [
        {
            "id": "b_01",
            "document_id": "doc_1",
            "section_id": "Introduction",
            "block_type": "paragraph",
            "current_text": "Prior work examined text classification using neural networks [1] and graph models [4]."
        },
        {
            "id": "b_02",
            "document_id": "doc_1",
            "section_id": "References",
            "block_type": "reference_entry",
            "current_text": "[1] J. Smith, Neural Methods, 2021."
        },
        {
            "id": "b_03",
            "document_id": "doc_1",
            "section_id": "References",
            "block_type": "reference_entry",
            "current_text": "[2] M. Taylor, Graph Networks, 2022."
        }
    ]

    findings, audit = CitationAnalyzer().analyze(blocks)

    # In-text citation [4] has no bibliography entry
    missing_entries = audit["missing_bibliography_entries"]
    assert 4 in missing_entries
    assert any(f["finding_type"] == "missing_citation" and "[4]" in f["matched_text"] for f in findings)

    # Reference [2] in bibliography is never cited
    uncited_entries = audit["uncited_bibliography_entries"]
    assert 2 in uncited_entries
    assert any(f["match_type"] == "uncited_reference" and "b_03" in f["block_id"] for f in findings)

def test_quotation_without_attribution():
    analyzer = CitationAnalyzer()
    blocks = [
        {
            "id": "b_quote",
            "document_id": "doc_2",
            "section_id": "Literature Review",
            "block_type": "paragraph",
            "current_text": "The authors argued that \"uncontrolled automated rewriting leads to severe degradation of scholarly rigor\" without any citation."
        }
    ]
    findings, _ = analyzer.analyze(blocks)
    assert any(f["match_type"] == "quotation_without_attribution" for f in findings)
