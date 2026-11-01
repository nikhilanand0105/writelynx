import React, { useEffect, useState } from 'react';
import { Layers, CheckCircle, ExternalLink, Info, Filter } from 'lucide-react';
import { api } from '../services/api';
import { AnalysisFinding, DiagnosticMetrics, ReferenceSource } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export const OverlapReviewPage: React.FC = () => {
  const { activeDocument, setActiveTab, setActiveBlockId } = useStudioStore();
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [metrics, setMetrics] = useState<DiagnosticMetrics | null>(null);
  const [sources, setSources] = useState<ReferenceSource[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (activeDocument) {
      loadOverlapData();
    }
  }, [activeDocument?.id]);

  const loadOverlapData = async () => {
    if (!activeDocument) return;
    setLoading(true);
    try {
      const [analysisRes, sourcesRes] = await Promise.all([
        api.getAnalysisResults(activeDocument.id),
        api.listSources(activeDocument.id),
      ]);
      setFindings(analysisRes.findings.filter((f) => 'matched_text' in f && f.similarity_score > 0));
      setMetrics(analysisRes.metrics);
      setSources(sourcesRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredFindings = categoryFilter === 'all'
    ? findings
    : findings.filter((f) => f.finding_type === categoryFilter);

  if (!activeDocument) {
    return (
      <div className="p-12 text-center text-slate-500">
        <Layers className="w-12 h-12 mx-auto text-slate-300 mb-3" />
        <p className="text-sm font-medium">Please select a manuscript to review textual overlap.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header & Transparency Notice */}
      <div className="space-y-3 pb-6 border-b border-slate-200">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
              Evidence-Based Overlap Review
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              Direct verification of textual similarity against uploaded benchmark references.
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Diagnostic Overlap Score
            </div>
            <div className="text-3xl font-extrabold text-slate-900 mt-0.5">
              {metrics ? `${metrics.local_textual_overlap_percentage}%` : '0.0%'}
            </div>
            <div className="text-[11px] font-semibold text-indigo-600">
              Local textual overlap against analyzed sources
            </div>
          </div>
        </div>

        {/* Turnitin Non-Replication Disclaimer */}
        <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 text-amber-900 text-xs leading-relaxed flex items-start gap-3">
          <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold text-amber-950">Diagnostic Methodology & Boundary:</strong> This analysis is calculated locally using normalized n-grams, RapidFuzz lexical matching, and TF-IDF candidate retrieval strictly against your {sources.length} indexed source document(s). Turnitin compares against private institutional repositories that this local offline application does not access. These metrics should never be represented as Turnitin percentages.
          </div>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Analyzed Sources</span>
          <div className="text-xl font-bold text-slate-900 mt-1">{sources.length} document(s)</div>
          <div className="text-[11px] text-slate-600 mt-0.5">Indexed locally in SQLite</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Overlapping Passages</span>
          <div className="text-xl font-bold text-slate-900 mt-1">{findings.length}</div>
          <div className="text-[11px] text-slate-600 mt-0.5">Meeting similarity thresholds</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Unattributed Overlap</span>
          <div className="text-xl font-bold text-rose-600 mt-1">
            {metrics ? metrics.unattributed_overlap_count : 0}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">Requiring quotation/citation</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Exact Match Words</span>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {metrics ? metrics.exact_match_words : 0}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">Normalized n-gram overlap</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <Filter className="w-4 h-4 text-slate-400 shrink-0 ml-1" />
        {[
          { id: 'all', label: 'All Findings' },
          { id: 'unattributed_overlap', label: 'Unattributed Overlap' },
          { id: 'direct_quote', label: 'Direct Quotes' },
          { id: 'cited_quote', label: 'Cited Quotes' },
          { id: 'cited_paraphrase', label: 'Cited Paraphrases' },
          { id: 'common_terminology', label: 'Common Terminology' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setCategoryFilter(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition whitespace-nowrap ${
              categoryFilter === tab.id
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Findings List with Side-by-Side Evidence */}
      {filteredFindings.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
          <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-slate-900">No overlapping passages found</h4>
          <p className="text-xs text-slate-600 mt-1">
            The manuscript does not exhibit textual overlap with the currently indexed reference sources under the selected filter.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredFindings.map((finding) => (
            <div
              key={finding.id}
              className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden"
            >
              <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                    finding.finding_type === 'unattributed_overlap'
                      ? 'bg-rose-100 text-rose-800 border-rose-200'
                      : finding.finding_type === 'common_terminology'
                      ? 'bg-slate-200 text-slate-700 border-slate-300'
                      : 'bg-indigo-100 text-indigo-800 border-indigo-200'
                  }`}>
                    {finding.finding_type.replace('_', ' ')}
                  </span>
                  <span className="text-xs font-mono text-slate-500">
                    Block: {finding.block_id}
                  </span>
                </div>

                <div className="flex items-center gap-4">
                  <span className="text-xs font-semibold text-slate-700">
                    Overlap: {Math.round(finding.similarity_score * 100)}% ({finding.match_type})
                  </span>
                  <button
                    onClick={() => {
                      setActiveBlockId(finding.block_id);
                      setActiveTab('editor');
                    }}
                    className="text-xs font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                  >
                    <span>View in Editor</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Side-by-Side Comparison */}
              <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
                {/* Your Manuscript */}
                <div className="space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase">
                    Your Manuscript Passage
                  </div>
                  <div className="p-3.5 rounded-lg bg-amber-50/50 border border-amber-200 text-slate-800 leading-relaxed">
                    {finding.matched_text}
                  </div>
                </div>

                {/* Benchmark Source */}
                <div className="space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase flex items-center justify-between">
                    <span>Matched Reference Source</span>
                    <span className="text-slate-700 font-normal truncate max-w-[200px]">
                      {finding.evidence.source_title || 'Indexed Document'}
                    </span>
                  </div>
                  <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-800 italic leading-relaxed">
                    {finding.source_matched_text || finding.evidence.explanation}
                  </div>
                </div>
              </div>

              {/* Diagnostic Recommendation */}
              <div className="px-5 py-3 bg-slate-50/80 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-600">
                  <strong className="text-slate-800">Recommendation:</strong>{' '}
                  {finding.evidence.recommended_action || (
                    finding.finding_type === 'unattributed_overlap'
                      ? 'Encapsulate in quotation marks or rewrite in author-verified prose with explicit attribution.'
                      : 'Verify attribution integrity.'
                  )}
                </span>
                <span className="text-[10px] text-slate-600 uppercase font-semibold">
                  Status: {finding.review_status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
