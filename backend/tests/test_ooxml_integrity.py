"""Regression coverage for destructive export bugs, using real OOXML fixtures."""
import copy
import csv
import shutil
import zipfile
from pathlib import Path
from unittest.mock import Mock

import docx
import pymupdf
import pytest
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from backend.app.services.docx_parser import DocxParser
from backend.app.services.export_engine import ExportEngine
from backend.app.services.structure_preserver import StructurePreserver


def _fixture(tmp_path):
    path = tmp_path / "original.docx"
    document = docx.Document()
    document.add_heading("Methods", 1)
    document.add_paragraph("")
    paragraph = document.add_paragraph()
    paragraph.add_run("In order to evaluate ")
    paragraph.add_run("robustness").bold = True
    paragraph.add_run(", we used 6 features and a 30-bar window [1].")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Feature"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Selected features"
    table.cell(1, 1).text = "6"
    document.add_paragraph("Following the table, this passage can be revised independently.")
    document.add_paragraph("Repeated passage.")
    document.add_paragraph("Repeated passage.")
    document.sections[0].header.paragraphs[0].text = "Immutable header"
    document.sections[0].footer.paragraphs[0].text = "Immutable footer"
    document.save(path)
    blocks, metadata = DocxParser(path, "integrity").parse()
    return path, blocks, metadata


