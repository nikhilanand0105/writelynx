from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

# Document Schemas
class DocumentBase(BaseModel):
    filename: str
    word_count: int
    processing_status: str

class DocumentResponse(DocumentBase):
    id: str
    uploaded_at: datetime
    original_paragraph_count: int
    table_count: int
    image_count: int
    detector_name: Optional[str] = None
    detector_score: Optional[float] = None
    is_truncated: bool = False
    doc_metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True

# Block Schemas
class DocumentBlockResponse(BaseModel):
    id: str
    document_id: str
    block_index: int
    section_id: str
    block_type: str
    original_text: str
    current_text: str
    is_protected: bool
    has_detector_highlight: bool = False
    structure_metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True

class DocumentStructureResponse(BaseModel):
    document_id: str
    sections: List[str]
    total_blocks: int
    blocks: List[DocumentBlockResponse]

# Detector Highlight Schemas
class DetectorHighlightResponse(BaseModel):
    id: str
    document_id: str
    block_id: Optional[str] = None
    page_number: int
    highlight_text: str
    bbox: List[float] = []
    match_confidence: float = 0.0
    mapping_status: str = "unresolved"
    detector_name: str = "ZeroGPT"
    extraction_strategy: str = "native_rectangles"
    metadata_json: Dict[str, Any] = {}

    class Config:
        from_attributes = True

class DetectorHighlightManualMapRequest(BaseModel):
    block_id: str

# Research Evidence Schemas
class ResearchEvidenceCreate(BaseModel):
    title: str
    evidence_type: str = "experiment_log"  # experiment_log, source_code, benchmark_table, screenshot, notes
    content: Optional[str] = None
    linked_blocks: List[str] = []
    metadata_json: Dict[str, Any] = {}

class ResearchEvidenceResponse(BaseModel):
    id: str
    document_id: str
    title: str
    evidence_type: str
    content: Optional[str] = None
    linked_blocks: List[str] = []
    created_at: datetime
    metadata_json: Dict[str, Any] = {}

    class Config:
        from_attributes = True

# Reference Source Schemas
class ReferenceSourceResponse(BaseModel):
    id: str
    document_id: str
    title: str
    source_type: str
    source_url: Optional[str] = None
    token_count: int
    source_metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True

# Analysis Finding Schemas
class AnalysisFindingResponse(BaseModel):
    id: str
    document_id: str
    block_id: str
    source_id: Optional[str] = None
    finding_type: str
    issue_category: str = "general"
    severity: str = "medium"
    external_detector_highlight: bool = False
    matched_text: Optional[str] = None
    source_matched_text: Optional[str] = None
    similarity_score: float = 0.0
    match_type: str = "exact"
    evidence: Dict[str, Any] = {}
    required_evidence: List[str] = []
    recommended_action: str = "verify_claim"
    requires_author_input: bool = True
    review_status: str = "pending"

    class Config:
        from_attributes = True

class DiagnosticMetrics(BaseModel):
    total_document_words: int
    analyzed_sources_count: int
    matching_passages_count: int
    exact_match_words: int
    approximate_match_count: int
    missing_citations_count: int
    unattributed_overlap_count: int
    reviewed_findings_count: int
    unresolved_findings_count: int
    local_textual_overlap_percentage: float

class AnalysisSummaryResponse(BaseModel):
    document_id: str
    status: str
    metrics: DiagnosticMetrics
    findings: List[AnalysisFindingResponse]

# Flagged vs Unflagged Comparison Schemas
class GroupCharacteristics(BaseModel):
    passage_count: int
    word_count: int
    avg_passage_length_words: float
    avg_sentence_length_words: float
    technical_term_density_pct: float
    citation_presence_pct: float
    enumerated_items_count: int
    claim_specificity_score: float
    readability_fk_grade: float
    unsupported_assertions_count: int

class FlaggedVsUnflaggedResponse(BaseModel):
    document_id: str
    detector_name: str
    sample_size_warning: str
    disclaimer: str
    highlighted_passages: GroupCharacteristics
    unhighlighted_passages: GroupCharacteristics
    observable_correlations: List[str]

# Suggestions Schemas
class EditSuggestionResponse(BaseModel):
    id: str
    document_id: str
    block_id: str
    issue_type: str
    original_text: str
    proposed_text: str
    reason: str
    citations_preserved: bool
    protected_entities_preserved: bool
    requires_user_review: bool
    confidence: float
    validation_status: str
    review_status: str

    class Config:
        from_attributes = True

class SuggestionReviseRequest(BaseModel):
    revised_text: str = Field(min_length=1, max_length=200000)
    user_notes: Optional[str] = None
    approve_fact_changes: bool = False

class ManualBlockEditRequest(BaseModel):
    new_text: str = Field(min_length=1, max_length=200000)
    user_notes: Optional[str] = None
    approve_fact_changes: bool = False

# Revision Event Schemas
class RevisionEventResponse(BaseModel):
    id: str
    document_id: str
    block_id: Optional[str]
    event_type: str
    before_text: Optional[str]
    after_text: Optional[str]
    timestamp: datetime
    user_notes: Optional[str]
    attribution_tag: str

    class Config:
        from_attributes = True

# Validation Schemas
class PreservationReport(BaseModel):
    model_config = {"extra": "allow"}
    valid: bool
    archive_valid: bool = True
    reopened_successfully: bool = True
    original_paragraph_count: int = 0
    final_paragraph_count: int = 0
    paragraph_count_match: bool = True
    table_count: int = 0
    image_count: int = 0
    protected_facts_intact: bool = True
    protected_fact_violations: List[str] = []
    citation_integrity_intact: bool = True
    citation_warnings: List[str] = []
    warnings: List[str] = []

# Export Schemas
class ExportResponse(BaseModel):
    id: str
    document_id: str
    export_type: str
    download_url: str
    created_at: datetime
    preservation_report: Optional[PreservationReport] = None

# Analysis Start Request
class AnalysisRequest(BaseModel):
    editing_mode: Literal["light_copyediting", "academic_revision", "research_grounded", "clarity", "natural_student_research", "source_grounded", "proofreading"] = "academic_revision"
    profile: Literal["general", "quantlens_xai"] = "general"
    enable_semantic: bool = True
    enable_fuzzy: bool = True
    ngram_size: int = 5
    llm_provider: Optional[Literal["no_llm", "ollama", "openai", "gemini", "custom"]] = None
