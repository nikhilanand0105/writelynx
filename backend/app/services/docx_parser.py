"""Read-only DOCX block extraction with stable OOXML addresses.

Unsupported objects stay in the package and are explicitly marked read-only.  A
block address is an element-index path from ``word/document.xml``'s root, not a
paragraph ordinal (which changes when tables or empty paragraphs are present).
"""
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import docx
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NAMESPACES = {"w": W_NS, "m": M_NS, "r": R_NS}


def element_path(element) -> List[int]:
    path = []
    while element.getparent() is not None:
        parent = element.getparent()
        path.append(parent.index(element))
        element = parent
    return list(reversed(path))


def paragraph_text(element) -> str:
    """Visible run text including hyperlinks, without flattening drawings/math."""
    parts = []
    for node in element.iter():
        # Text boxes have their own paragraphs and are not part of the outer one.
        nearest_p = next((a for a in node.iterancestors() if a.tag == qn("w:p")), None)
        if nearest_p is not None and nearest_p != element:
            continue
        if node.tag == qn("w:t"):
            parts.append(node.text or "")
        elif node.tag == qn("w:tab"):
            parts.append("\t")
        elif node.tag in {qn("w:br"), qn("w:cr")}:
            parts.append("\n")
    return "".join(parts)


def paragraph_constraints(element) -> List[str]:
    """Conservative boundaries for text-only patches; no object is discarded."""
    reasons = []
    selectors = {
        "equation": ".//m:oMath | .//m:oMathPara",
        "drawing or embedded image": ".//w:drawing | .//w:pict | .//w:object",
        "field code": ".//w:fldChar | .//w:instrText | .//w:fldSimple",
        "tracked change": ".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo",
        "content control": ".//w:sdt",
        "footnote or endnote reference": ".//w:footnoteReference | .//w:endnoteReference",
        "tab or line break": ".//w:tab | .//w:br | .//w:cr",
        "anchored comment or bookmark": ".//w:commentRangeStart | .//w:commentRangeEnd | .//w:bookmarkStart | .//w:bookmarkEnd",
    }
    for label, selector in selectors.items():
        if element.xpath(selector):
            reasons.append(label)
    return reasons


