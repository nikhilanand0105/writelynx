import { useEffect, useMemo, useState } from 'react';
import { Check, X, Edit3, RotateCcw, Undo2, Redo2, Search, ShieldCheck } from 'lucide-react';
import { api, ApiError, errorMessage } from '../services/api';
import { DocumentBlock, EditSuggestion, AnalysisFinding, DetectorHighlight, GroundedRevision } from '../types';
import { useStudioStore } from '../store/useStudioStore';
import { WordDiff } from '../components/WordDiff';
import { OriginalPreview } from '../components/OriginalPreview';

type Draft = { block: DocumentBlock; text: string; notes: string; suggestionId?: string };
type FactApproval = { message: string; violations: unknown[]; requires_fact_approval: boolean };

// Only paint spans that are actually present. Fuzzy mappings remain visible in
// the inspector without inventing precise character coordinates in the text.
function HighlightedText({ text, highlights }: { text: string; highlights: DetectorHighlight[] }) {
  const ranges = highlights.map(highlight => ({ start: text.indexOf(highlight.highlight_text), length: highlight.highlight_text.length })).filter(range => range.start >= 0 && range.length > 0).sort((a, b) => a.start - b.start);
  let cursor = 0;
  const output = [];
  for (const range of ranges) {
    if (range.start < cursor) continue;
    output.push(<span key={`text-${range.start}`}>{text.slice(cursor, range.start)}</span>);
    output.push(<mark key={`mark-${range.start}`} className="bg-amber-200 text-inherit">{text.slice(range.start, range.start + range.length)}</mark>);
    cursor = range.start + range.length;
  }
  output.push(<span key="end">{text.slice(cursor)}</span>);
  return <>{output}</>;
}

