"""Safe local evidence ingestion and conservative, traceable claim assessment."""
import csv
import datetime
import hashlib
import io
import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from backend.app.models.models import ResearchEvidence, AnalysisFinding, RevisionEvent, DocumentBlock
from backend.app.services.fact_validator import FactValidator


class EvidenceManager:
    TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.c', '.cc', '.cpp', '.h', '.hpp', '.java', '.js', '.ts',
                       '.log', '.patch', '.diff', '.csv', '.tsv', '.json', '.yaml', '.yml', '.toml', '.r', '.ipynb'}
    MAX_TEXT_CHARS = 1_000_000
    STOPWORDS = {'the', 'and', 'with', 'that', 'this', 'from', 'were', 'was', 'using', 'our', 'for', 'has',
                 'had', 'have', 'model', 'achieved', 'achieve', 'result', 'results', 'score', 'experiment', 'of', 'on', 'a', 'an'}

    @classmethod
    def extract_file_content(cls, path: Path, evidence_type: Optional[str] = None) -> Dict[str, Any]:
        path = Path(path)
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError('Evidence file exceeds the 50 MB limit.')
        suffix, warnings, content = path.suffix.lower(), [], ''
        raw = path.read_bytes()
        metadata = {'file_hash': hashlib.sha256(raw).hexdigest(), 'file_size': len(raw),
                    'extraction_status': 'extracted', 'parser': suffix.lstrip('.'), 'code_executed': False}
        if suffix in cls.TEXT_EXTENSIONS:
            try:
                content = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise ValueError('Text evidence must use UTF-8 encoding.')
            if '\x00' in content:
                raise ValueError('Binary content is not valid text evidence.')
            if suffix in {'.json', '.ipynb'}:
                try:
                    data = json.loads(content)
                except (ValueError, RecursionError):
                    raise ValueError('Evidence contains malformed JSON.')
                content = json.dumps(data, ensure_ascii=False, indent=2)
                metadata['structured_format'] = 'json'
            elif suffix in {'.csv', '.tsv'}:
                try:
                    rows = list(csv.reader(io.StringIO(content), delimiter='\t' if suffix == '.tsv' else ','))
                except csv.Error:
                    raise ValueError('Evidence contains malformed delimited data.')
                metadata['row_count'] = max(0, len(rows) - 1)
                metadata['columns'] = rows[0][:100] if rows else []
                # Label every cell for retrieval; do not infer dataset roles or metric meaning.
                if rows:
                    lines = [' | '.join(f'{rows[0][i]}: {value}' for i, value in enumerate(row) if i < len(rows[0])) for row in rows[1:]]
                    content = '\n'.join(lines)
                metadata['structured_format'] = 'table'
        elif suffix == '.pdf':
            import pymupdf
            with pymupdf.open(str(path)) as doc:
                if doc.needs_pass or len(doc) > 250:
                    raise ValueError('Evidence PDF must be unencrypted and at most 250 pages.')
                content = '\n\n'.join(f'[Page {i + 1}]\n{page.get_text()}' for i, page in enumerate(doc))
                metadata['page_count'] = len(doc)
                if not any(page.get_text().strip() for page in doc):
                    warnings.append('PDF has no readable text layer; manual transcription or local OCR is required.')
                    content = ''
        elif suffix == '.docx':
            from lxml import etree
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if sum(info.file_size for info in infos) > 100 * 1024 * 1024 or len(infos) > 10000:
                    raise ValueError('Evidence DOCX exceeds decompressed package limits.')
                if any('..' in Path(i.filename).parts or i.filename.startswith('/') for i in infos):
                    raise ValueError('Unsafe evidence DOCX package path.')
                parser = etree.XMLParser(resolve_entities=False, no_network=True)
                root = etree.fromstring(archive.read('word/document.xml'), parser=parser)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                content = '\n'.join(''.join(p.xpath('.//w:t/text()', namespaces=ns)) for p in root.xpath('//w:p', namespaces=ns))
        elif suffix in {'.png', '.jpg', '.jpeg', '.webp'}:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
            warnings.append('Image retained as evidence. Its content is not automatically verified; provide an exact transcription and context.')
            metadata['extraction_status'] = 'manual_transcription_required'
        else:
            raise ValueError('Unsupported evidence format.')
        if len(content) > cls.MAX_TEXT_CHARS:
            content = content[:cls.MAX_TEXT_CHARS]
            warnings.append('Text extraction was limited to 1,000,000 characters; remaining content was not analyzed.')
        if not content.strip() and metadata['extraction_status'] == 'extracted':
            metadata['extraction_status'] = 'no_readable_text'
        metadata['warnings'] = warnings
        return {'content': content, 'metadata_json': metadata}

    @classmethod
    def add_evidence(cls, db: Session, document_id: str, title: str, evidence_type: str,
                     content: Optional[str] = None, file_path: Optional[str] = None,
                     linked_blocks: Optional[List[str]] = None, metadata_json: Optional[Dict[str, Any]] = None) -> ResearchEvidence:
        if linked_blocks:
            found = {b.id for b in db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id,
                                                                 DocumentBlock.id.in_(linked_blocks)).all()}
            if found != set(linked_blocks):
                raise ValueError('Linked blocks must belong to the evidence document.')
        metadata = dict(metadata_json or {})
        if file_path and content is None:
            extracted = cls.extract_file_content(Path(file_path), evidence_type)
            content = extracted['content']
            metadata.update(extracted['metadata_json'])
        evidence = ResearchEvidence(id=str(uuid.uuid4()), document_id=document_id, title=title,
            evidence_type=evidence_type, content=content, file_path=file_path,
            linked_blocks=linked_blocks or [], created_at=datetime.datetime.utcnow(), metadata_json=metadata)
        db.add(evidence); db.commit(); db.refresh(evidence)
        return evidence

    @classmethod
    def _terms(cls, text):
        return {t for t in re.findall(r'[a-z][a-z0-9_-]{2,}', text.casefold()) if t not in cls.STOPWORDS}

    @classmethod
    def assess_claim(cls, claim: str, evidence_content: str, evidence_type: str) -> Dict[str, Any]:
        normalize = lambda s: re.sub(r'\s+', ' ', s).strip().casefold()
        claim = claim.strip()
        passages = [p.strip() for p in re.split(r'\n|(?<=[.!?])\s+', evidence_content or '') if p.strip()]
        terms = cls._terms(claim)
        scored = [(len(terms & cls._terms(p)) / max(1, len(terms)), p) for p in passages]
        scored.sort(reverse=True)
        relevant = [(s, p) for s, p in scored[:5] if s >= .30]
        result = {'verification_status': 'needs_evidence', 'reasons': [], 'supporting_passages': [],
                  'limitations': ['Local textual checks cannot establish provenance, experimental validity, or generalization.']}
        if not claim or not relevant:
            result['reasons'] = ['No passage directly supports the claim. A title, keyword, or linked block is not verification.']
            return result
        result['supporting_passages'] = [{'text': p[:2000], 'relevance': round(s, 3)} for s, p in relevant]
        facts = FactValidator.extract_facts(claim)
        claim_metrics = {re.sub(r'[-_\s]+', '', m['name'].casefold()): m['value'] for m in facts['metrics']}
        record = '\n'.join(p for _, p in relevant)
        ev_facts = FactValidator.extract_facts(record)
        ev_metrics = {}
        for m in ev_facts['metrics']:
            ev_metrics.setdefault(re.sub(r'[-_\s]+', '', m['name'].casefold()), set()).add(m['value'])
        conflicts = [(name, val, sorted(ev_metrics[name])) for name, val in claim_metrics.items()
                     if name in ev_metrics and val not in ev_metrics[name]]
        if conflicts:
            result['verification_status'] = 'contradicted'
            result['reasons'] = [f"The supplied record reports {', '.join(vals)} for {name}, whereas the claim states {val}. Confirm experiment and dataset scope." for name, val, vals in conflicts]
            return result
        # Direct record support only for a narrowly scoped, verbatim numerical statement.
        # Broad interpretation, code comments, notes, drafts and keyword retrieval cannot establish a result.
        exact = any(normalize(claim).rstrip('.') == normalize(p).rstrip('.') for _, p in relevant)
        interpretation = bool(re.search(r'\b(significan\w*|superior|best|novel|first|caus\w*|robust\w*|reliable|production|regulat\w*|prove\w*|outperform\w*|improv\w*|generaliz\w*)\b', claim, re.I))
        record_type = evidence_type in {'experiment_log', 'benchmark_table', 'benchmark', 'results'}
        if exact and facts['numbers'] and record_type and not interpretation:
            result['verification_status'] = 'verified'
            result['reasons'] = ['This exact numerical statement is present in the supplied experimental record. Verification is limited to consistency with that record.']
        else:
            result['verification_status'] = 'partially_supported'
            result['reasons'] = ['Relevant passages were retrieved, but they do not establish the full claim. Review experimental scope, methods, and source reliability.']
        return result

    @classmethod
    def verify_finding_with_evidence(cls, db: Session, finding_id: str, evidence_id: str,
                                   user_notes: Optional[str] = None) -> Dict[str, Any]:
        finding = db.query(AnalysisFinding).filter(AnalysisFinding.id == finding_id).first()
        evidence = db.query(ResearchEvidence).filter(ResearchEvidence.id == evidence_id).first()
        if not finding or not evidence:
            raise ValueError('Finding or evidence not found.')
        if evidence.document_id != finding.document_id:
            raise ValueError('Evidence and finding must belong to the same document.')
        assessment = cls.assess_claim(finding.matched_text or '', evidence.content or '', evidence.evidence_type)
        status = assessment['verification_status']
        finding.review_status = status
        finding.requires_author_input = status != 'verified'
        ev_data = dict(finding.evidence or {})
        ev_data.update({'linked_evidence_id': evidence_id, 'verified_evidence_title': evidence.title,
                        'verification_notes': user_notes or '', 'verification': assessment})
        if status == 'verified':
            ev_data['verified_by_evidence_id'] = evidence_id
        else:
            ev_data.pop('verified_by_evidence_id', None)
        finding.evidence = ev_data
        db.add(RevisionEvent(id=str(uuid.uuid4()), document_id=finding.document_id, block_id=finding.block_id,
            event_type='add_evidence', before_text=finding.matched_text, after_text=finding.matched_text,
            timestamp=datetime.datetime.utcnow(), user_notes=f'Evidence assessment: {status}; {evidence.title}. {user_notes or ""}',
            attribution_tag='original_author'))
        db.commit(); db.refresh(finding)
        return {'success': True, 'finding_id': finding.id, 'review_status': status, 'evidence_id': evidence.id,
                'evidence_title': evidence.title, **assessment}
