import datetime
import uuid
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, JSON
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


# ==============================================================================
# AUTHENTICATION & MULTI-TENANCY (PHASE 3 & 4)
# ==============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    hosted_domain = Column(String(100), default="vitstudent.ac.in")
    registration_number = Column(String(50), nullable=True, index=True)
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(50), default="student")  # "student", "admin"
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, default=datetime.datetime.utcnow)
    last_login_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")
    entitlements = relationship("Entitlement", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    restrictions = relationship("UserRestriction", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=True, index=True)
    session_token_hash = Column(String(64), unique=True, nullable=True, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="sessions")


class UserRestriction(Base):
    __tablename__ = "user_restrictions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    restriction_type = Column(String(50), default="suspension")
    reason = Column(Text, nullable=False)
    created_by = Column(String(255), default="system")
    restricted_by = Column(String(255), default="system")
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="restrictions")


# ==============================================================================
# BILLING, PAYMENTS & ENTITLEMENTS (PHASE 5 & 6)
# ==============================================================================

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_tier = Column(String(50), nullable=True)
    plan_id = Column(String(50), nullable=True)
    operating_mode = Column(String(50), default="academic_revision")
    mode = Column(String(50), default="academic_revision")
    amount_paise = Column(Integer, nullable=False)  # Stored in integer paise (e.g. 2000 = ₹20)
    currency = Column(String(10), default="INR")
    razorpay_order_id = Column(String(255), unique=True, nullable=True, index=True)
    gateway_order_id = Column(String(255), unique=True, nullable=True, index=True)
    razorpay_payment_id = Column(String(255), nullable=True, index=True)
    gateway_payment_id = Column(String(255), nullable=True, index=True)
    razorpay_signature = Column(String(255), nullable=True)
    gateway_signature = Column(String(255), nullable=True)
    status = Column(String(50), default="PENDING")
    is_upgrade = Column(Boolean, default=False)
    parent_purchase_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="purchases")
    entitlements = relationship("Entitlement", back_populates="purchase", cascade="all, delete-orphan")


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_id = Column(String(36), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_tier = Column(String(50), nullable=True)
    plan_id = Column(String(50), nullable=True)
    operating_mode = Column(String(50), default="academic_revision")
    mode = Column(String(50), default="academic_revision")
    max_pages = Column(Integer, default=4)
    max_characters = Column(Integer, default=15000)
    max_file_size_mb = Column(Integer, default=10)
    ai_budget_paise = Column(Integer, default=400)
    status = Column(String(50), default="AVAILABLE")
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    consumed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="entitlements")
    purchase = relationship("Purchase", back_populates="entitlements")
    upload_reservations = relationship("UploadReservation", back_populates="entitlement", cascade="all, delete-orphan")