export function EditorPage() {
  const { activeDocument, activeBlockId, setActiveBlockId, setActiveTab, triggerRefresh, refreshTrigger } = useStudioStore();
  const [blocks, setBlocks] = useState<DocumentBlock[]>([]);
  const [suggestions, setSuggestions] = useState<EditSuggestion[]>([]);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [highlights, setHighlights] = useState<DetectorHighlight[]>([]);
  const [section, setSection] = useState('All');
  const [query, setQuery] = useState('');
  const [view, setView] = useState<'current' | 'original' | 'word'>('current');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [grounded, setGrounded] = useState<GroundedRevision | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [approval, setApproval] = useState<FactApproval | null>(null);
  const [approveFacts, setApproveFacts] = useState(false);
  const [mode, setMode] = useState('academic_revision');
  useEffect(() => {
    if (!activeDocument) return;
    let cancelled = false;
    setLoading(true); setError('');
    Promise.all([api.getDocumentStructure(activeDocument.id), api.listSuggestions(activeDocument.id), api.getAnalysisResults(activeDocument.id), api.listDetectorHighlights(activeDocument.id)])
      .then(([structure, nextSuggestions, analysis, nextHighlights]) => {
        if (cancelled) return;
        setBlocks(structure.blocks); setSuggestions(nextSuggestions); setFindings(analysis.findings); setHighlights(nextHighlights);
        if (!structure.blocks.some(block => block.id === useStudioStore.getState().activeBlockId)) setActiveBlockId(structure.blocks[0]?.id || null);
      }).catch(error => { if (!cancelled) setError(errorMessage(error)); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeDocument?.id, refreshTrigger, setActiveBlockId]);
  useEffect(() => { setGrounded(null); setDraft(null); setApproval(null); setApproveFacts(false); }, [activeBlockId]);
  const current = blocks.find(block => block.id === activeBlockId);
  const sections = useMemo(() => ['All', ...new Set(blocks.map(block => block.section_id))], [blocks]);
  const visible = blocks.filter(block => (section === 'All' || block.section_id === section) && (!query || block.current_text.toLowerCase().includes(query.toLowerCase())) && (filter === 'all' || (filter === 'changed' ? block.original_text !== block.current_text : filter === 'highlights' ? highlights.some(highlight => highlight.block_id === block.id) : findings.some(finding => finding.block_id === block.id))));
  const currentFindings = findings.filter(finding => finding.block_id === activeBlockId);
  const currentSuggestions = suggestions.filter(suggestion => suggestion.block_id === activeBlockId);
  const currentHighlights = highlights.filter(highlight => highlight.block_id === activeBlockId);
  const act = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label); setError('');
    try { await action(); triggerRefresh(); } catch (error) { setError(errorMessage(error)); } finally { setBusy(''); }
  };
  const openDraft = (block: DocumentBlock, text: string, suggestionId?: string) => { setDraft({ block, text, notes: '', suggestionId }); setApproval(null); setApproveFacts(false); };
  const saveDraft = async () => {
    if (!draft) return;
    setBusy('save'); setError('');
    try {
      if (draft.suggestionId) await api.reviseSuggestion(draft.suggestionId, draft.text, draft.notes, approveFacts);
      else await api.reviseBlockManually(draft.block.id, draft.text, draft.notes, approveFacts);
      setDraft(null); setGrounded(null); setApproval(null); triggerRefresh();
    } catch (error) {
      if (error instanceof ApiError && (error.detail as FactApproval)?.requires_fact_approval) setApproval(error.detail as FactApproval);
      setError(errorMessage(error));
    } finally { setBusy(''); }
  };
  const accept = async (suggestion: EditSuggestion) => {
    setBusy(suggestion.id); setError('');
    try { await api.acceptSuggestion(suggestion.id); triggerRefresh(); }
    catch (error) {
      if (error instanceof ApiError && (error.detail as FactApproval)?.requires_fact_approval && current) { openDraft(current, suggestion.proposed_text, suggestion.id); setApproval(error.detail as FactApproval); }
      setError(errorMessage(error));
    } finally { setBusy(''); }
  };
  if (!activeDocument) return <div className="p-12 text-center text-slate-500">Select or upload a manuscript to open the editor.</div>;
  return <div className="flex flex-col h-[calc(100vh-4rem)] min-h-[650px]">
    <div className="p-3 bg-white border-b flex items-center justify-between flex-wrap gap-3 text-xs">
      <div className="flex gap-2"><button disabled={!!busy} onClick={() => act('undo', () => api.undo(activeDocument.id))} className="border rounded-lg px-3 py-2 flex items-center gap-1"><Undo2 size={14} />Undo</button><button disabled={!!busy} onClick={() => act('redo', () => api.redo(activeDocument.id))} className="border rounded-lg px-3 py-2 flex items-center gap-1"><Redo2 size={14} />Redo</button></div>
      <div className="flex items-center gap-2"><select aria-label="Editing intensity" value={mode} onChange={event => setMode(event.target.value)} className="border rounded-lg p-2"><option value="light_copyediting">Minimal proofreading</option><option value="academic_revision">Natural Academic Voice</option><option value="research_grounded">Research-grounded revision</option></select><button disabled={!!busy || activeDocument.processing_status === 'analyzing'} onClick={() => act('analysis', () => api.startAnalysis(activeDocument.id, mode))} className="bg-indigo-600 text-white rounded-lg p-2">Re-run diagnostics</button></div>
    </div>
    {error && <div role="alert" className="p-3 bg-rose-50 border-b border-rose-200 text-sm text-rose-800">{error}</div>}
    <div className="grid grid-cols-1 xl:grid-cols-[180px_minmax(300px,1fr)_360px] min-h-0 flex-1 overflow-auto">
      <nav aria-label="Document outline" className="bg-white border-r p-3 overflow-auto space-y-3 xl:block">
        <h2 className="font-semibold text-xs uppercase text-slate-500">Document outline</h2>
        <label className="flex gap-1 items-center border rounded-lg p-2"><Search size={14} /><input aria-label="Search manuscript" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search manuscript" className="w-full min-w-0 text-xs outline-none" /></label>
        <select aria-label="Filter manuscript blocks" value={filter} onChange={event => setFilter(event.target.value)} className="w-full border rounded-lg p-2 text-xs"><option value="all">All blocks</option><option value="changed">Edited blocks</option><option value="highlights">Imported highlights</option><option value="findings">Diagnostic findings</option></select>
        <div className="flex xl:flex-col gap-1 overflow-auto">{sections.map(item => <button key={item} onClick={() => setSection(item)} className={`text-left text-xs p-2 rounded-lg ${section === item ? 'bg-indigo-50 text-indigo-800' : 'hover:bg-slate-50'}`}>{item}</button>)}</div>
        <p className="text-xs text-slate-500">{blocks.length} blocks · {activeDocument.table_count} tables · {activeDocument.image_count} images</p>
      </nav>
      <section aria-label="Manuscript passages" className="bg-slate-100 overflow-auto p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span>{visible.length} passages</span><select aria-label="Document view" value={view} onChange={event => setView(event.target.value as typeof view)} className="border bg-white rounded-lg p-2"><option value="current">Current text</option><option value="original">Immutable original text</option><option value="word">Original document preview</option></select></div>
        <p className="text-xs text-slate-600">Yellow marks show extracted report text where an exact span is available. These judgments do not establish authorship. Text view is a structural reading view; use Word preview or export to inspect layout.</p>
        {view === 'word' ? <OriginalPreview documentId={activeDocument.id} /> : <div className="bg-white rounded-xl border p-5 md:p-8 space-y-4">
          {loading && <p role="status" className="text-sm text-slate-500">Loading passages…</p>}
          {!loading && visible.length === 0 && <p className="text-sm text-slate-500">No passages match these filters.</p>}
          {visible.map(block => <button key={block.id} data-testid={`block-${block.block_index}`} onClick={() => setActiveBlockId(block.id)} className={`block text-left w-full p-3 rounded-lg border transition ${block.id === activeBlockId ? 'border-indigo-500 ring-2 ring-indigo-100' : 'border-transparent hover:border-slate-300'}`}>
            <span className="text-[10px] text-slate-500 flex justify-between gap-2 mb-2"><span>{block.block_type.replace(/_/g, ' ')} · {block.block_index + 1}</span><span>{block.is_protected ? 'Protected structure' : ''}{block.original_text !== block.current_text ? ' · Edited' : ''}{highlights.some(highlight => highlight.block_id === block.id) ? ' · Imported highlight' : ''}</span></span>
            <span className={`block whitespace-pre-wrap leading-7 ${['heading', 'title'].includes(block.block_type) ? 'font-bold text-lg' : 'font-serif text-base'}`}><HighlightedText text={view === 'original' ? block.original_text : block.current_text} highlights={highlights.filter(highlight => highlight.block_id === block.id)} /></span>
          </button>)}
        </div>}
      </section>
      <section aria-label="Passage inspector" className="bg-white border-l overflow-auto p-4 space-y-5">
        {!current ? <p className="text-sm text-slate-500">Select a passage to review.</p> : <>
          <div className="flex justify-between items-center gap-2"><div><h2 className="font-semibold text-sm">Passage inspector</h2><span className="text-[10px] text-slate-500 break-all">{current.id}</span></div><button disabled={!!busy || current.is_protected} onClick={() => openDraft(current, current.current_text)} className="flex items-center gap-1 border rounded-lg px-2 py-1 text-xs"><Edit3 size={13} />Edit</button></div>
          {current.is_protected && <p className="text-xs p-3 bg-slate-50 border rounded-lg">This block contains protected document structure. Editing is disabled to preserve the original construct.</p>}
          <div className="text-xs bg-indigo-50 border border-indigo-200 p-3 rounded-lg space-y-2"><strong className="flex items-center gap-1"><ShieldCheck size={14} /> Protected facts and citations</strong><p>Server validation checks numbers, units, citations, and technical identifiers before each edit. A detected change requires explicit approval and an author note.</p><p className="font-mono break-words">{[...new Set(current.current_text.match(/\b\d+(?:\.\d+)?(?:%|\s?(?:ms|bars|features|channels|GB))?\b|\[\d+(?:[-–,]\s*\d+)*\]/g) || [])].join(' · ') || 'No numeric or citation tokens detected in this passage.'}</p><p className="text-slate-600">Detected tokens are preservation candidates, not evidence that the research values are verified.</p></div>
          {currentHighlights.length > 0 && <div className="space-y-2"><h3 className="text-xs font-bold">Imported detector passages</h3>{currentHighlights.map(highlight => <div key={highlight.id} className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs space-y-2"><p>{highlight.highlight_text}</p><p className="text-amber-900">Page {highlight.page_number} · {highlight.extraction_strategy} · mapping {Math.round(highlight.match_confidence * 100)}% · {highlight.mapping_status}</p></div>)}<p className="text-[11px] text-slate-500">Confidence describes mapping quality, not AI authorship.</p></div>}
          <div className="space-y-3"><h3 className="text-xs font-bold">Editorial findings ({currentFindings.length})</h3>{currentFindings.length === 0 && <p className="text-xs text-slate-500">No stored finding for this passage. Automated checks are not proof of correctness.</p>}{currentFindings.map(finding => <div key={finding.id} className="border rounded-lg p-3 text-xs space-y-2"><div className="flex justify-between gap-2"><strong>{(finding.issue_category || finding.finding_type).replace(/_/g, ' ')}</strong><span>{finding.severity}</span></div>{finding.matched_text && <blockquote className="border-l-2 pl-2 text-slate-600">{finding.matched_text}</blockquote>}<p>{finding.evidence?.reason || finding.evidence?.explanation || finding.evidence?.message || finding.recommended_action || 'Review the indicated passage and supporting sources.'}</p>{finding.required_evidence?.length ? <p>Evidence needed: {finding.required_evidence.join(', ')}</p> : null}<p>Status: {finding.review_status.replace(/_/g, ' ')}</p><div className="flex flex-wrap gap-2"><button disabled={!!busy} onClick={() => act(finding.id, () => api.reviewFinding(finding.id, 'user_reviewed', 'Author reviewed this finding in the paragraph editor.'))} className="underline text-indigo-700">Mark user-reviewed</button><button disabled={!!busy} onClick={() => act(finding.id, () => api.reviewFinding(finding.id, 'rejected'))} className="underline">Dismiss finding</button><button onClick={() => setActiveTab('evidence')} className="underline">Supply evidence</button></div></div>)}</div>
          <div className="space-y-3"><h3 className="text-xs font-bold">Revision suggestions ({currentSuggestions.length})</h3>{currentSuggestions.map(suggestion => <div key={suggestion.id} className="border rounded-lg p-3 text-xs space-y-3"><p className="font-semibold">{suggestion.review_status} · {suggestion.issue_type.replace(/_/g, ' ')}</p><WordDiff originalText={suggestion.original_text} proposedText={suggestion.proposed_text} /><p>{suggestion.reason}</p><p>Fact validation: {suggestion.validation_status} · Citations {suggestion.citations_preserved ? 'preserved' : 'need review'}</p>{suggestion.review_status === 'pending' && <div className="flex flex-wrap gap-2"><button disabled={!!busy} onClick={() => accept(suggestion)} className="bg-indigo-600 text-white rounded px-2 py-1 flex gap-1"><Check size={12} />Accept</button><button disabled={!!busy} onClick={() => act(suggestion.id, () => api.rejectSuggestion(suggestion.id))} className="border rounded px-2 py-1 flex gap-1"><X size={12} />Reject</button><button disabled={!!busy} onClick={() => openDraft(current, suggestion.proposed_text, suggestion.id)} className="underline">Modify suggestion</button></div>}</div>)}</div>
          <button disabled={!!busy || current.is_protected} onClick={async () => { setBusy('ground'); setError(''); try { setGrounded(await api.groundBlockRevision(activeDocument.id, current.id)); } catch (error) { setError(errorMessage(error)); } finally { setBusy(''); } }} className="w-full border border-indigo-300 text-indigo-800 rounded-lg p-2 text-xs">{busy === 'ground' ? 'Retrieving evidence…' : 'Retrieve evidence & propose revision'}</button>
          {grounded && <div className="space-y-3 text-xs p-3 border rounded-lg"><strong>Evidence-grounded review</strong><p>Validation: {grounded.validation_status}</p>{grounded.matching_evidence.map(evidence => <div key={evidence.evidence_id}><strong>{evidence.title}</strong><p className="text-slate-600 mt-1">{evidence.content_snippet}</p></div>)}{grounded.missing_information.map((missing, index) => <p key={index} className="text-amber-900">Needs evidence: {missing}</p>)}{grounded.author_clarifying_questions.map((question, index) => <p key={index}>{question.question} <span className="text-slate-500">{question.suggested_evidence}</span></p>)}<WordDiff originalText={grounded.original_text} proposedText={grounded.proposed_text} /><button onClick={() => setActiveTab('evidence')} className="underline">Provide evidence or an author answer</button>{grounded.proposed_text !== current.current_text && <button onClick={() => openDraft(current, grounded.proposed_text)} className="block bg-indigo-600 text-white p-2 rounded">Review proposed text</button>}</div>}
          {current.current_text !== current.original_text && <div className="space-y-3 border-t pt-4 text-xs"><strong>Applied changes</strong><WordDiff originalText={current.original_text} proposedText={current.current_text} /><button disabled={!!busy} onClick={() => act('restore', () => api.restoreBlock(activeDocument.id, current.id))} className="flex items-center gap-1 underline"><RotateCcw size={13} />Restore original passage</button></div>}
        </>}
      </section>
    </div>
    {draft && <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4"><section role="dialog" aria-modal="true" aria-labelledby="edit-title" className="bg-white p-6 rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-auto space-y-4"><h2 id="edit-title" className="font-bold text-lg">Review paragraph revision</h2><label className="block text-sm">Proposed text<textarea autoFocus value={draft.text} onChange={event => { setDraft({ ...draft, text: event.target.value }); setApproveFacts(false); }} rows={8} className="block w-full border rounded-lg p-3 mt-2" /></label><div className="bg-slate-50 border rounded-lg p-3 text-sm"><WordDiff originalText={draft.block.current_text} proposedText={draft.text} /></div><label className="block text-sm">Author note<textarea value={draft.notes} onChange={event => setDraft({ ...draft, notes: event.target.value })} rows={2} className="block w-full border rounded-lg p-2 mt-1" /></label>{approval && <div className="p-4 border border-amber-300 bg-amber-50 rounded-lg space-y-2 text-sm"><strong>{approval.message}</strong>{approval.violations?.map((violation, index) => <p key={index}>{typeof violation === 'string' ? violation : JSON.stringify(violation)}</p>)}<label className="flex gap-2 items-start"><input type="checkbox" checked={approveFacts} onChange={event => setApproveFacts(event.target.checked)} /><span>I explicitly approve these protected-fact changes and have explained the reason in the author note.</span></label></div>}{error && <p role="alert" className="text-sm text-rose-800">{error}</p>}<div className="flex justify-end gap-3"><button disabled={!!busy} onClick={() => { setDraft(null); setApproval(null); setError(''); }} className="border rounded-lg p-2 text-sm">Cancel</button><button disabled={!!busy || !draft.text.trim() || (!!approval && (!approveFacts || !draft.notes.trim()))} onClick={saveDraft} className="bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm">{busy === 'save' ? 'Validating…' : 'Save author-approved revision'}</button></div></section></div>}
  </div>;
}
