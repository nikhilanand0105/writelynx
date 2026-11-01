import { useEffect, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { api, downloadFile, downloadJson, errorMessage } from '../services/api';
import { PreservationReport, ExportItem, AppSettings } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export function ExportCenterPage() {
  const { activeDocument, refreshTrigger } = useStudioStore();
  const [report, setReport] = useState<PreservationReport | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [exports, setExports] = useState<ExportItem[]>([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const validate = async () => {
    if (!activeDocument) return;
    setBusy('validation'); setError(''); setReport(null);
    try { setReport(await api.validateDocument(activeDocument.id)); }
    catch (error) { setError(errorMessage(error)); } finally { setBusy(''); }
  };
  useEffect(() => { setReport(null); setExports([]); api.getSettings().then(setSettings).catch(error => setError(errorMessage(error))); }, [activeDocument?.id]);
  useEffect(() => { setReport(null); }, [refreshTrigger]);
  const generate = async (type: 'docx' | 'pdf' | 'audit' | 'history' | 'evidence' | 'highlights') => {
    if (!activeDocument) return;
    setBusy(type); setError('');
    try {
      if (type === 'history' || type === 'evidence' || type === 'highlights') {
        const data = await (type === 'history' ? api.listRevisions(activeDocument.id) : type === 'evidence' ? api.listResearchEvidence(activeDocument.id) : api.listDetectorHighlights(activeDocument.id));
        downloadJson(data, `${activeDocument.filename}_${type}.json`);
      } else {
        const result = await (type === 'docx' ? api.exportDocx(activeDocument.id) : type === 'pdf' ? api.exportPdf(activeDocument.id) : api.exportAuditCsv(activeDocument.id));
        setExports(previous => [result, ...previous]);
        if (result.preservation_report && 'valid' in result.preservation_report) setReport(result.preservation_report);
        await downloadFile(result.download_url);
      }
    } catch (error) { setError(errorMessage(error)); } finally { setBusy(''); }
  };
  if (!activeDocument) return <div className="p-12 text-center text-slate-500">Select a manuscript to export.</div>;
  const checks: Array<[string, boolean | undefined, string]> = [
    ['OOXML archive integrity', report?.archive_valid, 'Package validation'],
    ['Reopen verification', report?.reopened_successfully, 'Reopened by the document parser'],
    ['Paragraph count', report?.paragraph_count_match, report ? `${report.original_paragraph_count} original / ${report.final_paragraph_count} exported` : 'Not checked'],
    ['Protected facts', report?.protected_facts_intact, 'Values, units, technical identifiers'],
    ['Citation preservation', report?.citation_integrity_intact, 'Citation invariants'],
  ];
  return <div className="p-8 max-w-5xl mx-auto space-y-6">
    <div><h2 className="text-2xl font-bold">Export & Preservation Center</h2><p className="mt-1 text-sm text-slate-600">Generate versioned outputs from approved edits. The uploaded original remains unchanged.</p></div>
    {error && <p role="alert" className="p-4 border border-rose-200 bg-rose-50 rounded-xl text-sm text-rose-800">{error}</p>}
    <section className="bg-white border rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Preservation validation</h3><button onClick={validate} disabled={!!busy} className="flex items-center gap-2 text-sm border rounded-lg p-2"><RefreshCw size={16} className={busy === 'validation' ? 'animate-spin' : ''} />{busy === 'validation' ? 'Validating…' : 'Run validation'}</button></div>
      <p role="status" className="text-sm">{report ? report.valid ? 'Automated preservation checks passed.' : 'Validation found issues. Review the details below.' : 'Not yet validated for this document state.'}</p>
      <div className="grid md:grid-cols-2 gap-3">{checks.map(([label, passed, detail]) => <div key={label} className="border rounded-lg p-3 text-sm"><div className="flex justify-between gap-3"><strong>{label}</strong><span className={passed === true ? 'text-emerald-700' : passed === false ? 'text-rose-700' : 'text-slate-500'}>{passed === true ? 'Passed' : passed === false ? 'Review required' : 'Not checked'}</span></div><p className="text-xs text-slate-500 mt-1">{detail}</p></div>)}</div>
      {report && <><p className="text-sm text-slate-600">{report.table_count} tables · {report.image_count} images. Automated structure checks do not guarantee pixel-identical pagination.</p>{[...report.warnings || [], ...report.protected_fact_violations || [], ...report.citation_warnings || []].map((warning, index) => <p key={index} className="text-sm text-amber-900">{warning}</p>)}<button className="text-sm underline" onClick={() => downloadJson(report, 'preservation-report.json')}>Download validation report</button></>}
    </section>
    <section className="grid md:grid-cols-2 gap-4">{([
      ['docx', 'Revised DOCX', 'Applies approved changes to the original OOXML package and reopens the result.'],
      ['pdf', 'Revised PDF', settings?.libreoffice_available ? 'Converts with LibreOffice and inspects the generated PDF.' : 'Requires a working LibreOffice installation on the backend.'],
      ['audit', 'Diagnostic audit (CSV)', 'Download the recorded findings and their review status.'],
      ['history', 'Revision history (JSON)', 'Download the timestamped record of edits and decisions.'],
      ['evidence', 'Research evidence (JSON)', 'Download indexed records, extracted content, and source metadata.'],
      ['highlights', 'Detector alignment (JSON)', 'Download extracted passages, geometry, and mapping decisions.'],
    ] as const).map(([type, label, description]) => <div key={type} className="border rounded-xl p-5 bg-white flex flex-col gap-3"><h3 className="font-semibold">{label}</h3><p className="text-sm text-slate-600 flex-1">{description}</p><button disabled={!!busy || (type === 'pdf' && !settings?.libreoffice_available)} onClick={() => generate(type)} className="flex items-center justify-center gap-2 bg-indigo-600 text-white p-2 rounded-lg text-sm"><Download size={16} />{busy === type ? 'Preparing…' : `Export ${label}`}</button></div>)}</section>
    {exports.length > 0 && <section className="bg-white border rounded-xl p-5 space-y-3"><h3 className="font-semibold">Generated in this session</h3>{exports.map(item => <div key={item.id} className="flex justify-between text-sm gap-4"><span>{item.export_type.toUpperCase()} · {new Date(item.created_at).toLocaleString()}</span><button className="underline text-indigo-700" onClick={() => downloadFile(item.download_url)}>Download again</button></div>)}</section>}
  </div>;
}
