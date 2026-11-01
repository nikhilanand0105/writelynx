"""Atomic, text-only OOXML patches with fail-closed preservation validation."""
import copy
import difflib
import hashlib
import os
import posixpath
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote, urlsplit

import docx
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from lxml import etree

from backend.app.services.docx_parser import (
    DocxParser, NAMESPACES, element_path, paragraph_constraints, paragraph_text,
)
from backend.app.services.fact_validator import FactValidator

DOCUMENT_PART = "word/document.xml"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NUMBER_PATTERN = re.compile(r"(?<![\w])[-+−]?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?%?(?![\w])")
CITATION_PATTERN = re.compile(r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]|\([^()]*\b(?:19|20)\d{2}[a-z]?[^()]*\)")


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _at_path(root, path):
    node = root
    if not isinstance(path, list) or not path or any(type(i) is not int or i < 0 for i in path):
        raise ValueError("Invalid document element address.")
    for index in path:
        node = node[index]
    return node


def _fact_violations(original, revised):
    valid, violations = FactValidator.compare_facts(original, revised)
    violations = list(violations)
    if Counter(NUMBER_PATTERN.findall(original)) != Counter(NUMBER_PATTERN.findall(revised)):
        violations.append("Numerical values or their occurrence counts changed.")
    citation_issues = []
    if Counter(CITATION_PATTERN.findall(original)) != Counter(CITATION_PATTERN.findall(revised)):
        citation_issues.append("Citation text or its occurrence count changed.")
    return list(dict.fromkeys(violations)), citation_issues


