import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FileText,
  Download,
  ArrowLeft,
  ChevronDown,
  CheckCircle2,
  Clock,
  Sparkles,
  Layers,
  History,
  ShieldCheck,
  Edit3,
  Check,
  X,
  Search,
  RotateCcw,
  Undo2,
  Redo2,
  AlertCircle,
  FileDown,
  BookOpenCheck,
  GitCompare,
  Database,
  ExternalLink
} from 'lucide-react';
import { api, downloadFile, downloadJson, errorMessage, ApiError } from '../services/api';
import {
  DocumentItem,
  DocumentBlock,
  EditSuggestion,
  AnalysisFinding,
  DetectorHighlight,
  GroundedRevision
} from '../types';
import { useStudioStore, WorkspaceTab } from '../store/useStudioStore';
import { WordDiff } from '../components/WordDiff';
import { OriginalPreview } from '../components/OriginalPreview';

// Sub-components for progressive disclosure
import { CitationReviewPage } from './CitationReviewPage';
import { EvidenceReviewPage } from './EvidenceReviewPage';
import { OverlapReviewPage } from './OverlapReviewPage';
import { DetectorHighlightsPage } from './DetectorHighlightsPage';
import { ReportComparisonPage } from './ReportComparisonPage';
import { FlaggedComparisonPage } from './FlaggedComparisonPage';
import { RevisionHistoryPage } from './RevisionHistoryPage';

type Draft = { block: DocumentBlock; text: string; notes: string; suggestionId?: string };
type FactApproval = { message: string; violations: unknown[]; requires_fact_approval: boolean };

function HighlightedText({ text, highlights }: { text: string; highlights: DetectorHighlight[] }) {
  const ranges = highlights
    .map((highlight) => ({
      start: text.indexOf(highlight.highlight_text),
      length: highlight.highlight_text.length,
    }))
    .filter((range) => range.start >= 0 && range.length > 0)
    .sort((a, b) => a.start - b.start);

  let cursor = 0;
  const output = [];
  for (const range of ranges) {
    if (range.start < cursor) continue;
    output.push(<span key={`text-${range.start}`}>{text.slice(cursor, range.start)}</span>);
    output.push(
      <mark key={`mark-${range.start}`} className="bg-amber-200 text-inherit">
        {text.slice(range.start, range.start + range.length)}
      </mark>
    );
    cursor = range.start + range.length;
  }
  output.push(<span key="end">{text.slice(cursor)}</span>);
  return <>{output}</>;
}

