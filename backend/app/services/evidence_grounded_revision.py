"""Retrieve evidence separately from establishing support; never fill an evidence gap."""
import re
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from backend.app.models.models import ResearchEvidence
from backend.app.services.evidence_manager import EvidenceManager
from backend.app.services.fact_validator import FactValidator
from backend.app.services.quantlens_validator import QuantLensValidator


class EvidenceGroundedRevisionEngine:
    @classmethod
    def execute_9step_grounding(cls, db: Session, document_id: str, block_id: str,
                               original_text: str, section_id: str = 'General') -> Dict[str, Any]:
        claims = cls._extract_main_claims(original_text)
        available = db.query(ResearchEvidence).filter(ResearchEvidence.document_id == document_id).all()
        matches, established, missing, assessments = [], [], [], []
        for claim in claims:
            assessed = []
            for evidence in available:
                assessment = EvidenceManager.assess_claim(claim, evidence.content or '', evidence.evidence_type)
                if assessment['verification_status'] == 'needs_evidence':
                    continue
                assessed.append({'claim': claim, 'evidence_id': evidence.id, **assessment})
                matches.append({'evidence_id': evidence.id, 'title': evidence.title,
                                'evidence_type': evidence.evidence_type,
                                'content_snippet': assessment['supporting_passages'][0]['text'] if assessment['supporting_passages'] else '',
                                'verification_status': assessment['verification_status']})
                if assessment['verification_status'] == 'verified':
                    established.append({'claim': claim, 'evidence_id': evidence.id,
                                        'supporting_passages': assessment['supporting_passages'],
                                        'scope': 'Consistency with the supplied record only.'})
            assessments.extend(assessed)
            if not assessed or not any(a['verification_status'] == 'verified' for a in assessed):
                missing.append(f'Direct supporting evidence is still required for: {claim}')
        questions = QuantLensValidator.generate_author_questions(original_text, section_id)
        if missing and not questions:
            questions = [{'topic': 'Research evidence',
                          'question': 'Which source passage or experimental record directly supports this claim, including its dataset and evaluation scope?',
                          'suggested_evidence': 'An exact source passage, experiment log, or benchmark table.'}]
        # Grounding does not itself authorize a substantive rewrite. Local edits only remove wordiness.
        revised = re.sub(r'\bdue to the fact that\b', 'because', original_text, flags=re.I)
        revised = re.sub(r'\bin order to\b', 'to', revised, flags=re.I)
        okay, violations = FactValidator.compare_facts(original_text, revised)
        ql_okay, ql_violations = QuantLensValidator.validate_facts(original_text, revised)
        return {'block_id': block_id, 'original_text': original_text,
                'proposed_text': revised if okay and ql_okay else original_text,
                'claims_identified': claims, 'matching_evidence': matches, 'claim_assessments': assessments,
                'established_facts': established, 'missing_information': missing,
                'author_clarifying_questions': questions,
                'grounding_notes': ['Removed wordiness without adding research assertions.'] if revised != original_text else [],
                'is_fully_grounded': bool(claims) and not missing and not any(a['verification_status'] == 'contradicted' for a in assessments),
                'validation_status': 'valid' if okay and ql_okay else 'validation_warning',
                'fact_violations': violations + ql_violations, 'requires_author_approval': True,
                'workflow_step': 'Evidence assessed; awaiting author review'}

    @classmethod
    def _extract_main_claims(cls, text: str) -> List[str]:
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.split()) >= 3]
