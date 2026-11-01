"""Local PDF highlight extraction; confidence describes extraction, never authorship."""
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pymupdf

CHROME_PATTERNS = [
    re.compile(p, re.I) for p in (
        r'Trusted\s+(?:GPT|ChatGPT|AI)', r'ZeroGPT\s+the\s+most\s+Advanced',
        r'Check\s+\d+[\d,]*\s+characters', r'Upgrade\s+Here', r'^Detect\s+Text$',
        r'\b\d+[\d,]*\s*/\s*\d+[\d,]*\s*Characters\b',
        r'Your\s+Text\s+is\s+Likely\s+AI', r'Most\s+of\s+Your\s+File\s+Content\s+is\s+AI',
        r'^https?://\S+$', r'^www\.\S+$', r'^Terms\s+&\s+Conditions$',
        r'^Privacy\s+Policy$', r'^Powered\s+by', r'^Upload\s+File$',
        r'\b(?:buy now|add to cart|subscribe now|air fryer|free trial|advertisement)\b',
        r'^[₹$€£]\s*[\d,.]+(?:\s*/\s*(?:month|year))?$',
    )
]


class PDFHighlightExtractor:
    # Bounded rendering and OCR keep large screenshot PDFs workable on local laptops.
    MAX_PAGES = 250
    MAX_RENDER_SIDE = 2200
    MAX_OCR_PAGES = 8

    @classmethod
    def is_chrome_or_ad(cls, text: str) -> bool:
        return not text.strip() or any(p.search(text.strip()) for p in CHROME_PATTERNS)

    @staticmethod
    def _is_yellow(color, tolerance: float = 0.12) -> bool:
        if not color or len(color) < 3:
            return False
        r, g, b = color[:3]
        return r >= 0.78 - tolerance and g >= 0.70 - tolerance and b <= 0.60 + tolerance and min(r, g) - b >= 0.16

    @classmethod
    def extract_report_metadata(cls, doc: pymupdf.Document) -> Dict[str, Any]:
        text = '\n'.join(page.get_text() for page in doc)
        vendor = next((name for name in ('ZeroGPT', 'Turnitin', 'GPTZero', 'Copyleaks')
                       if re.search(r'\b' + name + r'\b', text, re.I)), 'Unknown')
        score_matches = []
        for pat in (r'([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:AI|GPT|Automated)',
                    r'(?:AI|GPT)(?:\s+(?:score|generated|probability))?[^0-9\n]{0,20}([0-9]+(?:\.[0-9]+)?)\s*%'):
            score_matches.extend(float(m) for m in re.findall(pat, text, re.I) if 0 <= float(m) <= 100)
        scores = sorted(set(score_matches))
        count = re.search(r'\b([\d,]+)\s*/\s*([\d,]+)\s*Characters\b', text, re.I)
        chars = int(count[1].replace(',', '')) if count else None
        limit = int(count[2].replace(',', '')) if count else None
        if chars is None:
            count = re.search(r'(?:submitted|analy[sz]ed|checked)\s+(?:text\s*)?(?:characters?\s*[:=]?\s*)?([\d,]+)\s*characters?\b', text, re.I)
            if not count:
                count = re.search(r'(?:character\s*count|characters\s+analy[sz]ed)\s*[:=]\s*([\d,]+)', text, re.I)
            chars = int(count[1].replace(',', '')) if count else None
        words = re.search(r'(?:word\s*count|words\s+analy[sz]ed)\s*[:=]?\s*([\d,]+)', text, re.I)
        if not words:
            words = re.search(r'\b([\d,]+)\s+words\b', text, re.I)
        version = re.search(r'(?:detector|model|service)\s+version\s*[:=]\s*([^\n]{1,80})', text, re.I)
        explicit_truncation = bool(re.search(r'limit\s*reached|truncated\s*report|only\s+part\s+of\s+(?:the|this)\s+document', text, re.I))
        at_limit = chars is not None and limit is not None and chars >= limit
        # A full input box establishes a scope limit, not proof that the original is longer.
        truncated = explicit_truncation or at_limit
        return {
            'detector_name': vendor, 'detector_score': scores[0] if len(scores) == 1 else None,
            'score_candidates': scores, 'analyzed_characters': chars,
            'analyzed_words': int(words[1].replace(',', '')) if words else None,
            'character_limit': limit, 'service_version': version[1].strip() if version else None,
            'is_truncated': truncated, 'coverage_status': 'limited' if truncated else 'unknown',
            'truncation_notice': ('Only part of this document was evaluated or the report reached its stated input limit. '
                                  'Coverage beyond the imported text is not established.') if truncated else None,
            'coverage_notice': ('The report states an input of ' + str(chars) + ' characters. ' if chars is not None else '')
                               + 'Full-manuscript coverage is not established by this report.',
            'page_count': len(doc),
        }

    @classmethod
    def extract_detector_metadata(cls, doc: pymupdf.Document) -> Tuple[str, Optional[float], bool]:
        meta = cls.extract_report_metadata(doc)
        return meta['detector_name'], meta['detector_score'], meta['is_truncated']

    @classmethod
    def extract_highlights(cls, pdf_path: Path, *, merge_lines: bool = True, allow_ocr: bool = True) -> Dict[str, Any]:
        highlights, notices = [], []
        with pymupdf.open(str(pdf_path)) as doc:
            if doc.needs_pass:
                raise ValueError('Password-protected detector PDFs are not supported.')
            if len(doc) > cls.MAX_PAGES:
                raise ValueError(f'Detector reports are limited to {cls.MAX_PAGES} pages.')
            meta = cls.extract_report_metadata(doc)
            for i, page in enumerate(doc):
                highlights.extend(cls._extract_page_highlights(
                    page, i + 1, meta['detector_name'], merge_lines=merge_lines,
                    allow_ocr=allow_ocr and i < cls.MAX_OCR_PAGES, notices=notices,
                ))
        source_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
        for h in highlights:
            h['source_file_id'] = source_hash
            h['metadata_json']['source_file_hash'] = source_hash
        if not highlights:
            notices.append('No readable highlights were extracted. This does not establish that the report contains no highlights.')
        return {**meta, 'total_highlights': len(highlights), 'highlights': highlights,
                'extraction_notices': list(dict.fromkeys(notices)), 'file_hash': source_hash}

    @classmethod
    def _raster_mask(cls, page):
        scale = min(1.8, cls.MAX_RENDER_SIDE / max(page.rect.width, page.rect.height))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
        pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).astype(np.int16)
        r, g, b = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
        mask = (r >= 170) & (g >= 150) & (b <= 200) & (np.minimum(r, g) - b >= 40)
        return mask, scale

    @staticmethod
    def _mask_fraction(mask, scale, rect, page_rect):
        x0 = max(0, int((rect.x0 - page_rect.x0) * scale))
        y0 = max(0, int((rect.y0 - page_rect.y0) * scale))
        x1 = min(mask.shape[1], int((rect.x1 - page_rect.x0) * scale) + 1)
        y1 = min(mask.shape[0], int((rect.y1 - page_rect.y0) * scale) + 1)
        region = mask[y0:y1, x0:x1]
        return float(region.mean()) if region.size else 0

    @classmethod
    def _extract_page_highlights(cls, page, page_number, detector_name, *, merge_lines=True, allow_ocr=True, notices=None):
        notices = notices if notices is not None else []
        regions = []
        for annot in page.annots() or []:
            if annot.type[0] != 8:
                continue
            color = annot.colors.get('stroke') or annot.colors.get('fill')
            vertices = annot.vertices or []
            for n in range(0, len(vertices), 4):
                if len(vertices[n:n + 4]) == 4:
                    quad = pymupdf.Quad(vertices[n:n + 4])
                    regions.append((quad.rect, 'native_annotations', .98, color, [list(p) for p in quad]))
            if not vertices:
                regions.append((annot.rect, 'native_annotations', .90, color, []))
        for drawing in page.get_drawings():
            if not cls._is_yellow(drawing.get('fill')):
                continue
            # Filled rectangle items avoid interpreting a complex path's large bounding box as text.
            rects = [pymupdf.Rect(item[1]) for item in drawing['items'] if item[0] == 're']
            for rect in rects:
                if 3 < rect.width < page.rect.width * .98 and 3 < rect.height < 100:
                    regions.append((rect, 'pdf_vector', .94, drawing['fill'], []))

        words = page.get_text('words', sort=True)
        mask, scale = None, None
        # Raster inspection also catches mixed pages with text and screenshot highlights.
        if page.get_images() or (not regions and words):
            mask, scale = cls._raster_mask(page)
            if not words and mask.any():
                if allow_ocr:
                    try:
                        tp = page.get_textpage_ocr(language='eng', dpi=150, full=True)
                        words = page.get_text('words', textpage=tp, sort=True)
                    except (RuntimeError, ValueError) as exc:
                        notices.append(f'Page {page_number}: yellow image regions found; local OCR unavailable. Manual transcription is required.')
                else:
                    notices.append(f'Page {page_number}: yellow image regions require OCR or manual transcription; OCR page limit reached or disabled.')
        ocr_used = bool(words and not page.get_text('words'))
        selected = []
        for index, word in enumerate(words):
            rect = pymupdf.Rect(word[:4])
            matches = [r for r in regions if rect.get_area() and (rect & r[0]).get_area() / rect.get_area() >= .40]
            if matches:
                region = max(matches, key=lambda r: r[2])
            elif mask is not None and cls._mask_fraction(mask, scale, rect, page.rect) >= .22:
                region = (rect, 'raster_ocr' if ocr_used else 'raster_text_layer', .65 if ocr_used else .82, (1, 1, 0), [])
            else:
                continue
            if word[4].strip():
                selected.append((index, word, region))
        groups = []
        for item in selected:
            if groups:
                prev = groups[-1][-1]
                same_line = item[1][5:7] == prev[1][5:7]
                next_line = item[1][5] == prev[1][5] and item[1][6] == prev[1][6] + 1
                close = abs(item[1][1] - prev[1][1]) <= max(20, 2 * (prev[1][3] - prev[1][1]))
                if item[0] == prev[0] + 1 and close and (same_line or (merge_lines and next_line)):
                    groups[-1].append(item)
                    continue
            groups.append([item])
        results, seen = [], set()
        for group in groups:
            text = ' '.join(item[1][4] for item in group).strip()
            if not text or cls.is_chrome_or_ad(text):
                continue
            rect = pymupdf.Rect(group[0][1][:4])
            for item in group[1:]:
                rect |= pymupdf.Rect(item[1][:4])
            key = (text, tuple(round(v, 1) for v in rect))
            if key in seen:
                continue
            seen.add(key)
            methods = list(dict.fromkeys(item[2][1] for item in group))
            confidence = min(item[2][2] for item in group)
            geometry = []
            for item in group:
                entry = {'bbox': list(item[2][0]), 'quad': item[2][4], 'color': list(item[2][3] or [])}
                if entry not in geometry:
                    geometry.append(entry)
            ident = f'hl_p{page_number}_{len(results):04d}'
            results.append({
                'id': ident, 'highlight_id': ident, 'page_number': page_number,
                'highlight_text': text, 'text': text, 'bbox': [round(v, 2) for v in rect],
                'match_confidence': 0.0, 'mapping_status': 'unresolved', 'detector_name': detector_name,
                'extraction_strategy': methods[0] if len(methods) == 1 else 'mixed',
                'extraction_method': methods[0] if len(methods) == 1 else 'mixed',
                'confidence': confidence, 'verified': False, 'geometry': geometry,
                'metadata_json': {'word_count': len(group), 'extraction_confidence': confidence,
                                  'geometry': geometry, 'verified': False, 'methods': methods,
                                  'requires_manual_review': ocr_used},
            })
        return results