class StructurePreserver:
    def __init__(self, original_docx_path: Path):
        self.original_path = Path(original_docx_path)

    def apply_edits_and_export(
        self, target_path: Path, block_updates: Dict[str, str], blocks_metadata: List[Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, Any]]:
        target_path = Path(target_path)
        if target_path.resolve() == self.original_path.resolve() or (
            target_path.exists() and os.path.samefile(target_path, self.original_path)
        ):
            return False, {"valid": False, "error": "The immutable original cannot be used as an export destination.", "warnings": []}
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with zipfile.ZipFile(self.original_path) as archive:
                root = parse_xml(archive.read(DOCUMENT_PART))
            metadata = {b["id"]: b for b in blocks_metadata}
            if len(metadata) != len(blocks_metadata):
                raise ValueError("Duplicate block identifiers prevent safe export.")
            unknown = set(block_updates) - set(metadata)
            if unknown:
                raise ValueError("Unknown revision block identifiers: " + ", ".join(sorted(unknown)))
            # Legacy records predate element addresses. Reparse the immutable file;
            # never infer a paragraph ordinal by counting only non-table blocks.
            legacy = {}
            if any(not b.get("structure_metadata", {}).get("xml_path") for b in blocks_metadata):
                doc_ids = {b.get("document_id") for b in blocks_metadata if b.get("document_id")}
                if len(doc_ids) == 1:
                    fresh, _ = DocxParser(self.original_path, next(iter(doc_ids))).parse()
                    legacy = {b["id"]: b for b in fresh}
            blocked = []
            changed = []
            approved_paths = set()
            expected_texts = {}
            for block_id, new_text in block_updates.items():
                if not isinstance(new_text, str):
                    blocked.append({"block_id": block_id, "reason": "Revision text must be a string."})
                    continue
                block = metadata[block_id]
                sm = block.get("structure_metadata") or {}
                if not sm.get("xml_path"):
                    fresh = legacy.get(block_id)
                    if not fresh and block.get("original_text") is not None:
                        matches = [b for b in legacy.values() if b["original_text"] == block["original_text"]]
                        fresh = matches[0] if len(matches) == 1 else None
                    if fresh is None:
                        blocked.append({"block_id": block_id, "reason": "Legacy block cannot be uniquely located; re-upload the original to obtain stable addresses."})
                        continue
                    sm = fresh["structure_metadata"]
                try:
                    element = _at_path(root, sm["xml_path"])
                    if element.tag == qn("w:tc"):
                        paragraphs = element.findall(qn("w:p"))
                        old_text = "\n".join(paragraph_text(p) for p in paragraphs)
                    elif element.tag == qn("w:p"):
                        paragraphs = [element]
                        old_text = paragraph_text(element)
                    else:
                        raise ValueError("Revision address does not point to a paragraph or table cell.")
                    if old_text == new_text:
                        continue
                    if block.get("original_text") is not None and block["original_text"] != old_text:
                        raise ValueError("Revision address no longer matches the immutable original text.")
                    constraints = list(sm.get("preservation_warnings", []))
                    constraints.extend(reason for p in paragraphs for reason in paragraph_constraints(p))
                    if len(paragraphs) != 1:
                        constraints.append("multiple cell paragraphs")
                    if element.tag == qn("w:tc") and element.findall(qn("w:tbl")):
                        constraints.append("nested table")
                    if any(p.xpath(".//w:tab | .//w:br | .//w:cr") for p in paragraphs):
                        constraints.append("tab or line break")
                    if sm.get("editable") is False or constraints:
                        raise ValueError("Preserved read-only construct: " + ", ".join(sorted(set(constraints))) + ".")
                    facts, citations = _fact_violations(old_text, new_text)
                    approved = block.get("allow_fact_changes") is True
                    if (facts or citations) and not approved:
                        raise ValueError("Author approval is required for protected changes: " + " ".join(facts + citations))
                    paragraph = paragraphs[0]
                    self._patch_text_nodes(paragraph, new_text)
                    path = tuple(element_path(paragraph))
                    expected_texts[path] = new_text
                    if approved:
                        approved_paths.add(path)
                    changed.append(block_id)
                except (ValueError, IndexError, TypeError) as exc:
                    blocked.append({"block_id": block_id, "reason": str(exc)})
            if blocked:
                return False, {"valid": False, "error": "Some revisions could not be safely exported.", "blocked_edits": blocked, "warnings": [b["reason"] for b in blocked], "applied_edits": []}

            fd, temporary_name = tempfile.mkstemp(prefix=".docx-export-", suffix=".docx", dir=target_path.parent)
            os.close(fd)
            temporary_path = Path(temporary_name)
            if not changed:
                shutil.copyfile(self.original_path, temporary_path)
            else:
                patched_xml = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
                with zipfile.ZipFile(self.original_path) as source, zipfile.ZipFile(temporary_path, "w") as output:
                    output.comment = source.comment
                    for member in source.infolist():
                        output.writestr(member, patched_xml if member.filename == DOCUMENT_PART else source.read(member.filename))
            report = self.validate_preservation(self.original_path, temporary_path, approved_paths=approved_paths)
            with zipfile.ZipFile(temporary_path) as output:
                reopened = parse_xml(output.read(DOCUMENT_PART))
            missing = [list(path) for path, text in expected_texts.items() if paragraph_text(_at_path(reopened, list(path))) != text]
            report["edits_verified"] = not missing
            report["applied_edits"] = changed
            if missing:
                report["valid"] = False
                report["warnings"].append("One or more requested edits failed their text read-back check.")
            if report["valid"]:
                os.replace(temporary_path, target_path)
                temporary_path = None
            return report["valid"], report
        except Exception as exc:
            return False, {"valid": False, "error": f"DOCX export failed: {exc}", "warnings": [str(exc)]}
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _patch_text_nodes(paragraph, new_text):
        nodes = paragraph.xpath("./w:r/w:t | ./w:hyperlink/w:r/w:t")
        original = "".join(node.text or "" for node in nodes)
        if original != paragraph_text(paragraph) or not nodes:
            raise ValueError("Unsupported text container; the original is preserved.")
        spans = []
        cursor = 0
        for node in nodes:
            length = len(node.text or "")
            spans.append((cursor, cursor + length))
            cursor += length
        output = ["" for _ in nodes]
        for op, a, b, c, d in difflib.SequenceMatcher(None, original, new_text, autojunk=False).get_opcodes():
            if op == "equal":
                for index, (start, end) in enumerate(spans):
                    left, right = max(start, a), min(end, b)
                    if left < right:
                        output[index] += original[left:right]
            elif op in {"replace", "insert"}:
                # New text inherits the affected run, while equal text remains in
                # its original run, preserving bold/italic/superscript boundaries.
                index = next((i for i, (start, end) in enumerate(spans) if start <= a < end), len(nodes) - 1)
                output[index] += new_text[c:d]
        for node, text in zip(nodes, output):
            if any(a.tag == qn("w:hyperlink") for a in node.iterancestors()) and text != (node.text or ""):
                raise ValueError("An edit overlaps a hyperlink label; preserve the linked text or edit it in Word.")
        for node, text in zip(nodes, output):
            if text != (node.text or ""):
                node.text = text
                if text[:1].isspace() or text[-1:].isspace():
                    node.set(XML_SPACE, "preserve")
                else:
                    node.attrib.pop(XML_SPACE, None)
        if paragraph_text(paragraph) != new_text:
            raise ValueError("Text-node patch did not reproduce the requested revision.")

    @staticmethod
    def _structural_signature(root):
        cloned = copy.deepcopy(root)
        for node in cloned.xpath(".//w:t"):
            node.text = None
            node.attrib.pop(XML_SPACE, None)
        return etree.tostring(cloned, method="c14n")

    @staticmethod
    def _relationship_issues(archive):
        issues = []
        names = set(archive.namelist())
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        for name in names:
            if not name.endswith(".rels"):
                continue
            root = etree.fromstring(archive.read(name), parser)
            base = posixpath.dirname(posixpath.dirname(name)) if name != "_rels/.rels" else ""
            ids = set()
            for rel in root:
                rel_id = rel.get("Id")
                if rel_id in ids:
                    issues.append(f"Duplicate relationship in {name}: {rel_id}")
                ids.add(rel_id)
                if rel.get("TargetMode") == "External":
                    continue  # Inspect only; never resolve external links.
                target = unquote(urlsplit(rel.get("Target", "")).path)
                resolved = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join(base, target))
                if resolved not in names:
                    issues.append(f"Missing internal relationship target: {resolved}")
        return issues

    def validate_preservation(self, original_path: Path, exported_path: Path, approved_paths=None) -> Dict[str, Any]:
        approved_paths = approved_paths or set()
        report = {"valid": False, "archive_valid": False, "reopened_successfully": False,
                  "protected_facts_intact": False, "citation_integrity_intact": False,
                  "protected_fact_violations": [], "citation_warnings": [], "warnings": []}
        try:
            with zipfile.ZipFile(original_path) as original, zipfile.ZipFile(exported_path) as exported:
                if exported.testzip() is not None:
                    raise ValueError("Exported archive failed its CRC check.")
                report["archive_valid"] = True
                original_names, exported_names = set(original.namelist()), set(exported.namelist())
                report["package_parts_match"] = original_names == exported_names
                changed_parts = sorted(name for name in original_names & exported_names if original.read(name) != exported.read(name))
                report["changed_package_parts"] = changed_parts
                report["unchanged_parts_intact"] = report["package_parts_match"] and not (set(changed_parts) - {DOCUMENT_PART})
                media = [n for n in original_names if n.startswith("word/media/") and not n.endswith("/")]
                report["image_count"] = len([n for n in exported_names if n.startswith("word/media/") and not n.endswith("/")])
                report["media_intact"] = all(n in exported_names and original.read(n) == exported.read(n) for n in media) and len(media) == report["image_count"]
                report["relationship_warnings"] = self._relationship_issues(exported)
                report["relationships_valid"] = not report["relationship_warnings"]
                orig_root, exp_root = parse_xml(original.read(DOCUMENT_PART)), parse_xml(exported.read(DOCUMENT_PART))
                report["structure_intact"] = self._structural_signature(orig_root) == self._structural_signature(exp_root)
                original_doc, exported_doc = docx.Document(str(original_path)), docx.Document(str(exported_path))
                report.update({"reopened_successfully": True,
                               "original_paragraph_count": len(original_doc.paragraphs),
                               "final_paragraph_count": len(exported_doc.paragraphs),
                               "paragraph_count_match": len(original_doc.paragraphs) == len(exported_doc.paragraphs),
                               "table_count": len(exported_doc.tables),
                               "table_count_match": len(original_doc.tables) == len(exported_doc.tables)})
                approved_changes = []
                original_paragraphs = orig_root.xpath(".//w:p")
                exported_paragraphs = exp_root.xpath(".//w:p")
                for index, (old, new) in enumerate(zip(original_paragraphs, exported_paragraphs)):
                    old_text, new_text = paragraph_text(old), paragraph_text(new)
                    if old_text == new_text:
                        continue
                    facts, citations = _fact_violations(old_text, new_text)
                    if tuple(element_path(old)) in approved_paths and (facts or citations):
                        approved_changes.append({"paragraph_index": index, "violations": facts + citations})
                    else:
                        report["protected_fact_violations"].extend(f"Paragraph {index}: {v}" for v in facts)
                        report["citation_warnings"].extend(f"Paragraph {index}: {v}" for v in citations)
                report["approved_fact_changes"] = approved_changes
                report["protected_facts_intact"] = not report["protected_fact_violations"] and not approved_changes
                report["citation_integrity_intact"] = not report["citation_warnings"] and not any(any("Citation" in v for v in c["violations"]) for c in approved_changes)
                for key in ("package_parts_match", "unchanged_parts_intact", "media_intact", "relationships_valid", "structure_intact", "paragraph_count_match", "table_count_match"):
                    if not report[key]:
                        report["warnings"].append(f"Preservation check failed: {key}.")
                report["warnings"].extend(report["relationship_warnings"] + report["protected_fact_violations"] + report["citation_warnings"])
                report["original_sha256"] = _hash(Path(original_path))
                report["exported_sha256"] = _hash(Path(exported_path))
                report["byte_identical"] = report["original_sha256"] == report["exported_sha256"]
                report["visual_validation"] = "Not performed for DOCX; use PDF export for rendered-page checks."
                report["valid"] = not report["warnings"]
        except Exception as exc:
            report["warnings"].append(f"Document validation failed: {exc}")
        return report
