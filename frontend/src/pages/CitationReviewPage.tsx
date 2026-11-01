import React, { useEffect, useState } from 'react';
import { BookOpenCheck, CheckCircle, ExternalLink, Download, } from 'lucide-react';
import { api, downloadFile } from '../services/api';
import { AnalysisFinding } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export const CitationReviewPage: React.FC = () => {
  const { activeDocument, setActiveTab, setActiveBlockId } = useStudioStore();
  const [citationFindings, setCitationFindings] = useState<AnalysisFinding[]>([]);
  const [auditMeta, setAuditMeta] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (activeDocument) {
      loadCitationData();
    }
  }, [activeDocument?.id]);

  const loadCitationData = async () => {
    if (!activeDocument) return;
    setLoading(true);
    try {
      const res = await api.getAnalysisResults(activeDocument.id);
      // Filter citation and claim issues
      const citItems = res.findings.filter((f) =>
        f.finding_type.includes('citation') || f.issue_category === 'citation_consistency' ||
        f.finding_type === 'unsupported_claim' ||
        f.match_type?.includes('reference') ||
        f.match_type?.includes('quotation')
      );
      setCitationFindings(citItems);
      setAuditMeta(activeDocument.doc_metadata?.citation_audit || null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExportCsv = async () => {
    if (!activeDocument) return;
    const res = await api.exportAuditCsv(activeDocument.id);
    await downloadFile(res.download_url);
  };

  if (!activeDocument) {
    return (
      <div className="p-12 text-center text-slate-500">
        <BookOpenCheck className="w-12 h-12 mx-auto text-slate-300 mb-3" />
        <p className="text-sm font-medium">Please select a manuscript to inspect citations.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {loading && <p role="status" className="text-sm text-slate-500">Loading saved data…</p>}
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Citation & Attribution Audit</h2>
          <p className="text-sm text-slate-500 mt-1">
            Validates IEEE numeric citations [X], APA author-year conventions, bibliography links, and unsupported claims.
          </p>
        </div>
        <button
          onClick={handleExportCsv}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-xs transition"
        >
          <Download className="w-4 h-4 text-slate-500" />
          <span>Export Citation Audit (CSV)</span>
        </button>
      </div>

      {/* Audit Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">References Defined</span>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {auditMeta ? auditMeta.total_references_defined : 0}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">In Bibliography section</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">In-Text Citations</span>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {auditMeta ? auditMeta.total_citations_in_text : 0}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">Found across body paragraphs</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Missing Bib Entries</span>
          <div className="text-2xl font-bold text-rose-600 mt-1">
            {auditMeta ? auditMeta.missing_bibliography_entries?.length || 0 : 0}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">Cited [X] with no definition</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Uncited References</span>
          <div className="text-2xl font-bold text-amber-600 mt-1">
            {auditMeta ? auditMeta.uncited_bibliography_entries?.length || 0 : 0}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">Listed in refs but never cited</div>
        </div>
      </div>

      {/* Findings List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Flagged Attribution & Citation Issues</h3>
          <span className="text-xs text-slate-500">{citationFindings.length} issue(s)</span>
        </div>

        {citationFindings.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-900">No stored citation findings</h4>
            <p className="text-xs text-slate-600 mt-1">
              Run analysis to check citation patterns. Absence of findings does not verify the existence, metadata, or support of every cited source.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {citationFindings.map((finding) => (
              <div key={finding.id} className="p-6 flex flex-col md:flex-row md:items-start justify-between gap-4 hover:bg-slate-50/50 transition">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                      finding.severity === 'high' ? 'bg-rose-100 text-rose-800 border-rose-200' : 'bg-amber-100 text-amber-800 border-amber-200'
                    }`}>
                      {finding.match_type?.replace(/_/g, ' ') || finding.finding_type}
                    </span>
                    <span className="text-xs font-mono text-slate-500">Block: {finding.block_id}</span>
                  </div>

                  <p className="text-xs font-medium text-slate-800 leading-relaxed">
                    {finding.evidence.issue}
                  </p>

                  {finding.matched_text && (
                    <div className="text-xs p-3 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 italic">
                      "{finding.matched_text}"
                    </div>
                  )}

                  {finding.evidence.recommended_action && (
                    <div className="text-xs text-indigo-700 font-medium">
                      Recommendation: {finding.evidence.recommended_action}
                    </div>
                  )}
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <button
                    onClick={() => {
                      setActiveBlockId(finding.block_id);
                      setActiveTab('editor');
                    }}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 flex items-center gap-1.5 transition"
                  >
                    <span>Inspect in Editor</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
