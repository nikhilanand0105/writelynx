import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  Upload,
  ArrowRight,
  Trash2,
  Download,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileDown
} from 'lucide-react';
import { api, downloadFile } from '../services/api';
import { DocumentItem } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export const DocumentsPage: React.FC = () => {
  const navigate = useNavigate();
  const { setActiveDocument, triggerRefresh, refreshTrigger } = useStudioStore();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'completed' | 'analyzing'>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.listDocuments()
      .then((docs) => {
        if (cancelled) return;
        setDocuments(docs);
      })
      .catch((err) => {
        console.error('Failed to load documents:', err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshTrigger]);

  const handleDelete = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this manuscript? This will permanently erase the document, highlights, and revision history.')) {
      try {
        await api.deleteDocument(docId);
        triggerRefresh();
      } catch (err: any) {
        alert(err.message || 'Failed to delete manuscript.');
      }
    }
  };

  const handleDownloadDocx = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    try {
      const res = await api.exportDocx(docId);
      await downloadFile(res.download_url);
    } catch (err: any) {
      alert(err.message || 'Failed to download DOCX.');
    }
  };

  const handleDownloadPdf = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    try {
      const res = await api.exportPdf(docId);
      await downloadFile(res.download_url);
    } catch (err: any) {
      alert(err.message || 'Failed to download PDF.');
    }
  };

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'completed' && doc.processing_status === 'completed') ||
      (statusFilter === 'analyzing' && doc.processing_status === 'analyzing');
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Ready for Review
          </span>
        );
      case 'analyzing':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600 animate-spin" />
            Reviewing Content
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3 h-3 text-rose-600" />
            Review Paused
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <FileText className="w-3 h-3 text-slate-500" />
            Upload Received
          </span>
        );
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">My Documents</h1>
          <p className="text-sm text-slate-500 mt-1">
            Access your uploaded manuscripts, review suggestions, and download updated Word reports.
          </p>
        </div>
        <button
          onClick={() => navigate('/documents/new')}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition self-start sm:self-auto"
        >
          <Upload className="w-4 h-4" />
          <span>New Document</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search manuscripts by filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-slate-200 bg-white text-xs outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-slate-500 font-medium">Filter:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="px-3 py-2 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 outline-none"
          >
            <option value="all">All Documents ({documents.length})</option>
            <option value="completed">Ready for Review</option>
            <option value="analyzing">In Progress</option>
          </select>
        </div>
      </div>

      {/* Document List */}
      {loading ? (
        <div className="py-16 text-center text-sm text-slate-500">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Loading manuscripts…
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
            <FileText className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-slate-900">
            {searchQuery ? 'No documents match your search' : 'No manuscripts uploaded yet'}
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {searchQuery
              ? 'Try searching with a different term or clear the search filter.'
              : 'Upload your academic report in Microsoft Word (.docx) format to begin diagnostic originality and attribution analysis.'}
          </p>
          {!searchQuery && (
            <button
              onClick={() => navigate('/documents/new')}
              className="mt-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
            >
              Upload First Document
            </button>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs divide-y divide-slate-100 overflow-hidden">
          {filteredDocs.map((doc) => (
            <div
              key={doc.id}
              onClick={() => {
                setActiveDocument(doc);
                navigate(`/documents/${doc.id}`);
              }}
              className="p-5 md:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/80 cursor-pointer transition"
            >
              <div className="flex items-start gap-4 min-w-0">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0 mt-0.5">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-slate-900 truncate">
                      {doc.filename}
                    </span>
                    {getStatusBadge(doc.processing_status)}
                  </div>
                  <div className="text-xs text-slate-500 flex items-center gap-3 flex-wrap">
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

              <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                <button
                  onClick={(e) => handleDownloadDocx(e, doc.id)}
                  title="Download Revised Word (.docx)"
                  className="p-2 border border-slate-200 hover:bg-slate-100 rounded-lg text-slate-600 transition"
                >
                  <Download className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveDocument(doc);
                    navigate(`/documents/${doc.id}`);
                  }}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-xs"
                >
                  <span>Open Workspace</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={(e) => handleDelete(e, doc.id)}
                  title="Delete manuscript"
                  className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
export default DocumentsPage;
