import {
  DocumentItem,
  DocumentBlock,
  ReferenceSource,
  AnalysisSummary,
  EditSuggestion,
  RevisionEvent,
  PreservationReport,
  ExportItem,
  AppSettings,
  DetectorHighlight,
  FlaggedVsUnflaggedResponse,
  ResearchEvidence,
  ReportComparison,
  GroundedRevision
} from '../types';

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') + '/api';

export class ApiError extends Error {
  constructor(message: string, public status: number, public detail: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The operation could not be completed.';
}

// Every response is checked here, including reads and review actions. A failed
// mutation must never reach the caller's success branch.
async function checkedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    const defaultInit: RequestInit = {
      credentials: 'include',
      ...init,
    };
    const response = await fetch(input, defaultInit);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail ?? body;
      const message = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map(item => item.msg || JSON.stringify(item)).join('; ')
        : detail?.message || detail?.error || `Request failed (${response.status}).`;
      throw new ApiError(message, response.status, detail);
    }
    return response;
  } catch (error) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('studio-error', { detail: errorMessage(error) }));
    }
    throw error;
  }
}

export async function downloadFile(url: string, filename?: string): Promise<void> {
  const response = await checkedFetch(url);
  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename || response.headers.get('content-disposition')?.match(/filename="?([^";]+)/)?.[1] || 'download';
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export function downloadJson(value: unknown, filename: string): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  // Authentication & VIT Student Identity
  async googleLogin(idToken: string) {
    const res = await checkedFetch(`${API_BASE}/auth/google-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken }),
    });
    return res.json();
  },

  async getMe() {
    const res = await checkedFetch(`${API_BASE}/auth/me`);
    return res.json();
  },

  async logout() {
    const res = await checkedFetch(`${API_BASE}/auth/logout`, { method: 'POST' });
    return res.json();
  },

  async eraseMyData() {
    const res = await checkedFetch(`${API_BASE}/auth/erase-my-data`, { method: 'POST' });
    return res.json();
  },

  // Payments & Billing (Integer Paise)
  async getPaymentPlans() {
    const res = await checkedFetch(`${API_BASE}/payments/plans`);
    return res.json();
  },

  async createPaymentOrder(planTier: string, operatingMode: string) {
    const res = await checkedFetch(`${API_BASE}/payments/create-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_tier: planTier, operating_mode: operatingMode }),
    });
    return res.json();
  },

  async verifyPayment(orderId: string, paymentId: string, signature: string) {
    const res = await checkedFetch(`${API_BASE}/payments/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        razorpay_order_id: orderId,
        razorpay_payment_id: paymentId,
        razorpay_signature: signature,
      }),
    });
    return res.json();
  },

  async createUpgradeOrder(entitlementId: string, targetTier: string) {
    const res = await checkedFetch(`${API_BASE}/payments/upgrade-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entitlement_id: entitlementId, target_tier: targetTier }),
    });
    return res.json();
  },

  async verifyUpgrade(entitlementId: string, targetTier: string, orderId: string, paymentId: string, signature: string) {
    const res = await checkedFetch(`${API_BASE}/payments/verify-upgrade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        entitlement_id: entitlementId,
        target_tier: targetTier,
        razorpay_order_id: orderId,
        razorpay_payment_id: paymentId,
        razorpay_signature: signature,
      }),
    });
    return res.json();
  },

  async getMyEntitlements() {
    const res = await checkedFetch(`${API_BASE}/payments/my-entitlements`);
    return res.json();
  },

  async getMyPurchases() {
    const res = await checkedFetch(`${API_BASE}/payments/my-purchases`);
    return res.json();
  },

  // Upload Gate & Quarantine
  async requestUploadToken(entitlementId: string) {
    const formData = new FormData();
    formData.append('entitlement_id', entitlementId);
    const res = await checkedFetch(`${API_BASE}/upload-gate/request-token`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  async uploadAuthorizedDocument(uploadToken: string, file: File) {
    const formData = new FormData();
    formData.append('upload_token', uploadToken);
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/upload-gate/upload`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 422 && data.status === 'OVER_LIMIT') {
      return { overLimit: true, ...data };
    }
    if (!res.ok) {
      throw new ApiError(data.detail || 'Upload failed', res.status, data);
    }
    return { overLimit: false, ...data };
  },

  // Health
  getHealth: async () => {
    const res = await checkedFetch(`${API_BASE}/health`);
    return res.json();
  },

  // Documents
  listDocuments: async (): Promise<DocumentItem[]> => {
    const res = await checkedFetch(`${API_BASE}/documents`);
    return res.json();
  },

  getDocument: async (id: string): Promise<DocumentItem> => {
    const res = await checkedFetch(`${API_BASE}/documents/${id}`);
    return res.json();
  },

  getDocumentStructure: async (id: string): Promise<{ document_id: string; sections: string[]; total_blocks: number; blocks: DocumentBlock[] }> => {
    const res = await checkedFetch(`${API_BASE}/documents/${id}/structure`);
    return res.json();
  },

  uploadDocument: async (file: File): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await checkedFetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  deleteDocument: async (id: string): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' });
    return res.json();
  },

  // Sources
  listSources: async (docId: string): Promise<ReferenceSource[]> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/sources`);
    return res.json();
  },

  uploadSource: async (docId: string, file: File, isExternalReport: boolean = false): Promise<ReferenceSource> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('is_external_report', String(isExternalReport));
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/sources`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Source upload failed');
    }
    return res.json();
  },

  // Analysis
  startAnalysis: async (docId: string, mode: string = 'academic_revision', profile: string = 'general'): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ editing_mode: mode, profile }),
    });
    return res.json();
  },

  getAnalysisStatus: async (docId: string): Promise<{ document_id: string; status: string; metadata: any; job?: { id: string; status: string; stage: string; progress: number; error?: string; cancel_requested?: boolean } }> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/analysis/status`);
    return res.json();
  },

  getAnalysisResults: async (docId: string): Promise<AnalysisSummary> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/analysis`);
    return res.json();
  },

  // Suggestions
  listSuggestions: async (docId: string): Promise<EditSuggestion[]> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/suggestions`);
    return res.json();
  },

  acceptSuggestion: async (suggestionId: string, userNotes?: string, approveFactChanges = false): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/suggestions/${suggestionId}/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_notes: userNotes, approve_fact_changes: approveFactChanges }),
    });
    return res.json();
  },

  rejectSuggestion: async (suggestionId: string, userNotes?: string): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/suggestions/${suggestionId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_notes: userNotes }),
    });
    return res.json();
  },

  reviseSuggestion: async (suggestionId: string, revisedText: string, userNotes?: string, approveFactChanges = false): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/suggestions/${suggestionId}/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revised_text: revisedText, user_notes: userNotes, approve_fact_changes: approveFactChanges }),
    });
    return res.json();
  },

  reviseBlockManually: async (blockId: string, newText: string, userNotes?: string, approveFactChanges = false): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/blocks/${blockId}/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_text: newText, user_notes: userNotes, approve_fact_changes: approveFactChanges }),
    });
    return res.json();
  },

  // Revisions & History
  listRevisions: async (docId: string): Promise<RevisionEvent[]> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/revisions`);
    return res.json();
  },

  restoreBlock: async (docId: string, blockId: string): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/restore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ block_id: blockId }),
    });
    return res.json();
  },

  // Validation
  validateDocument: async (docId: string): Promise<PreservationReport> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/validate`, {
      method: 'POST',
    });
    return res.json();
  },

  // Exports
  exportDocx: async (docId: string): Promise<ExportItem> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/export/docx`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('DOCX Export failed');
    return res.json();
  },

  exportPdf: async (docId: string): Promise<ExportItem> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/export/pdf`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('PDF Export failed');
    return res.json();
  },

  exportAuditCsv: async (docId: string): Promise<ExportItem> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/export/audit-csv`, {
      method: 'POST',
    });
    return res.json();
  },

  // External Detector Highlights & PDF Import
  uploadDetectorPdf: async (docId: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/detector-pdf`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Detector PDF upload failed');
    }
    return res.json();
  },

  listDetectorHighlights: async (docId: string): Promise<DetectorHighlight[]> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/detector-highlights`);
    return res.json();
  },

  manuallyMapHighlight: async (highlightId: string, blockId: string): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/documents/detector-highlights/${highlightId}/map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ block_id: blockId }),
    });
    return res.json();
  },

  getFlaggedVsUnflaggedComparison: async (docId: string): Promise<FlaggedVsUnflaggedResponse> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/flagged-comparison`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Flagged comparison failed');
    }
    return res.json();
  },

  compareDetectorReports: async (docId: string, file2: File, file1?: File): Promise<ReportComparison> => {
    const formData = new FormData();
    formData.append('file2', file2);
    if (file1) {
      formData.append('file1', file1);
    }
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/compare-reports`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Report comparison failed');
    }
    return res.json();
  },

  groundBlockRevision: async (docId: string, blockId: string): Promise<GroundedRevision> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/blocks/${blockId}/ground-revision`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Evidence grounding failed');
    }
    return res.json();
  },

  // Research Evidence & Verification
  addResearchEvidence: async (docId: string, formData: FormData): Promise<ResearchEvidence> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/evidence`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Evidence upload failed');
    }
    return res.json();
  },

  listResearchEvidence: async (docId: string): Promise<ResearchEvidence[]> => {
    const res = await checkedFetch(`${API_BASE}/documents/${docId}/evidence`);
    return res.json();
  },

  verifyClaimWithEvidence: async (findingId: string, evidenceId: string, userNotes?: string): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/claims/${findingId}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ evidence_id: evidenceId, user_notes: userNotes }),
    });
    return res.json();
  },

  cancelJob: async (id: string) => (await checkedFetch(`${API_BASE}/jobs/${id}/cancel`, { method: 'POST' })).json(),
  reviewFinding: async (id: string, reviewStatus: string, userNotes?: string) => (await checkedFetch(`${API_BASE}/findings/${id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ review_status: reviewStatus, user_notes: userNotes }) })).json(),
  listVersions: async (id: string): Promise<Array<{ id: string; version_number: number; label: string; created_at: string; is_current: boolean }>> => (await checkedFetch(`${API_BASE}/documents/${id}/versions`)).json(),
  restoreVersion: async (id: string, versionId: string) => (await checkedFetch(`${API_BASE}/documents/${id}/restore`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId }) })).json(),
  undo: async (id: string) => (await checkedFetch(`${API_BASE}/documents/${id}/undo`, { method: 'POST' })).json(),
  redo: async (id: string) => (await checkedFetch(`${API_BASE}/documents/${id}/redo`, { method: 'POST' })).json(),
  listDetectorReports: async (id: string): Promise<Array<Record<string, any>>> => (await checkedFetch(`${API_BASE}/documents/${id}/detector-reports`)).json(),

  // Settings
  getSettings: async (): Promise<AppSettings> => {
    const res = await checkedFetch(`${API_BASE}/settings`);
    return res.json();
  },

  updateSettings: async (settings: Partial<AppSettings> & { openai_api_key?: string; gemini_api_key?: string }): Promise<any> => {
    const res = await checkedFetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    return res.json();
  },

  testProvider: async (name: string): Promise<{ provider: string; available: boolean }> => {
    const res = await checkedFetch(`${API_BASE}/settings/test-provider/${name}`);
    return res.json();
  },
};
