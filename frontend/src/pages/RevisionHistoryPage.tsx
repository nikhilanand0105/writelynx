import React, { useEffect, useState } from 'react';
import { History, ShieldCheck, Clock, Download } from 'lucide-react';
import { api } from '../services/api';
import { RevisionEvent } from '../types';
import { useStudioStore } from '../store/useStudioStore';
import { WordDiff } from '../components/WordDiff';

export const RevisionHistoryPage: React.FC = () => {
  const { activeDocument } = useStudioStore();
  const [revisions, setRevisions] = useState<RevisionEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (activeDocument) {
      loadRevisions();
    }
  }, [activeDocument?.id]);

  const loadRevisions = async () => {
    if (!activeDocument) return;
    setLoading(true);
    try {
      const res = await api.listRevisions(activeDocument.id);
      setRevisions(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadLogJson = () => {
    if (!activeDocument) return;
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(revisions, null, 2));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute('href', dataStr);
    dlAnchorElem.setAttribute('download', `${activeDocument.filename}_revision_log.json`);
    dlAnchorElem.click();
  };

  if (!activeDocument) {
    return (
      <div className="p-12 text-center text-slate-500">
        <History className="w-12 h-12 mx-auto text-slate-300 mb-3" />
        <p className="text-sm font-medium">Please select a manuscript to inspect revision history.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {loading && <p role="status" className="text-sm text-slate-500">Loading saved data…</p>}
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Authorship & Writing-Process Evidence
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Verifiable, timestamped audit trail of every manual author revision and human-approved suggestion.
          </p>
        </div>

        <button
          onClick={handleDownloadLogJson}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-xs transition"
        >
          <Download className="w-4 h-4 text-slate-500" />
          <span>Export Revision Log (JSON)</span>
        </button>
      </div>

      {/* Trust Notice */}
      <div className="p-4 rounded-xl bg-slate-900 text-white text-xs leading-relaxed flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <div>
          <strong className="text-indigo-200">Academic Authorship Defense:</strong> When facing automated similarity or detector false positives, an author's primary defense is verifiable documentation of their genuine revision process. This studio logs authentic human approval events with exact timestamps and unedited source text.
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-6">
        {revisions.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
            <Clock className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-900">No Revisions Logged Yet</h4>
            <p className="text-xs text-slate-600 mt-1">
              Accepted suggestions and manual paragraph revisions will be recorded chronologically here.
            </p>
          </div>
        ) : (
          <div className="relative border-l-2 border-slate-200 pl-6 ml-4 space-y-8">
            {revisions.map((rev) => {
              const isAiApproved = rev.attribution_tag === 'user_approved_ai';
              const isManual = rev.attribution_tag === 'manual_revision';

              return (
                <div key={rev.id} className="relative group">
                  {/* Timeline bullet */}
                  <div className={`absolute -left-[31px] top-1.5 w-4 h-4 rounded-full border-2 bg-white ${
                    isAiApproved ? 'border-indigo-600' : isManual ? 'border-emerald-600' : 'border-slate-400'
                  }`} />

                  <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`px-2.5 py-0.5 rounded-full font-semibold uppercase text-[10px] border ${
                          isAiApproved
                            ? 'bg-indigo-50 text-indigo-800 border-indigo-200'
                            : isManual
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            : 'bg-slate-100 text-slate-700 border-slate-200'
                        }`}>
                          {rev.event_type.replace(/_/g, ' ')}
                        </span>
                        <span className="font-mono text-slate-500">
                          {rev.block_id || 'Document'}
                        </span>
                      </div>

                      <div className="text-slate-600 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{new Date(rev.timestamp).toLocaleString()}</span>
                      </div>
                    </div>

                    {/* Diff comparison */}
                    {rev.before_text && rev.after_text && (
                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                          Applied Textual Change
                        </div>
                        <WordDiff originalText={rev.before_text} proposedText={rev.after_text} />
                      </div>
                    )}

                    {rev.user_notes && (
                      <div className="text-xs text-slate-600 italic">
                        Author Note: "{rev.user_notes}"
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