class UploadReservation(Base):
    __tablename__ = "upload_reservations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entitlement_id = Column(String(36), ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_token = Column(String(64), unique=True, nullable=False, index=True)
    destination_key = Column(String(512), nullable=True)
    plan_tier = Column(String(50), default="basic")
    operating_mode = Column(String(50), default="academic_revision")
    max_file_size_bytes = Column(Integer, default=10 * 1024 * 1024)
    status = Column(String(50), default="PENDING")
    is_consumed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    entitlement = relationship("Entitlement", back_populates="upload_reservations")


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    gateway = Column(String(50), default="razorpay")
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict)
    payload_json = Column(JSON, default=dict)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AICostReservation(Base):
    __tablename__ = "ai_cost_reservations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id = Column(String(50), nullable=True, index=True)
    entitlement_id = Column(String(36), ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=True, index=True)
    plan_tier = Column(String(50), default="basic")
    budget_allocated_paise = Column(Integer, default=400)
    cost_incurred_paise = Column(Integer, default=0)
    reserved_paise = Column(Integer, default=0)
    actual_paise = Column(Integer, default=0)
    provider_used = Column(String(50), default="no_llm")
    model_name = Column(String(100), default="gemini-1.5-flash")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    status = Column(String(50), default="RESERVED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(255), default="false")
    value_json = Column(JSON, default=dict)
    description = Column(Text, nullable=True)
    updated_by = Column(String(36), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ==============================================================================
# CORE DOCUMENT PROCESSING (EXISTING & ENHANCED)
# ==============================================================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    entitlement_id = Column(String(36), nullable=True, index=True)
    plan_tier = Column(String(50), nullable=True)  # BASIC, STANDARD, EXTENDED
    operating_mode = Column(String(50), default="academic_revision")
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    processing_status = Column(String(50), default="ready")  # ready, analyzing, analyzed, error
    word_count = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    original_paragraph_count = Column(Integer, default=0)
    table_count = Column(Integer, default=0)
    image_count = Column(Integer, default=0)
    
    # External detector PDF fields
    detector_pdf_path = Column(String(512), nullable=True)
    detector_name = Column(String(100), nullable=True)  # e.g. "ZeroGPT", "Turnitin"
    detector_score = Column(Float, nullable=True)       # Reported score from PDF header (e.g. 78.4%)
    is_truncated = Column(Boolean, default=False)       # True if detector PDF evaluated only part of document
    
    doc_metadata = Column(JSON, default=dict)

    # Relationships
    user = relationship("User", back_populates="documents")
    blocks = relationship("DocumentBlock", back_populates="document", cascade="all, delete-orphan", order_by="DocumentBlock.block_index")
    sources = relationship("ReferenceSource", back_populates="document", cascade="all, delete-orphan")
    findings = relationship("AnalysisFinding", back_populates="document", cascade="all, delete-orphan")
    suggestions = relationship("EditSuggestion", back_populates="document", cascade="all, delete-orphan")
    revisions = relationship("RevisionEvent", back_populates="document", cascade="all, delete-orphan", order_by="desc(RevisionEvent.timestamp)")
    exports = relationship("Export", back_populates="document", cascade="all, delete-orphan", order_by="desc(Export.created_at)")
    detector_highlights = relationship("DetectorHighlight", back_populates="document", cascade="all, delete-orphan")
    research_evidence = relationship("ResearchEvidence", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", cascade="all, delete-orphan")
    detector_reports = relationship("DetectorReport", cascade="all, delete-orphan")
    verifications = relationship("ClaimVerification", cascade="all, delete-orphan")


class DocumentBlock(Base):
    __tablename__ = "document_blocks"

    id = Column(String(50), primary_key=True, index=True)  # e.g., doc_123_p_0042
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    block_index = Column(Integer, nullable=False, index=True)
    section_id = Column(String(100), default="General")
    block_type = Column(String(50), default="paragraph")  # title, abstract, heading, paragraph, list_item, table_cell, caption, etc.
    original_text = Column(Text, nullable=False)
    current_text = Column(Text, nullable=False)
    is_protected = Column(Boolean, default=False)
    has_detector_highlight = Column(Boolean, default=False)
    structure_metadata = Column(JSON, default=dict)  # runs, styling, xml path, attributes

    document = relationship("Document", back_populates="blocks")
    findings = relationship("AnalysisFinding", back_populates="block", cascade="all, delete-orphan")
    suggestions = relationship("EditSuggestion", back_populates="block", cascade="all, delete-orphan")
    detector_highlights = relationship("DetectorHighlight", back_populates="block")


class DetectorHighlight(Base):
    __tablename__ = "detector_highlights"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    block_id = Column(String(50), ForeignKey("document_blocks.id", ondelete="SET NULL"), nullable=True, index=True)
    page_number = Column(Integer, nullable=False)
    highlight_text = Column(Text, nullable=False)
    bbox = Column(JSON, default=list)  # [x0, y0, x1, y1]
    match_confidence = Column(Float, default=0.0)
    mapping_status = Column(String(50), default="unresolved")  # matched, unresolved, manually_corrected
    detector_name = Column(String(100), default="ZeroGPT")
    extraction_strategy = Column(String(50), default="native_rectangles")  # native_rectangles, fallback_ocr
    metadata_json = Column(JSON, default=dict)

    document = relationship("Document", back_populates="detector_highlights")
    block = relationship("DocumentBlock", back_populates="detector_highlights")


class ResearchEvidence(Base):
    __tablename__ = "research_evidence"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type = Column(String(50), default="text")  # text, paper_snippet, benchmark_metric, user_note
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    doi_or_url = Column(String(512), nullable=True)
    citation_key = Column(String(100), nullable=True)  # e.g., "vaswani2017attention"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    metadata_json = Column(JSON, default=dict)

    document = relationship("Document", back_populates="research_evidence")


class ReferenceSource(Base):
    __tablename__ = "reference_sources"

    id = Column(String(36), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    source_type = Column(String(50), default="text")  # text, upload_docx, upload_pdf, upload_txt, url
    source_url = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=True)
    extracted_text = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=True)
    token_count = Column(Integer, default=0)
    source_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("Document", back_populates="sources")
    findings = relationship("AnalysisFinding", back_populates="source", cascade="all, delete-orphan")


class AnalysisFinding(Base):
    __tablename__ = "analysis_findings"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    block_id = Column(String(50), ForeignKey("document_blocks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("reference_sources.id", ondelete="CASCADE"), nullable=True)
    
    finding_type = Column(String(50), nullable=False, default="diagnostic")
    issue_category = Column(String(50), default="general")
    severity = Column(String(20), default="medium")  # high, medium, low, info
    external_detector_highlight = Column(Boolean, default=False)
    matched_text = Column(Text, nullable=True)
    source_matched_text = Column(Text, nullable=True)
    similarity_score = Column(Float, default=0.0)
    match_type = Column(String(50), default="exact")
    evidence = Column(JSON, default=dict)
    required_evidence = Column(JSON, default=list)
    recommended_action = Column(String(100), default="verify_claim")
    requires_author_input = Column(Boolean, default=True)
    review_status = Column(String(50), default="pending")
    category = Column(String(50), nullable=True)
    source_snippet = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    detector_highlight_id = Column(String(50), nullable=True)

    document = relationship("Document", back_populates="findings")
    block = relationship("DocumentBlock", back_populates="findings")
    source = relationship("ReferenceSource", back_populates="findings")


class EditSuggestion(Base):
    __tablename__ = "edit_suggestions"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    block_id = Column(String(50), ForeignKey("document_blocks.id", ondelete="CASCADE"), nullable=False, index=True)
    
    issue_type = Column(String(50), default="academic_revision")  # light_copyediting, academic_revision, research_grounded
    original_text = Column(Text, nullable=False)
    proposed_text = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    citations_preserved = Column(Boolean, default=True)
    protected_entities_preserved = Column(Boolean, default=True)
    requires_user_review = Column(Boolean, default=True)
    confidence = Column(Float, default=1.0)
    validation_status = Column(String(50), default="valid")
    review_status = Column(String(50), default="pending")

    document = relationship("Document", back_populates="suggestions")
    block = relationship("DocumentBlock", back_populates="suggestions")


class RevisionEvent(Base):
    __tablename__ = "revision_events"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    block_id = Column(String(50), ForeignKey("document_blocks.id", ondelete="CASCADE"), nullable=True)
    
    event_type = Column(String(50), nullable=False)  # accept_suggestion, reject_suggestion, manual_edit, restore_original, add_evidence
    before_text = Column(Text, nullable=True)
    after_text = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    user_notes = Column(Text, nullable=True)
    attribution_tag = Column(String(50), default="user_approved_ai")  # original_author, manual_revision, ai_suggested, user_approved_ai

    document = relationship("Document", back_populates="revisions")


class Export(Base):
    __tablename__ = "exports"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    export_type = Column(String(20), nullable=False)  # docx, pdf, log_json, audit_csv
    file_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    preservation_report = Column(JSON, default=dict)

    document = relationship("Document", back_populates="exports")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    parent_id = Column(String(36), nullable=True)
    label = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    snapshot = Column(JSON, nullable=False)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    entitlement_id = Column(String(36), nullable=True, index=True)
    status = Column(String(32), default="queued", nullable=False)  # queued, validating, running, validating_output, completed, retryable_failure, permanent_failure, cancelled
    stage = Column(String(128), default="Queued")
    progress = Column(Integer, default=0)
    cancel_requested = Column(Boolean, default=False)
    worker_id = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    parameters = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class DetectorReport(Base):
    __tablename__ = "detector_reports"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    metadata_json = Column(JSON, default=dict)


class ClaimVerification(Base):
    __tablename__ = "claim_verifications"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id = Column(String(50), nullable=False)
    evidence_id = Column(String(50), nullable=False)
    verification_status = Column(String(64), nullable=False)
    rationale = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