def _part(path, name="word/document.xml"):
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def test_no_edit_round_trip_is_byte_identical_and_reports_real_checks(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    output = tmp_path / "copy.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {}, blocks)
    assert success, report
    assert output.read_bytes() == original.read_bytes()
    assert report["byte_identical"]
    assert report["relationships_valid"]
    assert report["media_intact"]
    assert report["changed_package_parts"] == []


def test_edits_after_tables_repeated_paragraphs_and_styled_runs_are_exact(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    first = next(b for b in blocks if b["original_text"].startswith("In order"))
    after = next(b for b in blocks if b["original_text"].startswith("Following"))
    repeat = [b for b in blocks if b["original_text"] == "Repeated passage."][-1]
    updates = {
        first["id"]: first["original_text"].replace("In order to evaluate", "To evaluate"),
        after["id"]: "After the table, this passage was revised independently.",
        repeat["id"]: "Only the latter repeated passage was revised.",
    }
    output = tmp_path / "patched.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, updates, blocks)
    assert success, report
    assert report["changed_package_parts"] == ["word/document.xml"]
    revised = docx.Document(output)
    assert revised.paragraphs[2].text == updates[first["id"]]
    assert next(r for r in revised.paragraphs[2].runs if r.bold).text == "robustness"
    assert revised.paragraphs[-2].text == "Repeated passage."
    assert revised.paragraphs[-1].text == updates[repeat["id"]]
    assert revised.paragraphs[3].text == updates[after["id"]]
    assert _part(original, "word/header1.xml") == _part(output, "word/header1.xml")
    assert _part(original, "word/footer1.xml") == _part(output, "word/footer1.xml")


def test_table_indices_and_cells_are_stable_and_editable(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    cell = next(b for b in blocks if b["original_text"] == "Selected features")
    assert cell["structure_metadata"]["table_index"] == 0
    output = tmp_path / "table.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {cell["id"]: "Chosen features"}, blocks)
    assert success, report
    assert docx.Document(output).tables[0].cell(1, 0).text == "Chosen features"


def test_legacy_paragraph_metadata_after_table_is_resolved(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    after = next(b for b in blocks if b["original_text"].startswith("Following"))
    for block in blocks:
        block["structure_metadata"].pop("xml_path")
    output = tmp_path / "legacy.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {after["id"]: "The passage after the table was revised."}, blocks)
    assert success, report
    assert docx.Document(output).paragraphs[3].text == "The passage after the table was revised."


@pytest.mark.parametrize("replacement", [
    "In order to evaluate robustness, we used 7 features and a 30-bar window [1].",
    "In order to evaluate robustness, we used 6 features and a 30-bar window.",
    "In order to evaluate robustness, we used 6 features and a 30-bar window [1]. Accuracy was 99%.",
])
def test_facts_and_citations_cannot_change_silently(tmp_path, replacement):
    original, blocks, _ = _fixture(tmp_path)
    target = next(b for b in blocks if b["original_text"].startswith("In order"))
    original_bytes = original.read_bytes()
    output = tmp_path / "rejected.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {target["id"]: replacement}, blocks)
    assert not success
    assert "Author approval" in report["blocked_edits"][0]["reason"]
    assert not output.exists()
    assert original.read_bytes() == original_bytes


def test_explicit_fact_approval_is_reported_not_misrepresented(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    target = next(b for b in blocks if b["original_text"].startswith("In order"))
    target["allow_fact_changes"] = True
    output = tmp_path / "approved.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {target["id"]: target["original_text"].replace("6 features", "7 features")}, blocks)
    assert success, report
    assert report["approved_fact_changes"]
    assert report["protected_facts_intact"] is False
    assert report["citation_integrity_intact"] is True


def test_attempt_to_overwrite_original_and_unknown_block_are_rejected(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    before = original.read_bytes()
    assert not StructurePreserver(original).apply_edits_and_export(original, {}, blocks)[0]
    output = tmp_path / "unknown.docx"
    assert not StructurePreserver(original).apply_edits_and_export(output, {"absent": "x"}, blocks)[0]
    assert not output.exists()
    assert original.read_bytes() == before


def test_failed_export_preserves_previous_destination(tmp_path):
    original, blocks, _ = _fixture(tmp_path)
    output = tmp_path / "existing.docx"
    output.write_bytes(b"existing export")
    target = next(b for b in blocks if "6 features" in b["original_text"])
    success, _ = StructurePreserver(original).apply_edits_and_export(output, {target["id"]: "A fabricated 99% result."}, blocks)
    assert not success
    assert output.read_bytes() == b"existing export"


@pytest.mark.parametrize("tag", ["w:drawing", "w:fldChar", "w:footnoteReference", "w:bookmarkStart", "m:oMath"])
def test_complex_paragraphs_remain_intact_and_read_only(tmp_path, tag):
    original = tmp_path / "complex.docx"
    document = docx.Document()
    p = document.add_paragraph("Complex material stays intact.")
    p.runs[0]._r.append(OxmlElement(tag))
    document.save(original)
    blocks, _ = DocxParser(original, "complex").parse()
    assert blocks[0]["structure_metadata"]["editable"] is False
    output = tmp_path / "complex-export.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {blocks[0]["id"]: "Edited complex material."}, blocks)
    assert not success
    assert "read-only construct" in report["blocked_edits"][0]["reason"]
    success, _ = StructurePreserver(original).apply_edits_and_export(output, {}, blocks)
    assert success
    assert original.read_bytes() == output.read_bytes()


def test_merged_cells_are_not_duplicated_and_multi_paragraph_cells_are_preserved(tmp_path):
    original = tmp_path / "merged.docx"
    document = docx.Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "Merged header"
    table.cell(1, 0).text = "First paragraph"
    table.cell(1, 0).add_paragraph("Second paragraph")
    document.save(original)
    blocks, _ = DocxParser(original, "merged").parse()
    assert sum(b["original_text"] == "Merged header" for b in blocks) == 1
    multiple = next(b for b in blocks if "First paragraph" in b["original_text"])
    assert multiple["structure_metadata"]["editable"] is False
    success, _ = StructurePreserver(original).apply_edits_and_export(tmp_path / "bad.docx", {multiple["id"]: "Flattened"}, blocks)
    assert not success


def test_hyperlink_text_is_extracted_and_unchanged_when_surrounding_text_edits(tmp_path):
    original = tmp_path / "links.docx"
    document = docx.Document()
    p = document.add_paragraph("In order to inspect ")
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), document.part.relate_to("https://example.org/paper", RT.HYPERLINK, is_external=True))
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "the paper"
    run.append(text)
    hyperlink.append(run)
    p._p.append(hyperlink)
    p.add_run(", consult the source.")
    document.save(original)
    blocks, _ = DocxParser(original, "links").parse()
    assert "the paper" in blocks[0]["original_text"]
    output = tmp_path / "link-edited.docx"
    success, report = StructurePreserver(original).apply_edits_and_export(output, {blocks[0]["id"]: "To inspect the paper, consult the source."}, blocks)
    assert success, report
    assert _part(original, "word/_rels/document.xml.rels") == _part(output, "word/_rels/document.xml.rels")
    success, _ = StructurePreserver(original).apply_edits_and_export(tmp_path / "bad-link.docx", {blocks[0]["id"]: "In order to inspect changed label, consult the source."}, blocks)
    assert not success


def test_validation_detects_missing_media_and_changed_headers(tmp_path):
    original, _, _ = _fixture(tmp_path)
    output = tmp_path / "corrupt.docx"
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(output, "w") as dest:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/header1.xml":
                data = data.replace(b"Immutable header", b"Corrupted header")
            dest.writestr(item, data)
    report = StructurePreserver(original).validate_preservation(original, output)
    assert report["valid"] is False
    assert report["unchanged_parts_intact"] is False


def test_validation_detects_changed_numbers_without_export_approval(tmp_path):
    original, _, _ = _fixture(tmp_path)
    output = tmp_path / "changed.docx"
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(output, "w") as dest:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = data.replace(b"6 features", b"7 features")
            dest.writestr(item, data)
    report = StructurePreserver(original).validate_preservation(original, output)
    assert not report["valid"]
    assert not report["protected_facts_intact"]
    assert report["protected_fact_violations"]


def test_pdf_validation_renders_blank_and_text_pages(tmp_path):
    path = tmp_path / "pages.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 50), "Real rendered text")
        pdf.new_page()
        pdf.save(path)
    result = ExportEngine.validate_pdf(path)
    assert result["valid"]
    assert result["page_count"] == result["rendered_page_count"] == 2
    assert result["blank_page_count"] == 1
    assert result["warnings"]


def test_failed_converter_cannot_reuse_stale_pdf(tmp_path, monkeypatch):
    original, _, _ = _fixture(tmp_path)
    stale = tmp_path / "original.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), "Stale output")
        pdf.save(stale)
    before = stale.read_bytes()
    monkeypatch.setattr("backend.app.services.export_engine.shutil.which", lambda _: "/fake/soffice")
    monkeypatch.setattr("backend.app.services.export_engine.subprocess.run", lambda *args, **kwargs: Mock(returncode=1))
    success, report = ExportEngine(original).export_pdf(original, stale)
    assert not success
    assert "fresh PDF" in report["error"]
    assert stale.read_bytes() == before


def test_audit_csv_does_not_execute_uploaded_spreadsheet_formula(tmp_path):
    output = tmp_path / "audit.csv"
    ExportEngine.export_citation_audit_csv(output, [{"matched_text": "=WEBSERVICE(\"https://example.org\")"}])
    with output.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1][4].startswith("'=")