class DocxParser:
    def __init__(self, file_path: Path, doc_id: str):
        self.file_path = Path(file_path)
        self.doc_id = doc_id
        self.doc = docx.Document(str(file_path))

    def parse(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        blocks = []
        current_section = "Title & Abstract"
        table_index = 0
        preservation_warnings = []

        def append_block(block_type, text, element, metadata, protected=False):
            index = len(blocks)
            if block_type == "table_cell":
                suffix = f"tbl_{metadata['table_index']:02d}_{metadata['row_index']:02d}_{metadata['col_index']:02d}"
            else:
                suffix = f"p_{index:04d}"
            blocks.append({
                "id": f"{self.doc_id}_{suffix}", "document_id": self.doc_id,
                "block_index": index, "section_id": current_section,
                "block_type": block_type, "original_text": text, "current_text": text,
                "is_protected": protected or not metadata.get("editable", True),
                "structure_metadata": {"xml_path": element_path(element), **metadata},
            })

        for child in self.doc.element.body:
            if child.tag == qn("w:p"):
                p = Paragraph(child, self.doc)
                text = paragraph_text(child)
                has_equations = bool(child.xpath(".//m:oMath | .//m:oMathPara"))
                has_images = bool(child.xpath(".//w:drawing | .//w:pict"))
                if not text.strip() and not has_equations and not has_images:
                    continue
                block_type, section = self._classify_paragraph(p, text.strip(), current_section)
                if section:
                    current_section = section
                constraints = paragraph_constraints(child)
                append_block(block_type, text, child, {
                    "style_name": p.style.name if p.style else "Normal",
                    "runs_count": len(p.runs), "runs": self._extract_runs_metadata(p),
                    "alignment": str(p.alignment) if p.alignment is not None else None,
                    "has_equations": has_equations, "has_images": has_images,
                    "has_hyperlinks": bool(child.xpath(".//w:hyperlink")),
                    "element_tag": "w:p", "editable": not constraints,
                    "preservation_warnings": constraints,
                }, block_type in {"title", "heading", "figure_caption", "table_caption", "reference_entry"})
            elif child.tag == qn("w:tbl"):
                # Walk physical cells once; python-docx's row.cells repeats merged cells.
                for row_index, row in enumerate(child.findall(qn("w:tr"))):
                    for col_index, cell in enumerate(row.findall(qn("w:tc"))):
                        paragraphs = cell.findall(qn("w:p"))
                        text = "\n".join(paragraph_text(p) for p in paragraphs)
                        if not text.strip():
                            continue
                        constraints = sorted({reason for p in paragraphs for reason in paragraph_constraints(p)})
                        if cell.findall(qn("w:tbl")):
                            constraints.append("nested table")
                        if len(paragraphs) != 1:
                            constraints.append("multiple cell paragraphs")
                        append_block("table_cell", text, cell, {
                            "table_index": table_index, "row_index": row_index, "col_index": col_index,
                            "element_tag": "w:tbl", "paragraph_paths": [element_path(p) for p in paragraphs],
                            "editable": not constraints, "preservation_warnings": constraints,
                        })
                table_index += 1
            elif child.tag != qn("w:sectPr"):
                # Expose visible content from unsupported wrappers for analysis, but do
                # not promise edits that could invalidate a field/control or revision.
                for p in child.xpath(".//w:p"):
                    text = paragraph_text(p)
                    if text.strip():
                        append_block("paragraph", text, p, {
                            "element_tag": "w:p", "editable": False,
                            "preservation_warnings": ["unsupported body container"],
                        }, True)
                preservation_warnings.append("Unsupported body containers are preserved without editing.")

        with zipfile.ZipFile(self.file_path) as archive:
            image_count = sum(name.startswith("word/media/") and not name.endswith("/") for name in archive.namelist())
            auxiliary = [name for name in archive.namelist() if re.match(r"word/(?:header|footer|footnotes|endnotes)", name) and name.endswith(".xml")]
        return blocks, {
            "total_blocks": len(blocks), "word_count": sum(len(b["original_text"].split()) for b in blocks),
            "paragraph_count": sum(b["structure_metadata"]["element_tag"] == "w:p" for b in blocks),
            "table_count": len(self.doc.tables), "image_count": image_count,
            "sections": list(dict.fromkeys(b["section_id"] for b in blocks)),
            "read_only_blocks": sum(not b["structure_metadata"].get("editable", True) for b in blocks),
            "preserved_auxiliary_parts": auxiliary,
            "preservation_warnings": list(dict.fromkeys(preservation_warnings)),
        }

    def _classify_paragraph(self, p: Paragraph, text: str, current_section: str) -> Tuple[str, str | None]:
        style_name = (p.style.name if p.style else "").lower()
        if "subtitle" in style_name:
            return "subtitle", None
        if "title" in style_name:
            return "title", "Title & Abstract"
        if style_name.startswith("heading"):
            return "heading", "References" if text.lower() in {"references", "bibliography"} else text
        if "caption" in style_name:
            return ("figure_caption" if re.match(r"^(figure|fig\.)", text, re.I) else "table_caption"), None
        if "list" in style_name or "bullet" in style_name or p._p.xpath("./w:pPr/w:numPr"):
            return "list_item", None
        if re.match(r"^(\d+(?:\.\d+)*\.?|[IVXLCDM]+\.)\s+[A-Z]", text) and len(text.split()) <= 12:
            return "heading", text
        lower = text.lower()
        if lower in {"abstract", "executive summary"}:
            return "heading", "Abstract"
        if lower in {"introduction", "background"}:
            return "heading", "Introduction"
        if lower in {"method", "methodology", "results", "experiments", "evaluation", "discussion", "conclusion", "conclusions", "future work"}:
            return "heading", text
        if lower in {"references", "bibliography", "reference list"}:
            return "heading", "References"
        if current_section == "References" or re.match(r"^\[\d+\]", text):
            return "reference_entry", None
        if re.match(r"^(Figure|Fig\.|Table)\s+\d+[:.]", text, re.I):
            return ("figure_caption" if "fig" in lower[:5] else "table_caption"), None
        if re.match(r"^([•\-\*]|\d+\.|\([a-z0-9]+\))\s+", text):
            return "list_item", None
        return ("abstract" if current_section == "Abstract" else "paragraph"), None

    def _extract_runs_metadata(self, p: Paragraph) -> List[Dict[str, Any]]:
        return [{
            "text": r.text, "bold": r.bold, "italic": r.italic, "underline": bool(r.underline) if r.underline is not None else None,
            "font_name": r.font.name, "font_size_pt": r.font.size.pt if r.font.size else None,
        } for r in p.runs]
