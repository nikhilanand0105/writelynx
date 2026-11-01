export interface DocumentItem {
  id: string;
  filename: string;
  word_count: number;
  processing_status: 'ready' | 'analyzing' | 'analyzed' | 'error' | 'cancelled' | 'uploaded';
  uploaded_at: string;
  original_paragraph_count: number;
  table_count: number;
  image_count: number;
  detector_pdf_path?: string;
  detector_name?: string;
  detector_score?: number;
  is_truncated?: boolean;
  doc_metadata: Record<string, any>;
}

export interface DocumentBlock {
  id: string;
  document_id: string;
  block_index: number;
  section_id: string;
  block_type: string;
  original_text: string;
  current_text: string;
  is_protected: boolean;
  has_detector_highlight?: boolean;
  structure_metadata: Record<string, any>;
}

export interface ReferenceSource {
  id: string;
  document_id: string;
  title: string;
  source_type: string;
  source_url?: string;
  file_path?: string;
  token_count: number;
  source_metadata: Record<string, any>;
}

export interface AnalysisFinding {
  id: string;
  document_id: string;
  block_id: string;
  source_id?: string;
  finding_type: string;
  issue_category?: string;
  severity: 'high' | 'medium' | 'low' | 'info';
  external_detector_highlight?: boolean;
  matched_text?: string;
  source_matched_text?: string;
  similarity_score: number;
  match_type: string;
  evidence: Record<string, any>;
  required_evidence?: string[];
  recommended_action?: string;
  requires_author_input?: boolean;
  review_status: 'pending' | 'accepted' | 'rejected' | 'resolved' | 'verified' | 'user_reviewed';
}

export interface DetectorHighlight {
  id: string;
  document_id: string;
  block_id?: string;
  page_number: number;
  highlight_text: string;
  bbox: number[];
  match_confidence: number;
  mapping_status: 'matched' | 'unmapped' | 'manually_corrected' | 'unresolved' | string;
  detector_name: string;
  extraction_strategy: string;
  metadata_json: Record<string, any>;
}

export interface GroupCharacteristics {
  passage_count: number;
  word_count: number;
  avg_passage_length_words: number;
  avg_sentence_length_words: number;
  technical_term_density_pct: number;
  citation_presence_pct: number;
  enumerated_items_count: number;
  claim_specificity_score: number;
  readability_fk_grade: number;
  unsupported_assertions_count: number;
}

export interface FlaggedVsUnflaggedResponse {
  document_id: string;
  detector_name: string;
  sample_size_warning: string;
  disclaimer: string;
  highlighted_passages: GroupCharacteristics;
  unhighlighted_passages: GroupCharacteristics;
  observable_correlations: string[];
}

export interface ResearchEvidence {
  id: string;
  document_id: string;
  title: string;
  evidence_type: 'experiment_log' | 'source_code' | 'benchmark_table' | 'screenshot' | 'notes' | string;
  content?: string;
  file_path?: string;
  linked_blocks: string[];
  created_at: string;
  metadata_json: Record<string, any>;
}

export interface ReportComparison {
  earlier_report: {
    detector_name: string;
    reported_score?: number;
    is_truncated: boolean;
    total_fragments: number;
  };
  latest_report: {
    detector_name: string;
    reported_score?: number;
    is_truncated: boolean;
    total_fragments: number;
  };
  comparison_summary: {
    score_difference?: number;
    is_essentially_identical: boolean;
    overlapping_fragments_count: number;
    verbatim_identical_count: number;
    newly_highlighted_count: number;
    removed_highlighted_count: number;
    both_truncated: boolean;
    conclusion: string;
  };
  unchanged_highlights: Array<{
    earlier_fragment: any;
    latest_fragment: any;
    similarity_ratio: number;
    is_verbatim_identical: boolean;
  }>;
  newly_highlighted: any[];
  removed_highlights: any[];
  disclaimer: string;
}

export interface GroundedRevision {
  block_id: string;
  original_text: string;
  proposed_text: string;
  claims_identified: string[];
  matching_evidence: Array<{
    evidence_id: string;
    title: string;
    evidence_type: string;
    content_snippet: string;
  }>;
  established_facts: string[];
  missing_information: string[];
  author_clarifying_questions: Array<{
    topic: string;
    question: string;
    suggested_evidence: string;
  }>;
  grounding_notes: string[];
  is_fully_grounded: boolean;
  validation_status: string;
  fact_violations: string[];
  requires_author_approval: boolean;
  workflow_step: string;
}

export interface DiagnosticMetrics {
  total_document_words: number;
  analyzed_sources_count: number;
  matching_passages_count: number;
  exact_match_words: number;
  approximate_match_count: number;
  missing_citations_count: number;
  unattributed_overlap_count: number;
  reviewed_findings_count: number;
  unresolved_findings_count: number;
  local_textual_overlap_percentage: number;
}

export interface AnalysisSummary {
  document_id: string;
  status: string;
  metrics: DiagnosticMetrics;
  findings: AnalysisFinding[];
}

export interface EditSuggestion {
  id: string;
  document_id: string;
  block_id: string;
  issue_type: string;
  original_text: string;
  proposed_text: string;
  reason: string;
  citations_preserved: boolean;
  protected_entities_preserved: boolean;
  requires_user_review: boolean;
  confidence: number;
  validation_status: string;
  review_status: 'pending' | 'accepted' | 'rejected' | 'revised';
}

export interface RevisionEvent {
  id: string;
  document_id: string;
  block_id?: string;
  event_type: string;
  before_text?: string;
  after_text?: string;
  timestamp: string;
  user_notes?: string;
  attribution_tag: string;
}

export interface PreservationReport {
  valid: boolean;
  archive_valid: boolean;
  reopened_successfully: boolean;
  original_paragraph_count: number;
  final_paragraph_count: number;
  paragraph_count_match: boolean;
  table_count: number;
  image_count: number;
  protected_facts_intact: boolean;
  protected_fact_violations: string[];
  citation_integrity_intact: boolean;
  citation_warnings: string[];
  warnings: string[];
}

export interface ExportItem {
  id: string;
  document_id: string;
  export_type: 'docx' | 'pdf' | 'audit_csv' | 'log_json';
  download_url: string;
  created_at: string;
  preservation_report?: PreservationReport;
}

export interface AppSettings {
  project_name: string;
  default_llm_provider: string;
  ollama_host: string;
  ollama_model: string;
  openai_model: string;
  openai_base_url?: string;
  gemini_model: string;
  has_openai_key: boolean;
  has_gemini_key: boolean;
  libreoffice_available: boolean;
  offline_only: boolean;
}
