import React, { useEffect, useState } from 'react';
import { Sparkles, Check, X, CheckCircle, ExternalLink, } from 'lucide-react';
import { api } from '../services/api';
import { EditSuggestion } from '../types';
import { useStudioStore } from '../store/useStudioStore';
import { WordDiff } from '../components/WordDiff';

export const WritingQualityPage: React.FC = () => {
  const { activeDocument, setActiveTab, setActiveBlockId, triggerRefresh, refreshTrigger } = useStudioStore();
  const [suggestions, setSuggestions] = useState<EditSuggestion[]>([]);
  const [busy, setBusy] = useState(false);
  const [selectedMode, setSelectedMode] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (activeDocument) {
      loadSuggestions();
    }
  }, [activeDocument?.id, refreshTrigger]);

  const loadSuggestions = async () => {
    if (!activeDocument) return;
    setLoading(true);
    try {
      const res = await api.listSuggestions(activeDocument.id);
      setSuggestions(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (id: string) => {
    setBusy(true);
    try { await api.acceptSuggestion(id); triggerRefresh(); }
    catch { const suggestion = suggestions.find(item => item.id === id); if (suggestion) { setActiveBlockId(suggestion.block_id); setActiveTab('editor'); } }
    finally { setBusy(false); }
  };

  const handleReject = async (id: string) => {
    setBusy(true);
    try { await api.rejectSuggestion(id); triggerRefresh(); } finally { setBusy(false); }
  };

  const filtered = selectedMode === 'all'
    ? suggestions
    : suggestions.filter((s) => s.issue_type === selectedMode);

  if (!activeDocument) {
    return (
      <div className="p-12 text-center text-slate-500">
        <Sparkles className="w-12 h-12 mx-auto text-slate-300 mb-3" />
        <p className="text-sm font-medium">Please select a manuscript to inspect writing quality.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {loading && <p role="status" className="text-sm text-slate-500">Loading saved data…</p>}
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Writing Quality & Clarity Review</h2>
          <p className="text-sm text-slate-500 mt-1">
            Targeted academic editing with protected facts. Review each change in context before accepting.
          </p>
        </div>
      </div>

      {/* Mode Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { id: 'light_copyediting', label: 'Minimal proofreading', count: suggestions.filter(s => ['minimal', 'light_copyediting'].includes(s.issue_type)).length },
          { id: 'academic_revision', label: 'Natural Academic Voice', count: suggestions.filter(s => ['clarity', 'academic_revision'].includes(s.issue_type)).length },
          { id: 'research_grounded', label: 'Research-grounded', count: suggestions.filter(s => ['substantive', 'research_grounded'].includes(s.issue_type)).length },
        ].map((m) => (
          <div
            key={m.id}
            onClick={() => setSelectedMode(selectedMode === m.id ? 'all' : m.id)}
            className={`p-4 rounded-xl border cursor-pointer transition ${
              selectedMode === m.id ? 'border-indigo-600 bg-indigo-50/50' : 'bg-white border-slate-200 hover:border-slate-300'
            }`}
          >
            <span className="text-xs font-medium text-slate-500">{m.label}</span>
            <div className="text-2xl font-bold text-slate-900 mt-1">{m.count}</div>
            <div className="text-[11px] text-slate-600 mt-0.5">Suggestions generated</div>
          </div>
        ))}
      </div>

      {/* Suggestions List */}
      <div className="space-y-4">
        {filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
            <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-900">No suggestions pending</h4>
            <p className="text-xs text-slate-600 mt-1">
              No stored suggestions match this filter. Automated analysis cannot establish that all prose meets academic standards.
            </p>
          </div>
        ) : (
          filtered.map((sug) => {
            const isAccepted = sug.review_status === 'accepted';
            const isRejected = sug.review_status === 'rejected';

            return (
              <div
                key={sug.id}
                className={`bg-white rounded-xl border p-5 space-y-4 shadow-xs transition ${
                  isAccepted
                    ? 'border-emerald-300 bg-emerald-50/10'
                    : isRejected
                    ? 'border-slate-200 opacity-60'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200 uppercase tracking-wide">
                      {sug.issue_type.replace('_', ' ')}
                    </span>
                    <span className="text-xs font-mono text-slate-500">Block: {sug.block_id}</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                      isAccepted ? 'bg-emerald-100 text-emerald-800' : isRejected ? 'bg-slate-200 text-slate-700' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {sug.review_status}
                    </span>
                    <button
                      onClick={() => {
                        setActiveBlockId(sug.block_id);
                        setActiveTab('editor');
                      }}
                      className="text-xs font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                    >
                      <span>Open Editor</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Word Diff */}
                <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                    Proposed Revision Diff
                  </div>
                  <WordDiff originalText={sug.original_text} proposedText={sug.proposed_text} />
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 text-xs text-slate-600">
                  <div>
                    <span className="font-semibold text-slate-700">Editorial Rationale:</span> {sug.reason}
                  </div>

                  {!isAccepted && !isRejected && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        disabled={busy}
                        onClick={() => handleAccept(sug.id)}
                        className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold flex items-center gap-1.5 shadow-xs transition"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Accept Edit</span>
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => handleReject(sug.id)}
                        className="px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg font-medium flex items-center gap-1.5 transition"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Reject</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
