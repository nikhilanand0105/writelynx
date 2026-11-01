import React, { useEffect, useState } from 'react';
import {
  FileText,
  Layers,
  AlertTriangle,
  CheckCircle2,
  Upload,
  ArrowRight,
  Trash2,
  Cpu,
  RefreshCw
} from 'lucide-react';
import { api } from '../services/api';
import { DocumentItem, AnalysisSummary } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export const DashboardPage: React.FC = () => {
  const { activeDocument, setActiveDocument, setActiveTab, triggerRefresh, refreshTrigger } = useStudioStore();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisSummary | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [refreshTrigger, activeDocument?.id]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [docs, healthInfo] = await Promise.all([
        api.listDocuments(),
        api.getHealth(),
      ]);
      setDocuments(docs);
      setHealth(healthInfo);

      if (docs.length > 0 && !activeDocument) {
        setActiveDocument(docs[0]);
      }

      const currentDocId = activeDocument?.id || (docs.length > 0 ? docs[0].id : null);
      if (currentDocId) {
        try {
          const res = await api.getAnalysisResults(currentDocId);
          setAnalysis(res);
        } catch (e) {
          setAnalysis(null);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    if (confirm('Delete this manuscript and all associated findings?')) {
      await api.deleteDocument(docId);
      if (activeDocument?.id === docId) {
        setActiveDocument(null);
      }
      triggerRefresh();
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {loading && <p role="status" className="text-sm text-slate-500">Loading saved data…</p>}
      {/* Welcome Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Manuscript Integrity Dashboard</h2>
          <p className="text-sm text-slate-500 mt-1">
            Empirical similarity analysis, strict formatting preservation, and citation audit studio.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => triggerRefresh()}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setActiveTab('new_analysis')}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <Upload className="w-4 h-4" />
            <span>Upload New Manuscript</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Active Manuscript</span>
            <FileText className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-3">
            <div className="text-xl font-bold text-slate-900 truncate">
              {activeDocument ? activeDocument.filename : 'None selected'}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {activeDocument ? `${activeDocument.word_count.toLocaleString()} words` : 'Upload a DOCX to begin'}
            </div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Local Overlap Ratio</span>
            <Layers className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900">
              {analysis ? `${analysis.metrics.local_textual_overlap_percentage}%` : 'Not analyzed'}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Against {analysis ? analysis.metrics.analyzed_sources_count : 0} indexed sources
            </div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Citation Warnings</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900">
              {analysis ? analysis.metrics.missing_citations_count : 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Uncited refs or quotes without attribution
            </div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Pending Findings</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900">
              {analysis ? analysis.metrics.unresolved_findings_count : 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Requires author inspection
            </div>
          </div>
        </div>
      </div>

      {/* System Status & Diagnostic Disclaimer */}
      <div className="bg-slate-900 text-white rounded-xl p-5 border border-slate-800 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">Backend: {health?.status || 'checking connection'}</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">
                {health ? 'Connected' : 'Unconfirmed'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              LibreOffice Headless: {health?.libreoffice ? 'Installed & Ready for PDF' : 'Not detected'} • DB: SQLite persistent • LLM Mode: {health?.default_provider}
            </p>
          </div>
        </div>
        <div className="text-xs text-slate-400 bg-slate-800/80 px-4 py-2.5 rounded-lg border border-slate-700 max-w-md">
          <strong className="text-slate-200">Scientific Integrity Notice:</strong> Diagnostic scores reflect strictly local similarity against user-supplied reference texts. This software does not scrape proprietary student databases.
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Available Manuscripts</h3>
          <span className="text-xs text-slate-500">{documents.length} document{documents.length === 1 ? '' : 's'}</span>
        </div>

        {documents.length === 0 ? (
          <div className="text-center py-16 px-4">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400 mb-3">
              <FileText className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-medium text-slate-900">No manuscripts uploaded yet</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Upload your academic research paper in Microsoft Word (.docx) format to begin diagnostic originality and citation analysis.
            </p>
            <button
              onClick={() => setActiveTab('new_analysis')}
              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
            >
              Upload DOCX Now
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {documents.map((doc) => {
              const isSelected = activeDocument?.id === doc.id;
              return (
                <div
                  key={doc.id}
                  onClick={() => setActiveDocument(doc)}
                  className={`px-6 py-4 flex items-center justify-between cursor-pointer transition ${
                    isSelected ? 'bg-indigo-50/40 border-l-4 border-indigo-600' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-900 flex items-center gap-2">
                        <span>{doc.filename}</span>
                        {isSelected && (
                          <span className="text-[10px] bg-indigo-100 text-indigo-700 font-semibold px-2 py-0.5 rounded">
                            {health ? 'Connected' : 'Unconfirmed'}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-3">
                        <span>{doc.word_count.toLocaleString()} words</span>
                        <span>•</span>
                        <span>{doc.original_paragraph_count} paragraphs</span>
                        <span>•</span>
                        <span>{doc.table_count} table{doc.table_count === 1 ? '' : 's'}</span>
                        <span>•</span>
                        <span>Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        setActiveDocument(doc);
                        setActiveTab('editor');
                      }}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 flex items-center gap-1.5 transition"
                    >
                      <span>Open Editor</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, doc.id)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
                      title="Delete manuscript"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
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
