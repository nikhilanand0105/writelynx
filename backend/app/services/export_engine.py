import csv
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import Counter
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pymupdf as fitz
from lxml import etree
from backend.app.core.config import settings
from backend.app.services.structure_preserver import StructurePreserver

class ExportEngine:
    """
    Handles generation of revised DOCX, PDF conversion via LibreOffice headless,
    audit CSV generation, and revision log exports.
    """

    def __init__(self, original_docx_path: Path):
        self.original_path = original_docx_path
        self.preserver = StructurePreserver(original_docx_path)

    def export_docx(
        self,
        output_path: Path,
        block_updates: Dict[str, str],
        blocks_metadata: List[Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate revised DOCX and run preservation validation checks.
        """
        return self.preserver.apply_edits_and_export(output_path, block_updates, blocks_metadata)

    def export_pdf(self, docx_path: Path, pdf_output_path: Path) -> Tuple[bool, Dict[str, Any]]:
        """Convert in an isolated profile; publish only a fresh, reopened PDF."""
        docx_path, pdf_output_path = Path(docx_path), Path(pdf_output_path)
        if pdf_output_path.resolve() in {docx_path.resolve(), self.original_path.resolve()}:
            return False, {"error": "The original or revised DOCX cannot be a PDF destination."}
        soffice = shutil.which(settings.LIBREOFFICE_PATH) or shutil.which("libreoffice") or shutil.which("soffice")
        if not soffice:
            return False, {"error": "LibreOffice is unavailable. Install LibreOffice or configure LIBREOFFICE_PATH to enable PDF export.", "available": False}
        pdf_output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # External hyperlinks remain inert. Linked images/templates/objects
            # could trigger network access in an office renderer, so reject them.
            with zipfile.ZipFile(docx_path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith("vbaproject.bin"):
                        return False, {"error": "Macro-bearing documents cannot be converted."}
                    if name.endswith(".rels"):
                        root = etree.fromstring(archive.read(name), etree.XMLParser(resolve_entities=False, no_network=True))
                        if any(rel.get("TargetMode") == "External" and not rel.get("Type", "").endswith("/hyperlink") for rel in root):
                            return False, {"error": "PDF conversion is disabled for active external document relationships. Embed linked content locally first."}
            with tempfile.TemporaryDirectory(prefix=".pdf-convert-", dir=pdf_output_path.parent) as directory:
                work = Path(directory)
                profile = work / "profile"
                (profile / "user").mkdir(parents=True)
                (profile / "user" / "registrymodifications.xcu").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
                    '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
                    '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
                    '<item oor:path="/org.openoffice.Office.Writer/Content/Update">'
                    '<prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item></oor:items>',
                    encoding="utf-8",
                )
                input_path = work / "document.docx"
                shutil.copyfile(docx_path, input_path)
                result = subprocess.run([
                    soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore", "--nodefault",
                    "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(work), str(input_path),
                ], capture_output=True, text=True, timeout=90)
                converted = work / "document.pdf"
                if result.returncode != 0 or not converted.is_file():
                    return False, {"error": "LibreOffice failed to generate a fresh PDF.", "converter_exit_code": result.returncode}
                validation = self.validate_pdf(converted)
                if not validation["valid"]:
                    return False, {"error": "Rendered PDF validation failed.", **validation}
                # Compare extracted text as a diagnostic, not a proof of layout fidelity.
                with zipfile.ZipFile(docx_path) as archive:
                    document = etree.fromstring(archive.read("word/document.xml"), etree.XMLParser(resolve_entities=False, no_network=True))
                    source_text = " ".join(document.xpath("//w:t/text()", namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}))
                with fitz.open(converted) as pdf:
                    rendered_text = " ".join(page.get_text() for page in pdf)
                source_words = Counter(re.findall(r"\w+", source_text.casefold()))
                pdf_words = Counter(re.findall(r"\w+", rendered_text.casefold()))
                coverage = sum((source_words & pdf_words).values()) / max(1, sum(source_words.values()))
                validation["source_word_coverage"] = round(coverage, 4)
                if source_words and coverage < 0.90:
                    validation["warnings"].append("Some source text was not recovered from the PDF; inspect fonts, equations and possible truncation.")
                if source_words and validation["blank_page_count"] == validation["page_count"]:
                    return False, {"error": "All rendered PDF pages are blank despite source text.", **validation, "valid": False}
                os.replace(converted, pdf_output_path)
                validation["file_size_bytes"] = pdf_output_path.stat().st_size
                return True, validation
        except subprocess.TimeoutExpired:
            return False, {"error": "LibreOffice conversion exceeded 90 seconds; the original and existing exports are unchanged."}
        except Exception as exc:
            return False, {"error": f"PDF conversion failed: {exc}"}

    @staticmethod
    def validate_pdf(pdf_path: Path, reference_pdf_path: Optional[Path] = None) -> Dict[str, Any]:
        """Reopen and rasterize every page; flag blank pages and edge overflow.

        These are inspection aids. They do not establish pixel-perfect fidelity
        to Word or treat a legitimate page-count change as a failure.
        """
        report = {"valid": False, "reopened_successfully": False, "page_count": 0,
                  "rendered_page_count": 0, "blank_page_count": 0, "pages": [], "warnings": []}
        try:
            with fitz.open(pdf_path) as pdf:
                if not pdf.is_pdf or pdf.is_encrypted or not pdf.page_count:
                    raise ValueError("The PDF is empty, encrypted, or unreadable.")
                report.update({"reopened_successfully": True, "page_count": pdf.page_count})
                for number, page in enumerate(pdf):
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), colorspace=fitz.csGRAY, alpha=False)
                    ink_pixels = sum(value < 245 for value in pixmap.samples)
                    blank = ink_pixels == 0
                    blocks = page.get_text("blocks")
                    overflow = any(fitz.Rect(block[:4]).x0 < -2 or fitz.Rect(block[:4]).y0 < -2
                                   or fitz.Rect(block[:4]).x1 > page.rect.width + 2
                                   or fitz.Rect(block[:4]).y1 > page.rect.height + 2 for block in blocks)
                    report["pages"].append({"page": number + 1, "rendered": True, "blank": blank,
                                            "width_pt": round(page.rect.width, 2), "height_pt": round(page.rect.height, 2),
                                            "possible_overflow": overflow})
                    report["rendered_page_count"] += 1
                    report["blank_page_count"] += int(blank)
                    if overflow:
                        report["warnings"].append(f"Page {number + 1}: content extends beyond the page boundary; inspect layout.")
                if report["blank_page_count"]:
                    report["warnings"].append(f"{report['blank_page_count']} blank rendered page(s); these may be intentional section separators.")
                if reference_pdf_path:
                    with fitz.open(reference_pdf_path) as reference:
                        report["reference_page_count"] = reference.page_count
                        report["page_count_changed"] = reference.page_count != pdf.page_count
                        if report["page_count_changed"]:
                            report["warnings"].append("Page count differs from the reference; legitimate edits can change pagination.")
                report["valid"] = report["rendered_page_count"] == report["page_count"]
                report["comparison_limitations"] = "Rasterization and boundary checks cannot prove full Word layout fidelity. Inspect the exported PDF for unexpected pagination or font changes."
        except Exception as exc:
            report["warnings"].append(str(exc))
        return report

    @staticmethod
    def export_citation_audit_csv(output_path: Path, findings: List[Dict[str, Any]]) -> str:
        """Export citation findings as a CSV audit report."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Finding ID", "Block ID", "Finding Type", "Severity", "Matched Text", "Status", "Issue Explanation", "Recommended Action"])
            for item in findings:
                ev = item.get("evidence", {})
                values = [
                    item.get("id"),
                    item.get("block_id"),
                    item.get("finding_type"),
                    item.get("severity"),
                    item.get("matched_text"),
                    item.get("review_status"),
                    ev.get("issue", ev.get("explanation", "")),
                    ev.get("recommended_action", "")
                ]
                # Spreadsheet applications must not execute uploaded text as formulas.
                writer.writerow(["\'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values])
        return str(output_path)

    @staticmethod
    def export_revision_log_json(output_path: Path, revisions: List[Dict[str, Any]], doc_info: Dict[str, Any]) -> str:
        """Export comprehensive revision log in JSON format."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "document_info": doc_info,
            "total_revisions": len(revisions),
            "revisions": revisions
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        return str(output_path)
