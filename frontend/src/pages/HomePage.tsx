import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Upload,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Sparkles,
  Layers,
  Trash2,
  Download,
  AlertCircle,
  HelpCircle,
  FileCheck
} from 'lucide-react';
import { api, downloadFile } from '../services/api';
import { DocumentItem } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { setActiveDocument, triggerRefresh, refreshTrigger } = useStudioStore();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.listDocuments(), api.getMe().catch(() => null)])
      .then(([docs, userData]) => {
        if (cancelled) return;
        setDocuments(docs);
        setUser(userData);
      })
      .catch((err) => {
        console.error('Error loading home data:', err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshTrigger]);

  const latestDoc = documents.length > 0 ? documents[0] : null;

  const handleDelete = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    if (confirm('Delete this manuscript and all associated findings? This cannot be undone.')) {
      try {
        await api.deleteDocument(docId);
        triggerRefresh();
      } catch (err: any) {
        alert(err.message || 'Failed to delete document.');
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

  const getActionLabel = (doc: DocumentItem) => {
    if (doc.processing_status === 'analyzing') return 'View Progress';
    if (doc.processing_status === 'completed') return 'Continue Review';
    return 'Open Document';
  };

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-8">
      {/* Top Welcome Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              {user?.full_name ? `Welcome, ${user.full_name}` : 'Writelynx Academic Studio'}
            </h1>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
              VIT Exclusive
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Empirical originality verification, natural academic editing, and formatting-preserving revision.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/documents/new')}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <Upload className="w-4 h-4" />
            <span>Start New Document</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-16 text-center text-sm text-slate-500">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Loading your documents…
        </div>
      ) : documents.length === 0 ? (
        /* FIRST-TIME STUDENT VIEW (0 documents) */
        <div className="space-y-8">
          {/* Welcome Card */}
          <div className="bg-gradient-to-br from-indigo-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-8 md:p-10 shadow-md">
            <div className="max-w-2xl space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-medium border border-indigo-500/30">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Verified VIT Institutional SaaS</span>
              </div>
              <h2 className="text-3xl font-extrabold tracking-tight">
                Review your academic report with confidence.
              </h2>
              <p className="text-sm text-slate-300 leading-relaxed">
                Writelynx helps Vellore Institute of Technology students check academic originality, attribution, and structure in Microsoft Word (.docx) reports—preserving your original tables, formulas, citations, and layout without altering technical facts.
              </p>
              <div className="pt-2">
                <button
                  onClick={() => navigate('/documents/new')}
                  className="flex items-center gap-2 px-5 py-3 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-semibold shadow-sm transition"
                >
                  <Upload className="w-4 h-4" />
                  <span>Start New Document</span>
                  <ArrowRight className="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>
          </div>

          {/* 3-Stage Explanation: Choose -> Review -> Download */}
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider text-center mb-6">
              How Writelynx Works in 3 Simple Steps
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                  1
                </div>
                <h4 className="font-semibold text-slate-900 text-base">Choose Help Mode & Upload</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Select whether you need light proofreading, academic tone revision, or research and citation review. Complete payment and upload your Word (.docx) document.
                </p>
              </div>

              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                  2
                </div>
                <h4 className="font-semibold text-slate-900 text-base">Review Suggestions</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Inspect paragraph-by-paragraph suggestions. Review clear sentence diffs, check preserved numbers and citations, and choose to Accept, Edit, or Ignore.
                </p>
              </div>

              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                  3
                </div>
                <h4 className="font-semibold text-slate-900 text-base">Download Clean Word (.docx)</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Export the finished manuscript with all approved edits applied directly to your original Word document. Tables, headings, and formatting remain 100% intact.
                </p>
              </div>
            </div>
          </div>

          {/* Simple Paid Pricing Summary */}
          <div className="bg-white p-6 md:p-8 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-slate-900">Affordable Student Pricing</h3>
                <p className="text-xs text-slate-500 mt-0.5">Pay-per-document single use via instant UPI. No recurring subscriptions.</p>
              </div>
              <button
                onClick={() => navigate('/documents/new')}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 underline self-start sm:self-auto"
              >
                Choose a plan and start →
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-sm text-slate-900">Basic</span>
                  <span className="text-base font-bold text-indigo-950">₹20</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">Up to 4 pages · 15,000 characters · 10 MB limit</p>
                <p className="text-[11px] text-slate-400 mt-1">Ideal for short lab reports & seminar summaries.</p>
              </div>

              <div className="border-2 border-indigo-500 rounded-lg p-4 bg-indigo-50/20 relative">
                <span className="absolute -top-2.5 right-3 bg-indigo-600 text-white text-[10px] uppercase font-bold px-2 py-0.5 rounded">
                  Recommended
                </span>
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-sm text-slate-900">Standard</span>
                  <span className="text-base font-bold text-indigo-950">₹50</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">Up to 20 pages · 65,000 characters · 20 MB limit</p>
                <p className="text-[11px] text-slate-400 mt-1">Ideal for course project reports & capstone drafts.</p>
              </div>

              <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-sm text-slate-900">Extended</span>
                  <span className="text-base font-bold text-indigo-950">₹100</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">Up to 50 pages · 160,000 characters · 30 MB limit</p>
                <p className="text-[11px] text-slate-400 mt-1">Ideal for comprehensive thesis & research manuscripts.</p>
              </div>
            </div>
          </div>

          {/* Privacy & Disclaimers Link */}
          <div className="text-center text-xs text-slate-400 pt-4">
            <p>
              Writelynx never sells student documents or shares manuscripts with public AI datasets. All documents are retained ephemerally and can be permanently erased at any time in compliance with DPDP Act 2023.
            </p>
          </div>
        </div>
      ) : (
        /* RETURNING STUDENT VIEW (>= 1 document) */
        <div className="space-y-8">
          {/* Continue Previous Document Hero Card */}
          {latestDoc && (
            <div className="bg-white rounded-2xl border border-indigo-100 p-6 md:p-8 shadow-sm space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold text-indigo-600 uppercase tracking-wider">
                    Continue Previous Document
                  </div>
                  <h2 className="text-xl font-bold text-slate-900 mt-1 truncate max-w-xl">
                    {latestDoc.filename}
                  </h2>
                  <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
                    <span>{latestDoc.word_count.toLocaleString()} words</span>
                    <span>•</span>
                    <span>{latestDoc.original_paragraph_count} paragraphs</span>
                    <span>•</span>
                    <span>Uploaded {new Date(latestDoc.uploaded_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {getStatusBadge(latestDoc.processing_status)}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100">
                <button
                  onClick={() => {
                    setActiveDocument(latestDoc);
                    navigate(`/documents/${latestDoc.id}`);
                  }}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                >
                  <span>{getActionLabel(latestDoc)}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={(e) => handleDownloadDocx(e, latestDoc.id)}
                  className="flex items-center gap-1.5 px-4 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium transition"
                >
                  <Download className="w-3.5 h-3.5 text-slate-500" />
                  <span>Download Word (.docx)</span>
                </button>
              </div>
            </div>
          )}

          {/* Recent Documents Section */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Recent Manuscripts</h3>
                <p className="text-xs text-slate-500 mt-0.5">Your submitted documents and analysis status</p>
              </div>
              <button
                onClick={() => navigate('/documents')}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
              >
                View all documents ({documents.length}) →
              </button>
            </div>

            <div className="divide-y divide-slate-100">
              {documents.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => {
                    setActiveDocument(doc);
                    navigate(`/documents/${doc.id}`);
                  }}
                  className="px-6 py-4 flex items-center justify-between hover:bg-slate-50 cursor-pointer transition gap-4"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-900 truncate">
                        {doc.filename}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-3 flex-wrap">
                        <span>{doc.word_count.toLocaleString()} words</span>
                        <span>•</span>
                        <span>Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {getStatusBadge(doc.processing_status)}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveDocument(doc);
                        navigate(`/documents/${doc.id}`);
                      }}
                      className="px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 rounded-lg flex items-center gap-1 transition"
                    >
                      <span>Review</span>
                      <ArrowRight className="w-3 h-3 text-slate-400" />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, doc.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                      title="Delete manuscript"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default HomePage;
