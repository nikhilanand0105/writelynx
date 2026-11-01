"""Atomic author revisions with stale-edit checks, fact approvals and immutable snapshots."""
import datetime
import threading
import uuid
from contextlib import contextmanager
from typing import Optional

from sqlalchemy.orm import Session
from backend.app.models.models import Document, DocumentBlock, DocumentVersion, EditSuggestion, RevisionEvent, AnalysisJob
from backend.app.services.fact_validator import FactValidator

_locks = [threading.RLock() for _ in range(64)]


@contextmanager
def document_lock(document_id):
    with _locks[hash(document_id) % len(_locks)]:
        yield


class RevisionConflict(ValueError):
    def __init__(self, message, violations=None, requires_fact_approval=False):
        super().__init__(message)
        self.detail = {"message": message, "violations": violations or [], "requires_fact_approval": requires_fact_approval}


class RevisionManager:
    @staticmethod
    def _snapshot(db, doc, label, original=False):
        db.flush()
        versions = db.query(DocumentVersion).filter_by(document_id=doc.id).all()
        meta = dict(doc.doc_metadata or {})
        blocks = db.query(DocumentBlock).filter_by(document_id=doc.id).all()
        version = DocumentVersion(
            id=str(uuid.uuid4()), document_id=doc.id,
            version_number=max((v.version_number for v in versions), default=-1) + 1,
            parent_id=meta.get("current_version_id"), label=label,
            snapshot={"blocks": {b.id: {"text": b.original_text if original else b.current_text,
                         "fact_change_approval": None if original else (b.structure_metadata or {}).get("fact_change_approval")} for b in blocks},
                      "suggestions": {s.id: s.review_status for s in db.query(EditSuggestion).filter_by(document_id=doc.id)}},
        )
        db.add(version)
        db.flush()
        doc.doc_metadata = {**meta, "current_version_id": version.id, "redo_stack": []}
        return version

    @staticmethod
    def ensure_initial_version(db, doc):
        if not db.query(DocumentVersion).filter_by(document_id=doc.id).first():
            RevisionManager._snapshot(db, doc, "Original upload", original=True)
            if any(b.current_text != b.original_text for b in doc.blocks):
                RevisionManager._snapshot(db, doc, "Imported existing revisions")

    @staticmethod
    def _ready(db, block):
        doc = db.get(Document, block.document_id)
        if db.query(AnalysisJob).filter(AnalysisJob.document_id == doc.id, AnalysisJob.status.in_(["queued", "running"])).first():
            raise RevisionConflict("Wait for analysis to finish or cancel it before editing.")
        RevisionManager.ensure_initial_version(db, doc)
        return doc

    @staticmethod
    def _validate(block, new_text, approve_fact_changes=False, user_notes=None):
        if len(new_text) > 200000 or not new_text.strip():
            raise RevisionConflict("A revision must contain text and be at most 200,000 characters.")
        if new_text == block.current_text:
            return
        if block.is_protected or (block.structure_metadata or {}).get("editable") is False:
            raise RevisionConflict("This block contains protected structure. Its original XML is preserved; edit it in Word instead.")
        intact, violations = FactValidator.compare_facts(block.current_text, new_text)
        if not intact:
            if not approve_fact_changes or not (user_notes or "").strip():
                raise RevisionConflict("Protected facts or citations changed. Explicit author approval and an explanation are required.", violations, True)
            block.structure_metadata = {**(block.structure_metadata or {}), "fact_change_approval": {
                "before_text": block.current_text, "after_text": new_text, "violations": violations,
                "reason": user_notes, "approved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }}

    @staticmethod
    def _event(db, block, event_type, before, after, notes, tag):
        event = RevisionEvent(id=str(uuid.uuid4()), document_id=block.document_id, block_id=block.id,
                              event_type=event_type, before_text=before, after_text=after,
                              user_notes=notes, attribution_tag=tag)
        db.add(event)
        return event

    @staticmethod
    def accept_suggestion(db: Session, suggestion_id: str, user_notes: Optional[str] = None, approve_fact_changes=False, revised_text=None):
        sug = db.get(EditSuggestion, suggestion_id)
        if not sug:
            raise ValueError("Suggestion not found.")
        with document_lock(sug.document_id):
            db.refresh(sug)
            if sug.review_status not in {"pending", "revised"}:
                raise RevisionConflict("This suggestion has already been reviewed.")
            block = db.get(DocumentBlock, sug.block_id)
            db.refresh(block)
            doc = RevisionManager._ready(db, block)
            if block.current_text != sug.original_text:
                raise RevisionConflict("The paragraph changed after this suggestion was created. Analyze again or edit the current text.")
            proposed = revised_text if revised_text is not None else sug.proposed_text
            RevisionManager._validate(block, proposed, approve_fact_changes, user_notes)
            before = block.current_text
            block.current_text = proposed
            sug.proposed_text = proposed
            sug.review_status = "accepted"
            facts_ok, _ = FactValidator.compare_facts(before, proposed)
            sug.protected_entities_preserved = sug.citations_preserved = facts_ok
            sug.validation_status = "valid" if facts_ok else "author_approved_fact_change"
            event = RevisionManager._event(db, block, "accept_suggestion", before, proposed, user_notes or sug.reason,
                                           "manual_revision" if revised_text is not None else "author_approved_suggestion")
            version = RevisionManager._snapshot(db, doc, "Accepted revision")
            db.commit()
            return {"success": True, "block_id": block.id, "current_text": block.current_text, "event_id": event.id, "version_id": version.id}

    @staticmethod
    def reject_suggestion(db: Session, suggestion_id: str, user_notes: Optional[str] = None):
        sug = db.get(EditSuggestion, suggestion_id)
        if not sug:
            raise ValueError("Suggestion not found.")
        with document_lock(sug.document_id):
            db.refresh(sug)
            if sug.review_status not in {"pending", "revised"}:
                raise RevisionConflict("This suggestion has already been reviewed.")
            block = db.get(DocumentBlock, sug.block_id)
            doc = RevisionManager._ready(db, block)
            sug.review_status = "rejected"
            RevisionManager._event(db, block, "reject_suggestion", block.current_text, block.current_text,
                                   user_notes or f"Rejected proposed wording: {sug.proposed_text}", "original_author")
            RevisionManager._snapshot(db, doc, "Rejected suggestion (text unchanged)")
            db.commit()
            return {"success": True, "suggestion_id": suggestion_id, "status": "rejected"}

    @staticmethod
    def revise_block_manually(db: Session, block_id: str, new_text: str, user_notes: Optional[str] = None, approve_fact_changes=False):
        block = db.get(DocumentBlock, block_id)
        if not block:
            raise ValueError("Block not found.")
        with document_lock(block.document_id):
            db.refresh(block)
            doc = RevisionManager._ready(db, block)
            RevisionManager._validate(block, new_text, approve_fact_changes, user_notes)
            before = block.current_text
            block.current_text = new_text
            event = RevisionManager._event(db, block, "manual_edit", before, new_text, user_notes or "Manual author edit", "manual_revision")
            version = RevisionManager._snapshot(db, doc, "Manual author edit")
            db.commit()
            return {"success": True, "block_id": block.id, "current_text": new_text, "event_id": event.id, "version_id": version.id}

    @staticmethod
    def restore_block_original(db: Session, block_id: str, document_id=None):
        block = db.get(DocumentBlock, block_id)
        if not block or (document_id and block.document_id != document_id):
            raise ValueError("Block not found in this document.")
        with document_lock(block.document_id):
            db.refresh(block)
            doc = RevisionManager._ready(db, block)
            before = block.current_text
            block.current_text = block.original_text
            block.structure_metadata = {**(block.structure_metadata or {}), "fact_change_approval": None}
            event = RevisionManager._event(db, block, "restore_original", before, block.original_text, "Restored original wording", "original_author")
            version = RevisionManager._snapshot(db, doc, "Restored original paragraph")
            db.commit()
            return {"success": True, "block_id": block.id, "current_text": block.current_text, "event_id": event.id, "version_id": version.id}

    @staticmethod
    def navigate_version(db, document_id, action, version_id=None):
        with document_lock(document_id):
            doc = db.get(Document, document_id)
            if not doc:
                raise ValueError("Document not found.")
            if db.query(AnalysisJob).filter(AnalysisJob.document_id == doc.id, AnalysisJob.status.in_(["queued", "running"])).first():
                raise RevisionConflict("Cancel or finish analysis before changing versions.")
            RevisionManager.ensure_initial_version(db, doc)
            meta = dict(doc.doc_metadata or {})
            current = db.get(DocumentVersion, meta["current_version_id"])
            redo = list(meta.get("redo_stack", []))
            if action == "undo":
                target_id = current.parent_id
                redo.append(current.id)
            elif action == "redo":
                target_id = redo.pop() if redo else None
            else:
                target_id = version_id
            target = db.get(DocumentVersion, target_id) if target_id else None
            if not target or target.document_id != doc.id:
                raise RevisionConflict("No matching version is available.")
            for block in db.query(DocumentBlock).filter_by(document_id=doc.id):
                saved = target.snapshot["blocks"].get(block.id)
                if saved:
                    before = block.current_text
                    block.current_text = saved["text"]
                    block.structure_metadata = {**(block.structure_metadata or {}), "fact_change_approval": saved.get("fact_change_approval")}
                    if before != block.current_text:
                        RevisionManager._event(db, block, action, before, block.current_text, f"Version {target.version_number}: {target.label}", "manual_revision")
            statuses = target.snapshot.get("suggestions", {})
            for sug in db.query(EditSuggestion).filter_by(document_id=doc.id):
                sug.review_status = statuses.get(sug.id, "pending")
            if action == "restore_version":
                version = RevisionManager._snapshot(db, doc, f"Restored version {target.version_number}")
            else:
                doc.doc_metadata = {**meta, "current_version_id": target.id, "redo_stack": redo}
                version = target
            db.commit()
            return {"success": True, "version_id": version.id, "version_number": version.version_number}
