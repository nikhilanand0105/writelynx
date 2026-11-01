import React, { useState, } from 'react';
import { api } from '../services/api';
import { DocumentItem, ReportComparison } from '../types';
import {
  GitCompare,
  AlertTriangle,
  CheckCircle2,
  Upload,
  Info,
  RefreshCw,
  } from 'lucide-react';

interface Props {
  document: DocumentItem | null;
}

export const ReportComparisonPage: React.FC<Props> = ({ document: doc }) => {
  const [comparison, setComparison] = useState<ReportComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file1, setFile1] = useState<File | null>(null);
  const [file2, setFile2] = useState<File | null>(null);

  const handleRunComparison = async () => {
    if (!doc || !file2) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.compareDetectorReports(doc.id, file2, file1 || undefined);
      setComparison(res);
    } catch (e: any) {
      setError(e.message || 'Failed to compare detector reports');
    } finally {
      setLoading(false);
    }
  };

  if (!doc) {
    return (
      <div className="p-8 text-center text-zinc-500">
        Please select a document from the dashboard to compare detector reports.
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <GitCompare className="w-6 h-6 text-blue-500" />
            Multi-Report Detector Comparison
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Programmatic fragment-level comparison across repeated or historical detector PDF exports.
          </p>
        </div>
      </div>

      {/* Mandatory Transparent Disclaimer */}
      <div className="p-4 bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-300 dark:border-zinc-700 rounded-xl space-y-2">
        <div className="flex items-center gap-2 text-zinc-900 dark:text-zinc-100 font-semibold text-sm">
          <Info className="w-4 h-4 text-blue-500 flex-shrink-0" />
          <span>Scientific Disclaimer on Detector Score Comparability</span>
        </div>
        <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
          {comparison?.disclaimer ||
            "A detector score comparison is valid only when documents, evaluated character ranges, and vendor model versions are identical. Differences in score do not prove changes in document originality, nor do identical scores prove the presence of AI-authored content."}
        </p>
      </div>

      {/* Upload Form to Compare Reports */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm space-y-4">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
          <Upload className="w-4 h-4 text-blue-500" />
          Select Detector PDF Reports to Contrast
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl p-4 space-y-2 bg-zinc-50/50 dark:bg-zinc-800/20">
            <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider">
              Report 1 (Earlier Export)
            </span>
            <input
              type="file"
              accept=".pdf"
              onChange={e => setFile1(e.target.files ? e.target.files[0] : null)}
              className="text-xs block w-full text-zinc-600 dark:text-zinc-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-blue-100 dark:file:bg-blue-900 file:text-blue-800 dark:file:text-blue-200 cursor-pointer"
            />
            <span className="text-[11px] text-zinc-500">
              {file1 ? file1.name : (doc.detector_pdf_path ? 'Defaults to currently imported detector PDF' : 'Select earlier PDF')}
            </span>
          </div>

          <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl p-4 space-y-2 bg-zinc-50/50 dark:bg-zinc-800/20">
            <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider">
              Report 2 (Latest Export) *
            </span>
            <input
              type="file"
              accept=".pdf"
              required
              onChange={e => setFile2(e.target.files ? e.target.files[0] : null)}
              className="text-xs block w-full text-zinc-600 dark:text-zinc-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-blue-100 dark:file:bg-blue-900 file:text-blue-800 dark:file:text-blue-200 cursor-pointer"
            />
            <span className="text-[11px] text-zinc-500">
              {file2 ? file2.name : 'Upload newer ZeroGPT or Turnitin PDF to compare'}
            </span>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleRunComparison}
            disabled={!file2 || loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm disabled:opacity-50 flex items-center gap-2 transition"
          >
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <GitCompare className="w-3.5 h-3.5" />}
            <span>Compare Reports</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs">
          {error}
        </div>
      )}

      {/* Comparison Results */}
      {comparison && (
        <div className="space-y-6">
          {/* Key Metric Diff Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
              <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Earlier Report Score</span>
              <p className="text-2xl font-bold text-amber-600 mt-1">
                {comparison.earlier_report.reported_score != null ? `${comparison.earlier_report.reported_score}%` : 'N/A'}
              </p>
              <span className="text-[11px] text-zinc-400">
                {comparison.earlier_report.total_fragments} fragments extracted
              </span>
            </div>

            <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
              <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Latest Report Score</span>
              <p className="text-2xl font-bold text-amber-600 mt-1">
                {comparison.latest_report.reported_score != null ? `${comparison.latest_report.reported_score}%` : 'N/A'}
              </p>
              <span className="text-[11px] text-zinc-400">
                {comparison.latest_report.total_fragments} fragments extracted
              </span>
            </div>

            <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
              <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Overlapping Fragments</span>
              <p className="text-2xl font-bold text-emerald-600 mt-1">
                {comparison.comparison_summary.overlapping_fragments_count}
              </p>
              <span className="text-[11px] text-zinc-400">
                {comparison.comparison_summary.verbatim_identical_count} verbatim identical
              </span>
            </div>

            <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
              <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Outcome Identity</span>
              <p className="text-sm font-bold text-blue-600 mt-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span>{comparison.comparison_summary.is_essentially_identical ? 'Identical Outcome' : 'Variant Outcome'}</span>
              </p>
              <span className="text-[11px] text-zinc-400">
                Reported score difference: {comparison.comparison_summary.score_difference == null ? 'Not available' : `${comparison.comparison_summary.score_difference} percentage points`}
              </span>
            </div>
          </div>

          {/* Conclusion Banner */}
          <div className="p-4 bg-blue-50/80 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl text-xs space-y-1">
            <span className="font-semibold text-blue-900 dark:text-blue-300">
              Comparative Analysis Finding:
            </span>
            <p className="text-blue-800/90 dark:text-blue-400/90 leading-relaxed">
              {comparison.comparison_summary.conclusion}
            </p>
          </div>

          {/* Truncation Status Alert */}
          {comparison.comparison_summary.both_truncated && (
            <div className="p-4 bg-amber-50/80 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-xl flex items-start gap-3">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs space-y-1 text-amber-900 dark:text-amber-300">
                <p className="font-semibold">Both reports indicate limited coverage</p>
                <p className="text-amber-800/80 dark:text-amber-400/80">
                  The reports cover limited inputs. Matching limits alone do not establish matching submitted text. Sections outside the reported scope must not be treated as evaluated.
                </p>
              </div>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">{[['New highlights', comparison.newly_highlighted], ['Removed highlights', comparison.removed_highlights]].map(([label, items]) => <section key={String(label)} className="bg-white border rounded-xl p-4 space-y-2"><h3 className="text-sm font-semibold">{String(label)} ({(items as any[]).length})</h3>{(items as any[]).map((item, index) => <p key={index} className="text-xs">Page {item.page_number}: {item.text || item.highlight_text}</p>)}</section>)}</div>
          {/* Overlapping Fragments Table */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                Overlapping Highlight Fragments ({comparison.unchanged_highlights.length})
              </h3>
              <span className="text-xs text-zinc-400">Matched fragment pairs</span>
            </div>

            <div className="divide-y divide-zinc-200 dark:divide-zinc-800 max-h-96 overflow-y-auto">
              {comparison.unchanged_highlights.map((item, idx) => (
                <div key={idx} className="p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/40 text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-zinc-500 text-[11px]">
                    <span className="font-mono font-medium text-zinc-700 dark:text-zinc-300">
                      Page {item.earlier_fragment.page_number}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-medium text-[10px]">
                      {item.is_verbatim_identical ? '100% Verbatim Match' : `${item.similarity_ratio}% Match`}
                    </span>
                  </div>
                  <p className="text-zinc-800 dark:text-zinc-200 font-serif italic bg-amber-50/30 dark:bg-amber-950/20 p-2 rounded border-l-2 border-amber-400">
                    "{item.earlier_fragment.text || item.earlier_fragment.highlight_text}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
