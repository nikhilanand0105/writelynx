import re
from pathlib import Path
from typing import Dict, Any, List
import pymupdf as fitz

class ExternalReportParser:
    """
    Parses historical similarity report PDFs (e.g. authorized Turnitin PDF receipts/reports)
    to extract previously flagged passages, historical percentages, and source attributions.
    """

    SIMILARITY_SCORE_RE = re.compile(r'(?:Similarity\s+Index|Similarity\s+Report|Overall\s+Similarity)\s*[:=]?\s*(\d+)\s*%', re.IGNORECASE)
    SOURCE_ITEM_RE = re.compile(r'(\d+)\s+([a-zA-Z0-9.-]+\.[a-z]{2,}|Internet Source|Publications|Student Paper)\s+(\d+)\s*%', re.IGNORECASE)

    @classmethod
    def parse_pdf_report(cls, pdf_path: Path) -> Dict[str, Any]:
        doc = fitz.open(str(pdf_path))
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()

        # Extract overall historical score
        score_match = cls.SIMILARITY_SCORE_RE.search(full_text)
        historical_score = int(score_match.group(1)) if score_match else None

        # Extract primary sources mentioned
        sources = []
        for m in cls.SOURCE_ITEM_RE.finditer(full_text):
            sources.append({
                "source_index": int(m.group(1)),
                "title": m.group(2).strip(),
                "percentage": int(m.group(3))
            })

        # Extract quoted blocks or highlighted sections
        # Often Turnitin outputs marked paragraphs with numbers [1], [2] next to text
        matches = []
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        for line in lines:
            if len(line.split()) >= 6:
                # Look for lines with substantial content
                matches.append(line)

        return {
            "is_external_report": True,
            "historical_similarity_percentage": historical_score,
            "label": "Historical External Similarity Report (Uploaded File)",
            "sources_extracted": sources,
            "raw_text_length": len(full_text),
            "disclaimer": "This score reflects only the historical score printed on the uploaded external report document. Manuscript Integrity Studio does not claim to generate official Turnitin scores.",
            "extracted_passages": matches[:20]  # top passage snippets
        }
