import re
from typing import List, Dict, Any, Tuple, Set

class CitationAnalyzer:
    """
    Analyzes IEEE, APA, Harvard, and numeric citations across a document,
    identifying broken links, missing citations, uncited references, and unattributed claims.
    """

    NUMERIC_CITATION = re.compile(r'\[(\d+(?:\s*[,-–]\s*\d+)*)\]')
    AUTHOR_YEAR_CITATION = re.compile(r'\(([A-Z][a-zA-Z\s.-]+(?:\s+et\s+al\.)?),\s*((?:19|20)\d{2}[a-z]?)\)')
    QUOTATION_PATTERN = re.compile(r'["“]([^"”]{15,})["”]')
    UNSUPPORTED_CLAIM_TRIGGER = re.compile(
        r'\b(studies show that|research proves that|it is well known that|it has been widely proven that|prior work has demonstrated that|experiments undeniably prove)\b',
        re.IGNORECASE
    )

    def analyze(self, blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Analyze citations and bibliography in document blocks.
        Returns (findings, citation_audit_summary).
        """
        findings = []
        cited_numeric_ids: Set[int] = set()
        cited_author_years: Set[Tuple[str, str]] = set()
        
        # 1. Identify reference list entries
        ref_blocks = [
            b for b in blocks 
            if b.get("block_type") == "reference_entry" or b.get("section_id") == "References"
        ]
        
        # Extract bibliography items
        bibliography: Dict[int, Dict[str, Any]] = {}
        author_year_bib: List[str] = []
        duplicate_entries = []

        for ref_b in ref_blocks:
            text = ref_b.get("current_text", "").strip()
            num_match = re.match(r'^\[(\d+)\]', text)
            if num_match:
                ref_num = int(num_match.group(1))
                if ref_num in bibliography:
                    duplicate_entries.append(ref_num)
                bibliography[ref_num] = {
                    "block_id": ref_b["id"],
                    "text": text,
                    "num": ref_num
                }
            else:
                author_year_bib.append(text)

        # 2. Extract citations in body blocks (exclude reference list itself)
        body_blocks = [b for b in blocks if b not in ref_blocks]

        for b in body_blocks:
            text = b.get("current_text", "")
            if not text.strip():
                continue

            # Check numeric citations
            for match in self.NUMERIC_CITATION.finditer(text):
                raw_nums = match.group(1)
                # Parse commas and ranges e.g. "1, 2" or "1-3"
                for part in re.split(r'[,–-]', raw_nums):
                    part = part.strip()
                    if part.isdigit():
                        cited_numeric_ids.add(int(part))

            # Check author-year citations
            for match in self.AUTHOR_YEAR_CITATION.finditer(text):
                author = match.group(1).strip()
                year = match.group(2).strip()
                cited_author_years.add((author, year))

            # Check for direct quotations without a citation
            quotes = self.QUOTATION_PATTERN.finditer(text)
            for q in quotes:
                quote_text = q.group(1)
                # Check if citation appears right after or inside the quotation
                quote_end = q.end()
                surrounding = text[quote_end:quote_end + 30]
                has_nearby_cit = bool(self.NUMERIC_CITATION.search(surrounding) or self.AUTHOR_YEAR_CITATION.search(surrounding))
                if not has_nearby_cit:
                    findings.append({
                        "id": f"cit_quote_{b['id']}_{len(findings)}",
                        "document_id": b["document_id"],
                        "block_id": b["id"],
                        "finding_type": "missing_citation",
                        "severity": "high",
                        "matched_text": quote_text[:100],
                        "similarity_score": 0.0,
                        "match_type": "quotation_without_attribution",
                        "evidence": {
                            "issue": "Direct quotation lacking immediate citation or attribution.",
                            "quote": quote_text,
                            "recommended_action": "Add appropriate citation [X] or (Author, Year) immediately following the quote."
                        },
                        "review_status": "pending"
                    })

            # Check for unsupported sweeping claims
            for claim_match in self.UNSUPPORTED_CLAIM_TRIGGER.finditer(text):
                claim_phrase = claim_match.group(0)
                # Check if sentence has a citation
                sentence_end = text.find(".", claim_match.end())
                if sentence_end == -1:
                    sentence_end = len(text)
                sentence = text[claim_match.start():sentence_end]
                if not (self.NUMERIC_CITATION.search(sentence) or self.AUTHOR_YEAR_CITATION.search(sentence)):
                    findings.append({
                        "id": f"cit_claim_{b['id']}_{len(findings)}",
                        "document_id": b["document_id"],
                        "block_id": b["id"],
                        "finding_type": "unsupported_claim",
                        "severity": "medium",
                        "matched_text": claim_phrase,
                        "similarity_score": 0.0,
                        "match_type": "unsupported_claim",
                        "evidence": {
                            "issue": f"Sweeping generalization ('{claim_phrase}') without supporting reference.",
                            "recommended_action": "Provide specific citation supporting this claim or temper the wording."
                        },
                        "review_status": "pending"
                    })

        # 3. Check for citations without corresponding reference in bibliography
        if bibliography:
            for cit_id in sorted(cited_numeric_ids):
                if cit_id not in bibliography:
                    # Find which block had this missing citation
                    for b in body_blocks:
                        if f"[{cit_id}]" in b.get("current_text", ""):
                            findings.append({
                                "id": f"cit_missing_ref_{b['id']}_{cit_id}",
                                "document_id": b["document_id"],
                                "block_id": b["id"],
                                "finding_type": "missing_citation",
                                "severity": "high",
                                "matched_text": f"[{cit_id}]",
                                "similarity_score": 0.0,
                                "match_type": "missing_bibliography_entry",
                                "evidence": {
                                    "issue": f"In-text citation [{cit_id}] has no matching reference entry in the bibliography.",
                                    "recommended_action": f"Add full bibliographic details for reference [{cit_id}] in the References section."
                                },
                                "review_status": "pending"
                            })
                            break

            # 4. Check for uncited references in bibliography
            for ref_num, ref_info in bibliography.items():
                if ref_num not in cited_numeric_ids:
                    findings.append({
                        "id": f"cit_uncited_ref_{ref_info['block_id']}_{ref_num}",
                        "document_id": ref_blocks[0]["document_id"],
                        "block_id": ref_info["block_id"],
                        "finding_type": "common_terminology",
                        "severity": "low",
                        "matched_text": ref_info["text"][:100],
                        "similarity_score": 0.0,
                        "match_type": "uncited_reference",
                        "evidence": {
                            "issue": f"Reference [{ref_num}] is listed in the bibliography but is never cited in the document text.",
                            "recommended_action": f"Cite [{ref_num}] where relevant or remove it if unused."
                        },
                        "review_status": "pending"
                    })

        audit_summary = {
            "total_references_defined": len(bibliography) + len(author_year_bib),
            "total_citations_in_text": len(cited_numeric_ids) + len(cited_author_years),
            "missing_bibliography_entries": [c for c in cited_numeric_ids if bibliography and c not in bibliography],
            "uncited_bibliography_entries": [r for r in bibliography if r not in cited_numeric_ids],
            "duplicate_entries": duplicate_entries,
        }

        return findings, audit_summary
