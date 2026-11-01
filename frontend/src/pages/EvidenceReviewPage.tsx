import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { DocumentItem, ResearchEvidence, DocumentBlock, AnalysisFinding } from '../types';
import {
  Database,
  Plus,
  CheckCircle,
  AlertCircle,
  Calendar,
  Layers,
  RefreshCw
} from 'lucide-react';

interface Props {
  document: DocumentItem | null;
}

export const EvidenceReviewPage: React.FC<Props> = ({ document: doc }) => {
  const [evidenceList, setEvidenceList] = useState<ResearchEvidence[]>([]);
  const [blocks, setBlocks] = useState<DocumentBlock[]>([]);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAdding, setIsAdding] = useState(false);

  // Form states
  const [newTitle, setNewTitle] = useState('');
  const [newType, setNewType] = useState('experiment_log');
  const [newContent, setNewContent] = useState('');
  const [selectedBlocks, setSelectedBlocks] = useState<string[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // Verification modal state
  const [verifyingFinding, setVerifyingFinding] = useState<AnalysisFinding | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string>('');
  const [userNotes, setUserNotes] = useState<string>('');

  const loadData = async () => {
    if (!doc) return;
    setLoading(true);
    try {
      const [evs, struct, analysis] = await Promise.all([
        api.listResearchEvidence(doc.id),
        api.getDocumentStructure(doc.id),
        api.getAnalysisResults(doc.id).catch(() => ({ findings: [] }))
      ]);
      setEvidenceList(evs);
      setBlocks(struct.blocks);
      setFindings(analysis.findings || []);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [doc?.id]);

  const handleCreateEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!doc || !newTitle.trim()) return;

    const formData = new FormData();
    formData.append('title', newTitle.trim());
    formData.append('evidence_type', newType);
    if (newContent) formData.append('content', newContent);
    if (selectedBlocks.length > 0) formData.append('linked_blocks', selectedBlocks.join(','));
    if (uploadFile) formData.append('file', uploadFile);

    try {
      await api.addResearchEvidence(doc.id, formData);
      setNewTitle('');
      setNewContent('');
      setSelectedBlocks([]);
      setUploadFile(null);
      setIsAdding(false);
      await loadData();
    } catch (e: any) {
      alert(e.message || 'Failed to add research evidence');
    }
  };

  const handleVerifyClaim = async () => {
    if (!verifyingFinding || !selectedEvidenceId) return;
    try {
      await api.verifyClaimWithEvidence(verifyingFinding.id, selectedEvidenceId, userNotes);
      setVerifyingFinding(null);
      setSelectedEvidenceId('');
      setUserNotes('');
      await loadData();
    } catch (e: any) {
      alert(e.message || 'Failed to verify claim');
    }
  };

  if (!doc) {
    return (
      <div className="p-8 text-center text-zinc-500">
        Please select a document from the dashboard to manage research evidence.
      </div>
    );
  }

  // Findings requiring empirical verification
  const empiricalFindings = findings.filter(
    f => f.requires_author_input || f.recommended_action === 'supply_experimental_evidence'
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <Database className="w-6 h-6 text-teal-500" />
            Research Evidence & Claim Verification
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Attach experiment logs, benchmark tables, and code artifacts to protect author contributions and verify statistical assertions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsAdding(!isAdding)}
            className="bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium px-4 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>{isAdding ? 'Cancel' : 'Attach New Evidence'}</span>
          </button>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 border border-zinc-300 dark:border-zinc-700 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-zinc-600 dark:text-zinc-300"
            title="Refresh Evidence"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Add Evidence Form */}
      {isAdding && (
        <form onSubmit={handleCreateEvidence} className="bg-zinc-50 dark:bg-zinc-900/80 border border-zinc-300 dark:border-zinc-700 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <Plus className="w-4 h-4 text-teal-600" />
            Attach Author Empirical Record
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Artifact Title *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Training logs for Table 2 (F1=0.3410) or PyTorch Evaluation Script"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                className="w-full text-xs p-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-zinc-400"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Evidence Type
              </label>
              <select
                value={newType}
                onChange={e => setNewType(e.target.value)}
                className="w-full text-xs p-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-zinc-800 dark:text-zinc-200"
              >
                <option value="experiment_log">Experiment Run Log / Terminal Output</option>
                <option value="benchmark_table">Raw Benchmark Data / CSV</option>
                <option value="source_code">Source Code Implementation / Repo</option>
                <option value="screenshot">Screenshot / Instrumentation Trace</option>
                <option value="notes">Lab Notes / Proof Sketch</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              Data Content / Notes / Raw Output (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Paste relevant terminal logs, metric numbers, or command-line parameters..."
              value={newContent}
              onChange={e => setNewContent(e.target.value)}
              className="w-full text-xs p-2 font-mono bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-zinc-400"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Upload Raw File (Optional)
              </label>
              <input
                type="file"
                onChange={e => setUploadFile(e.target.files ? e.target.files[0] : null)}
                className="text-xs text-zinc-600 dark:text-zinc-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-zinc-200 dark:file:bg-zinc-700 file:text-zinc-800 dark:file:text-zinc-200 cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Link to Manuscript Paragraphs
              </label>
              <select
                multiple
                value={selectedBlocks}
                onChange={e => {
                  const opts = Array.from(e.target.selectedOptions, option => option.value);
                  setSelectedBlocks(opts);
                }}
                className="w-full h-24 text-xs p-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-zinc-800 dark:text-zinc-200"
              >
                {blocks.map(b => (
                  <option key={b.id} value={b.id}>
                    [{b.section_id}] {b.current_text.substring(0, 60)}...
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-zinc-500">Hold Cmd/Ctrl to select multiple paragraphs</span>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              className="px-3 py-1.5 border border-zinc-300 dark:border-zinc-700 rounded-lg text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-500"
            >
              Save Artifact
            </button>
          </div>
        </form>
      )}

      {/* Verification Modal for empirical claims */}
      {verifyingFinding && (
        <div className="p-4 bg-teal-50 dark:bg-teal-950/30 border border-teal-300 dark:border-teal-800 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-teal-900 dark:text-teal-200 flex items-center gap-1.5">
              <CheckCircle className="w-4 h-4 text-teal-600" />
              Verify Unsupported Claim: {verifyingFinding.finding_type}
            </h3>
            <button
              onClick={() => setVerifyingFinding(null)}
              className="text-xs text-zinc-500 hover:text-zinc-800"
            >
              Cancel
            </button>
          </div>

          <p className="text-xs text-teal-800/80 dark:text-teal-300/80 font-serif italic">
            "{verifyingFinding.matched_text}"
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Select Supporting Author Artifact:
              </label>
              <select
                value={selectedEvidenceId}
                onChange={e => setSelectedEvidenceId(e.target.value)}
                className="w-full p-2 bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg"
              >
                <option value="">-- Choose Attached Artifact --</option>
                {evidenceList.map(ev => (
                  <option key={ev.id} value={ev.id}>
                    [{ev.evidence_type}] {ev.title}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                Author Verification Notes (Audit Log):
              </label>
              <input
                type="text"
                placeholder="e.g. Verified against Section 4 test logs run on seed 42."
                value={userNotes}
                onChange={e => setUserNotes(e.target.value)}
                className="w-full p-2 bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={handleVerifyClaim}
              disabled={!selectedEvidenceId}
              className="px-4 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-medium hover:bg-teal-500 disabled:opacity-50"
            >
              Confirm Verification & Resolve Finding
            </button>
          </div>
        </div>
      )}

      {/* Grid of Evidence Artifacts */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 flex items-center justify-between">
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
            Attached Author Records ({evidenceList.length})
          </h2>
          <span className="text-xs text-zinc-400">
            Immutable research provenance
          </span>
        </div>

        {evidenceList.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <Database className="w-10 h-10 text-zinc-300 dark:text-zinc-700 mx-auto" />
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">No Research Evidence Attached</h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
              Attach experimental logs, raw metric files, or code to prove novel contributions and defend against generic detector false positives.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {evidenceList.map(ev => (
              <div key={ev.id} className="p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-teal-100 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 border border-teal-300 dark:border-teal-800">
                      {ev.evidence_type.replace('_', ' ')}
                    </span>
                    <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                      {ev.title}
                    </h3>
                  </div>

                  <span className="text-[11px] text-zinc-400 flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {new Date(ev.created_at).toLocaleDateString()}
                  </span>
                </div>

                {ev.content && (
                  <p className="text-xs font-mono bg-zinc-100 dark:bg-zinc-800/80 p-2.5 rounded-lg text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                    {ev.content}
                  </p>
                )}

                {ev.linked_blocks && ev.linked_blocks.length > 0 && (
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <Layers className="w-3.5 h-3.5 text-zinc-400 flex-shrink-0" />
                    <span>Supports {ev.linked_blocks.length} manuscript blocks:</span>
                    <span className="font-mono text-[11px] text-zinc-700 dark:text-zinc-300">
                      {ev.linked_blocks.join(', ')}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Claims Pending Evidence Verification */}
      {empiricalFindings.length > 0 && (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 bg-amber-50/40 dark:bg-amber-950/20 flex items-center justify-between">
            <h2 className="font-semibold text-amber-900 dark:text-amber-200 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-500" />
              Empirical Claims Awaiting Verification ({empiricalFindings.length})
            </h2>
            <span className="text-xs text-amber-700/80 dark:text-amber-300/80">
              Required evidence: experiment logs, statistical tests
            </span>
          </div>

          <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {empiricalFindings.map(f => (
              <div key={f.id} className="p-4 flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                      {f.finding_type.replace('_', ' ').toUpperCase()}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-mono">
                      {f.recommended_action}
                    </span>
                    {f.review_status === 'verified' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-medium">
                        Verified
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-600 dark:text-zinc-400 font-serif">
                    "{f.matched_text}"
                  </p>
                </div>

                {f.review_status !== 'verified' && (
                  <button
                    onClick={() => {
                      setVerifyingFinding(f);
                      setSelectedEvidenceId(evidenceList.length > 0 ? evidenceList[0].id : '');
                    }}
                    className="px-3 py-1.5 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-lg text-xs font-medium hover:bg-zinc-800 flex-shrink-0"
                  >
                    Link Evidence
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