export const DocumentWorkspace: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    activeDocument,
    setActiveDocument,
    workspaceTab,
    setWorkspaceTab,
    activeChecksSubTab,
    setActiveChecksSubTab,
    activeBlockId,
    setActiveBlockId,
    triggerRefresh,
    refreshTrigger,
  } = useStudioStore();

  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [blocks, setBlocks] = useState<DocumentBlock[]>([]);
  const [suggestions, setSuggestions] = useState<EditSuggestion[]>([]);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [highlights, setHighlights] = useState<DetectorHighlight[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [downloadDropdown, setDownloadDropdown] = useState(false);

  // Review & Editor State
  const [section, setSection] = useState('All');
  const [query, setQuery] = useState('');
  const [view, setView] = useState<'current' | 'original' | 'word'>('current');
  const [filter, setFilter] = useState('all');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [approval, setApproval] = useState<FactApproval | null>(null);
  const [approveFacts, setApproveFacts] = useState(false);
  const [grounded, setGrounded] = useState<GroundedRevision | null>(null);
  const [mobileTab, setMobileTab] = useState<'text' | 'suggestions'>('text');

  // Load document and data
  useEffect(() => {
    const docId = id || activeDocument?.id;
    if (!docId) return;

    let cancelled = false;
    setLoading(true);
    setError('');

    Promise.all([
      api.getDocument(docId),
      api.getDocumentStructure(docId).catch(() => ({ blocks: [] })),
      api.listSuggestions(docId).catch(() => []),
      api.getAnalysisResults(docId).catch(() => ({ findings: [] })),
      api.listDetectorHighlights(docId).catch(() => []),
    ])
      .then(([doc, structure, nextSuggestions, analysis, nextHighlights]) => {
        if (cancelled) return;
        setDocument(doc);
        setActiveDocument(doc);
        setBlocks(structure.blocks || []);
        setSuggestions(nextSuggestions || []);
        setFindings(analysis.findings || []);
        setHighlights(nextHighlights || []);

        if (
          structure.blocks &&
          structure.blocks.length > 0 &&
          !structure.blocks.some((b: any) => b.id === activeBlockId)
        ) {
          setActiveBlockId(structure.blocks[0].id);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, refreshTrigger]);

  const current = blocks.find((block) => block.id === activeBlockId);
  const sections = useMemo(() => ['All', ...new Set(blocks.map((block) => block.section_id))], [blocks]);

  const visibleBlocks = blocks.filter(
    (block) =>
      (section === 'All' || block.section_id === section) &&
      (!query || block.current_text.toLowerCase().includes(query.toLowerCase())) &&
      (filter === 'all' ||
        (filter === 'changed'
          ? block.original_text !== block.current_text
          : filter === 'highlights'
          ? highlights.some((h) => h.block_id === block.id)
          : findings.some((f) => f.block_id === block.id)))
  );

  const currentFindings = findings.filter((finding) => finding.block_id === activeBlockId);
  const currentSuggestions = suggestions.filter((suggestion) => suggestion.block_id === activeBlockId);
  const currentHighlights = highlights.filter((highlight) => highlight.block_id === activeBlockId);

  const act = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label);
    setError('');
    try {
      await action();
      triggerRefresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy('');
    }
  };

  const openDraft = (block: DocumentBlock, text: string, suggestionId?: string) => {
    setDraft({ block, text, notes: '', suggestionId });
    setApproval(null);
    setApproveFacts(false);
  };

  const saveDraft = async () => {
    if (!draft) return;
    setBusy('save');
    setError('');
    try {
      if (draft.suggestionId) {
        await api.reviseSuggestion(draft.suggestionId, draft.text, draft.notes, approveFacts);
      } else {
        await api.reviseBlockManually(draft.block.id, draft.text, draft.notes, approveFacts);
      }
      setDraft(null);
      setGrounded(null);
      setApproval(null);
      triggerRefresh();
    } catch (err) {
      if (err instanceof ApiError && (err.detail as FactApproval)?.requires_fact_approval) {
        setApproval(err.detail as FactApproval);
      }
      setError(errorMessage(err));
    } finally {
      setBusy('');
    }
  };

  const accept = async (suggestion: EditSuggestion) => {
    setBusy(suggestion.id);
    setError('');
    try {
      await api.acceptSuggestion(suggestion.id);
      triggerRefresh();
    } catch (err) {
      if (err instanceof ApiError && (err.detail as FactApproval)?.requires_fact_approval && current) {
        openDraft(current, suggestion.proposed_text, suggestion.id);
        setApproval(err.detail as FactApproval);
      }
      setError(errorMessage(err));
    } finally {
      setBusy('');
    }
  };

  // Direct Downloads
  const handleDownload = async (type: 'docx' | 'pdf' | 'validation' | 'audit_csv') => {
    if (!document) return;
    setBusy(type);
    setDownloadDropdown(false);
    setError('');
    try {
      if (type === 'docx') {
        const res = await api.exportDocx(document.id);
        await downloadFile(res.download_url);
      } else if (type === 'pdf') {
        const res = await api.exportPdf(document.id);
        await downloadFile(res.download_url);
      } else if (type === 'validation') {
        const report = await api.validateDocument(document.id);
        downloadJson(report, `${document.filename}_preservation_report.json`);
      } else if (type === 'audit_csv') {
        const res = await api.exportAuditCsv(document.id);
        await downloadFile(res.download_url);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy('');
    }
  };

  if (!document && !loading) {
    return (
      <div className="p-12 text-center space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">Manuscript not found</h2>
        <p className="text-xs text-slate-500">The requested document could not be loaded or was removed.</p>
        <button
          onClick={() => navigate('/documents')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold"
        >
          Return to My Documents
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-slate-50 overflow-hidden">
      {/* Contextual Workspace Header */}
      <header className="bg-white border-b border-slate-200 px-4 md:px-6 py-2.5 flex items-center justify-between shrink-0 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/documents')}
            className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-slate-900 transition shrink-0"
            title="Back to My Documents"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-sm text-slate-900 truncate max-w-sm md:max-w-md">
                {document?.filename || 'Loading manuscript...'}
              </h1>
              {document && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium shrink-0">
                  {document.word_count.toLocaleString()} words
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 3 Contextual Tabs */}
        <div className="flex items-center bg-slate-100 p-1 rounded-xl text-xs font-medium">
          <button
            onClick={() => setWorkspaceTab('review')}
            className={`px-3.5 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              workspaceTab === 'review'
                ? 'bg-white text-indigo-950 font-semibold shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <span>Review</span>
            {suggestions.filter((s) => s.review_status === 'pending').length > 0 && (
              <span className="ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-100 text-indigo-700 font-bold">
                {suggestions.filter((s) => s.review_status === 'pending').length}
              </span>
            )}
          </button>

          <button
            onClick={() => setWorkspaceTab('checks')}
            className={`px-3.5 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              workspaceTab === 'checks'
                ? 'bg-white text-indigo-950 font-semibold shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-indigo-500" />
            <span>Sources & Checks</span>
          </button>

          <button
            onClick={() => setWorkspaceTab('history')}
            className={`px-3.5 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              workspaceTab === 'history'
                ? 'bg-white text-indigo-950 font-semibold shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <History className="w-3.5 h-3.5 text-indigo-500" />
            <span>History</span>
          </button>
        </div>

        {/* Prominent Direct Download Button & Dropdown */}
        <div className="relative shrink-0">
          <div className="flex items-center rounded-lg shadow-xs overflow-hidden">
            <button
              disabled={!!busy}
              onClick={() => handleDownload('docx')}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{busy === 'docx' ? 'Preparing…' : 'Download Word'}</span>
            </button>
            <button
              onClick={() => setDownloadDropdown(!downloadDropdown)}
              className="p-1.5 bg-indigo-700 hover:bg-indigo-800 text-white transition border-l border-indigo-500"
              title="More export formats"
            >
              <ChevronDown className="w-3.5 h-3.5" />
            </button>
          </div>

          {downloadDropdown && (
            <div className="absolute right-0 mt-1 w-56 bg-white border border-slate-200 rounded-xl shadow-lg z-50 py-1 text-xs">
              <button
                onClick={() => handleDownload('docx')}
                className="w-full px-4 py-2 text-left hover:bg-slate-50 flex items-center justify-between font-medium text-slate-800"
              >
                <span>Download Word (.docx)</span>
                <span className="text-[10px] text-slate-400">Primary</span>
              </button>
              <button
                onClick={() => handleDownload('pdf')}
                className="w-full px-4 py-2 text-left hover:bg-slate-50 flex items-center justify-between text-slate-700"
              >
                <span>Download PDF (.pdf)</span>
              </button>
              <div className="border-t border-slate-100 my-1" />
              <div className="px-4 py-1 text-[10px] uppercase font-bold text-slate-400">
                Audit & Preservation
              </div>
              <button
                onClick={() => handleDownload('validation')}
                className="w-full px-4 py-2 text-left hover:bg-slate-50 text-slate-600"
              >
                Preservation Report (.json)
              </button>
              <button
                onClick={() => handleDownload('audit_csv')}
                className="w-full px-4 py-2 text-left hover:bg-slate-50 text-slate-600"
              >
                Diagnostic Findings (.csv)
              </button>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div role="alert" className="p-3 bg-rose-50 border-b border-rose-200 text-xs text-rose-800 flex items-center justify-between px-6">
          <span>{error}</span>
          <button onClick={() => setError('')} className="underline">Dismiss</button>
        </div>
      )}

      {/* TAB 1: REVIEW (DEFAULT VIEW) */}
      {workspaceTab === 'review' && (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Top Review Toolbar */}
          <div className="p-2.5 bg-white border-b border-slate-200 flex items-center justify-between flex-wrap gap-2 text-xs px-6">
            <div className="flex items-center gap-2">
              <button
                disabled={!!busy}
                onClick={() => act('undo', () => api.undo(document!.id))}
                className="border border-slate-200 rounded-lg px-2.5 py-1.5 flex items-center gap-1 hover:bg-slate-50 text-slate-700"
              >
                <Undo2 size={13} />
                <span>Undo</span>
              </button>
              <button
                disabled={!!busy}
                onClick={() => act('redo', () => api.redo(document!.id))}
                className="border border-slate-200 rounded-lg px-2.5 py-1.5 flex items-center gap-1 hover:bg-slate-50 text-slate-700"
              >
                <Redo2 size={13} />
                <span>Redo</span>
              </button>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-slate-500 text-[11px]">
                {suggestions.filter((s) => s.review_status === 'accepted').length} accepted ·{' '}
                {suggestions.filter((s) => s.review_status === 'pending').length} pending review
              </span>
              <button
                disabled={!!busy || document?.processing_status === 'analyzing'}
                onClick={() => act('analysis', () => api.startAnalysis(document!.id, 'academic_revision'))}
                className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-medium transition"
              >
                Re-check Writing
              </button>
            </div>
          </div>

          {/* 2-Column Responsive Editor */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[200px_minmax(350px,1fr)_380px] min-h-0 overflow-hidden">
            {/* Outline Column (Desktop) */}
            <nav
              aria-label="Document outline"
              className="hidden lg:block bg-white border-r border-slate-200 p-3 overflow-y-auto space-y-3"
            >
              <div className="font-semibold text-[11px] uppercase tracking-wider text-slate-400">
                Document Outline
              </div>
              <div className="relative">
                <Search size={13} className="text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search text..."
                  className="w-full pl-7 pr-2 py-1.5 text-xs border border-slate-200 rounded-lg outline-none focus:border-indigo-500"
                />
              </div>

              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full border border-slate-200 rounded-lg p-1.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">All passages ({blocks.length})</option>
                <option value="changed">Edited passages</option>
                <option value="highlights">Imported highlights</option>
                <option value="findings">Findings</option>
              </select>

              <div className="space-y-1">
                {sections.map((item) => (
                  <button
                    key={item}
                    onClick={() => setSection(item)}
                    className={`w-full text-left text-xs px-2.5 py-1.5 rounded-lg truncate transition ${
                      section === item ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </nav>

            {/* Manuscript Passages Column */}
            <section
              aria-label="Manuscript passages"
              className="bg-slate-100 overflow-y-auto p-4 md:p-6 space-y-4"
            >
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-500 font-medium">
                  {visibleBlocks.length} passages shown
                </span>
                <select
                  value={view}
                  onChange={(e) => setView(e.target.value as any)}
                  className="border border-slate-200 bg-white rounded-lg px-2.5 py-1 text-xs text-slate-700 outline-none"
                >
                  <option value="current">Current text</option>
                  <option value="original">Original immutable text</option>
                  <option value="word">Original document preview</option>
                </select>
              </div>

              {view === 'word' ? (
                <OriginalPreview documentId={document!.id} />
              ) : (
                <div className="bg-white rounded-xl border border-slate-200 p-6 md:p-8 space-y-4 shadow-xs">
                  {loading && <p className="text-xs text-slate-500">Loading passages…</p>}
                  {!loading && visibleBlocks.length === 0 && (
                    <p className="text-xs text-slate-500">No passages match these filters.</p>
                  )}
                  {visibleBlocks.map((block) => {
                    const isSelected = block.id === activeBlockId;
                    const blockHighlights = highlights.filter((h) => h.block_id === block.id);
                    const isEdited = block.original_text !== block.current_text;

                    return (
                      <div
                        key={block.id}
                        data-testid={`block-${block.block_index}`}
                        onClick={() => setActiveBlockId(block.id)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition ${
                          isSelected
                            ? 'border-indigo-500 ring-2 ring-indigo-100 bg-indigo-50/10'
                            : 'border-transparent hover:border-slate-200 hover:bg-slate-50/60'
                        }`}
                      >
                        <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1.5">
                          <span className="capitalize">{block.block_type.replace(/_/g, ' ')} · {block.block_index + 1}</span>
                          <span className="flex items-center gap-2">
                            {isEdited && <span className="text-indigo-600 font-semibold">• Edited</span>}
                            {blockHighlights.length > 0 && <span className="text-amber-600 font-semibold">• Highlighted</span>}
                            {block.is_protected && <span className="text-slate-500 font-mono">Protected</span>}
                          </span>
                        </div>
                        <div
                          className={`whitespace-pre-wrap leading-relaxed ${
                            ['heading', 'title'].includes(block.block_type)
                              ? 'font-bold text-base text-slate-900'
                              : 'text-sm text-slate-800'
                          }`}
                        >
                          <HighlightedText
                            text={view === 'original' ? block.original_text : block.current_text}
                            highlights={blockHighlights}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* Suggestions & Inspector Column */}
            <section
              aria-label="Passage inspector"
              className="bg-white border-l border-slate-200 overflow-y-auto p-5 space-y-5"
            >
              {!current ? (
                <div className="text-center py-12 text-xs text-slate-400">
                  Select a passage on the left to review suggestions.
                </div>
              ) : (
                <div className="space-y-5">
                  <div className="flex items-center justify-between gap-2 pb-3 border-b border-slate-100">
                    <div>
                      <h2 className="font-bold text-sm text-slate-900">Passage Review</h2>
                      <span className="text-[10px] text-slate-400">Paragraph #{current.block_index + 1}</span>
                    </div>
                    <button
                      disabled={!!busy || current.is_protected}
                      onClick={() => openDraft(current, current.current_text)}
                      className="flex items-center gap-1 border border-slate-200 hover:bg-slate-50 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-700 transition"
                    >
                      <Edit3 size={12} />
                      <span>Edit</span>
                    </button>
                  </div>

                  {/* Fact & Citation Protection Notice */}
                  <div className="bg-indigo-50 border border-indigo-100 p-3.5 rounded-xl space-y-1.5 text-xs text-indigo-950">
                    <div className="flex items-center gap-1.5 font-semibold text-indigo-900">
                      <ShieldCheck size={14} className="text-indigo-600" />
                      <span>Protected Technical Facts</span>
                    </div>
                    <p className="text-[11px] text-indigo-800/80 leading-relaxed">
                      Numbers, percentages, units, and citation indices in this passage are strictly monitored.
                    </p>
                  </div>

                  {/* Revision Suggestions */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Writing Suggestions ({currentSuggestions.length})
                    </h3>

                    {currentSuggestions.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">No automated suggestions for this passage.</p>
                    ) : (
                      currentSuggestions.map((suggestion) => (
                        <div
                          key={suggestion.id}
                          className="border border-slate-200 rounded-xl p-3.5 space-y-3 text-xs bg-slate-50/50"
                        >
                          <div className="flex justify-between items-center">
                            <span className="font-semibold text-slate-800 capitalize">
                              {suggestion.issue_type.replace(/_/g, ' ')}
                            </span>
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                                suggestion.review_status === 'accepted'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : suggestion.review_status === 'rejected'
                                  ? 'bg-rose-100 text-rose-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {suggestion.review_status}
                            </span>
                          </div>

                          <WordDiff
                            originalText={suggestion.original_text}
                            proposedText={suggestion.proposed_text}
                          />

                          <p className="text-slate-600 text-[11px] leading-relaxed">{suggestion.reason}</p>

                          {suggestion.review_status === 'pending' && (
                            <div className="flex items-center gap-2 pt-2 border-t border-slate-200">
                              <button
                                disabled={!!busy}
                                onClick={() => accept(suggestion)}
                                className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                              >
                                <Check size={12} />
                                <span>Accept</span>
                              </button>
                              <button
                                disabled={!!busy}
                                onClick={() =>
                                  act(suggestion.id, () => api.rejectSuggestion(suggestion.id))
                                }
                                className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 hover:bg-slate-100 text-slate-600 rounded-lg text-xs font-medium transition"
                              >
                                <X size={12} />
                                <span>Ignore</span>
                              </button>
                              <button
                                disabled={!!busy}
                                onClick={() => openDraft(current, suggestion.proposed_text, suggestion.id)}
                                className="text-xs text-indigo-600 hover:underline font-medium ml-auto"
                              >
                                Edit Suggestion
                              </button>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>

                  {/* Editorial Findings */}
                  {currentFindings.length > 0 && (
                    <div className="space-y-3 pt-3 border-t border-slate-100">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Diagnostic Findings ({currentFindings.length})
                      </h3>
                      {currentFindings.map((finding) => (
                        <div
                          key={finding.id}
                          className="border border-slate-200 rounded-xl p-3 text-xs space-y-2 bg-white"
                        >
                          <div className="flex justify-between items-center">
                            <strong className="text-slate-800 capitalize">
                              {(finding.issue_category || finding.finding_type).replace(/_/g, ' ')}
                            </strong>
                            <span className="text-[10px] text-slate-500 uppercase">{finding.severity}</span>
                          </div>
                          <p className="text-slate-600 text-[11px]">
                            {finding.evidence?.reason ||
                              finding.evidence?.explanation ||
                              finding.recommended_action ||
                              'Inspect passage context.'}
                          </p>
                          <div className="flex gap-2 pt-1">
                            <button
                              disabled={!!busy}
                              onClick={() =>
                                act(finding.id, () =>
                                  api.reviewFinding(finding.id, 'user_reviewed', 'Reviewed by student')
                                )
                              }
                              className="text-xs text-indigo-600 hover:underline"
                            >
                              Mark Reviewed
                            </button>
                            <button
                              disabled={!!busy}
                              onClick={() => act(finding.id, () => api.reviewFinding(finding.id, 'rejected'))}
                              className="text-xs text-slate-500 hover:underline"
                            >
                              Dismiss
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Applied Changes & Restore */}
                  {current.current_text !== current.original_text && (
                    <div className="space-y-2.5 pt-4 border-t border-slate-100 text-xs">
                      <div className="font-semibold text-slate-800">Passage Changes</div>
                      <WordDiff originalText={current.original_text} proposedText={current.current_text} />
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          act('restore', () => api.restoreBlock(document!.id, current.id))
                        }
                        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 underline"
                      >
                        <RotateCcw size={12} />
                        <span>Restore original passage</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </section>
          </div>
        </div>
      )}

      {/* TAB 2: SOURCES & CHECKS */}
      {workspaceTab === 'checks' && (
        <div className="flex-1 flex flex-col min-h-0 bg-white overflow-hidden">
          {/* Sub-navigation Pills */}
          <div className="bg-slate-50 border-b border-slate-200 px-6 py-2.5 flex items-center gap-2 overflow-x-auto text-xs shrink-0">
            {[
              { id: 'citations', label: 'Citations & Attribution' },
              { id: 'sources', label: 'Supporting Sources & Claims' },
              { id: 'overlap', label: 'Overlap Review' },
              { id: 'highlights', label: 'Detector Highlights' },
              { id: 'comparison', label: 'Report Comparison' },
            ].map((sub) => (
              <button
                key={sub.id}
                onClick={() => setActiveChecksSubTab(sub.id)}
                className={`px-3 py-1.5 rounded-lg font-medium shrink-0 transition ${
                  activeChecksSubTab === sub.id
                    ? 'bg-slate-900 text-white font-semibold'
                    : 'text-slate-600 hover:bg-slate-200/60'
                }`}
              >
                {sub.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">
            {activeChecksSubTab === 'citations' && <CitationReviewPage />}
            {activeChecksSubTab === 'sources' && <EvidenceReviewPage document={document} />}
            {activeChecksSubTab === 'overlap' && <OverlapReviewPage />}
            {activeChecksSubTab === 'highlights' && (
              <DetectorHighlightsPage document={document} onRefreshDocument={triggerRefresh} />
            )}
            {activeChecksSubTab === 'comparison' && (
              <div className="p-6 space-y-8 max-w-6xl mx-auto">
                <ReportComparisonPage document={document} />
                <FlaggedComparisonPage document={document} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: HISTORY */}
      {workspaceTab === 'history' && (
        <div className="flex-1 overflow-y-auto bg-white">
          <RevisionHistoryPage />
        </div>
      )}

      {/* Edit Paragraph Modal Dialog */}
      {draft && (
        <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-title"
            className="bg-white p-6 rounded-2xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto space-y-4"
          >
            <h2 id="edit-title" className="font-bold text-base text-slate-900">
              Edit Manuscript Passage
            </h2>

            <label className="block text-xs font-semibold text-slate-700">
              Proposed Text
              <textarea
                autoFocus
                value={draft.text}
                onChange={(e) => {
                  setDraft({ ...draft, text: e.target.value });
                  setApproveFacts(false);
                }}
                rows={7}
                className="block w-full border border-slate-200 rounded-xl p-3 mt-1.5 text-xs outline-none focus:border-indigo-500 font-sans"
              />
            </label>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs">
              <WordDiff originalText={draft.block.current_text} proposedText={draft.text} />
            </div>

            <label className="block text-xs font-semibold text-slate-700">
              Author Note (optional)
              <textarea
                value={draft.notes}
                onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                rows={2}
                placeholder="Brief reason for this revision..."
                className="block w-full border border-slate-200 rounded-lg p-2 mt-1 text-xs outline-none focus:border-indigo-500"
              />
            </label>

            {approval && (
              <div className="p-3.5 border border-amber-300 bg-amber-50 rounded-xl space-y-2 text-xs text-amber-900">
                <strong>{approval.message}</strong>
                <label className="flex gap-2 items-start mt-2">
                  <input
                    type="checkbox"
                    checked={approveFacts}
                    onChange={(e) => setApproveFacts(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span>
                    I confirm that the numbers, citations, or technical facts modified in this passage are intentional.
                  </span>
                </label>
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-2 border-t border-slate-100">
              <button
                disabled={!!busy}
                onClick={() => {
                  setDraft(null);
                  setApproval(null);
                  setError('');
                }}
                className="border border-slate-200 rounded-lg px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
              >
                Cancel
              </button>
              <button
                disabled={
                  !!busy ||
                  !draft.text.trim() ||
                  (!!approval && (!approveFacts || !draft.notes.trim()))
                }
                onClick={saveDraft}
                className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-5 py-2 text-xs font-semibold transition disabled:opacity-50"
              >
                {busy === 'save' ? 'Validating…' : 'Save Revision'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};
export default DocumentWorkspace;
