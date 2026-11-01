import os
import shutil
from pathlib import Path
import pytest
import docx
from backend.app.services.docx_parser import DocxParser
from backend.app.services.structure_preserver import StructurePreserver
from backend.app.services.export_engine import ExportEngine

SAMPLE_DOC = Path("sample_documents/academic_research_report.docx")

def test_docx_round_trip(tmp_path):
    """
    Test A: DOCX round-trip.
    Upload and export without making edits.
    Exported document must preserve its text, table count, paragraph structure, and validity.
    """
    assert SAMPLE_DOC.exists(), "Sample doc must exist"
    target_path = tmp_path / "round_trip_export.docx"

    parser = DocxParser(SAMPLE_DOC, "test_doc_001")
    blocks, meta = parser.parse()
    assert len(blocks) > 0
    assert meta["table_count"] == 1

    preserver = StructurePreserver(SAMPLE_DOC)
    success, report = preserver.apply_edits_and_export(
        target_path=target_path,
        block_updates={},  # zero edits
        blocks_metadata=blocks
    )

    assert success is True
    assert report["valid"] is True
    assert report["archive_valid"] is True
    assert report["reopened_successfully"] is True
    assert report["table_count"] == 1
    assert report["paragraph_count_match"] is True

def test_paragraph_revision_preserves_unrelated(tmp_path):
    """
    Test B: Paragraph revision.
    Change a single paragraph and verify that unrelated paragraphs,
    tables, and embedded structure remain intact.
    """
    target_path = tmp_path / "single_paragraph_revised.docx"
    parser = DocxParser(SAMPLE_DOC, "test_doc_002")
    blocks, meta = parser.parse()

    # Find the methodology paragraph
    target_block = None
    for b in blocks:
        if "combination of contextualized token embeddings" in b["original_text"]:
            target_block = b
            break
    assert target_block is not None

    new_text = target_block["original_text"].replace(
        "We formalize our feature representation through a combination of contextualized token embeddings and structural graph relations.",
        "We formalize our architectural representation through dense contextual token embeddings and graph relations.",
    )
    block_updates = {target_block["id"]: new_text}

    preserver = StructurePreserver(SAMPLE_DOC)
    success, report = preserver.apply_edits_and_export(
        target_path=target_path,
        block_updates=block_updates,
        blocks_metadata=blocks
    )

    assert success is True
    assert report["valid"] is True

    # Reopen exported file and inspect
    revised_doc = docx.Document(str(target_path))
    # Check that new text is in the doc
    all_texts = [p.text for p in revised_doc.paragraphs]
    assert new_text in all_texts

    # Check that abstract and references are completely untouched
    assert any("Accurate classification of complex textual representations" in t for t in all_texts)
    assert any("Foundations of Modern Plagiarism Detection" in t for t in all_texts)
    assert len(revised_doc.tables) == 1

def test_pdf_export_conversion(tmp_path):
    """
    Test H: Export PDF.
    Verify that LibreOffice headless converts the DOCX into a valid, readable PDF.
    """
    target_docx = tmp_path / "test_report.docx"
    target_pdf = tmp_path / "test_report.pdf"
    shutil.copyfile(SAMPLE_DOC, target_docx)

    engine = ExportEngine(SAMPLE_DOC)
    success, info = engine.export_pdf(target_docx, target_pdf)
    assert success is True, f"PDF export failed: {info}"
    assert target_pdf.exists()
    assert info["page_count"] >= 1
    assert info["file_size_bytes"] > 0
