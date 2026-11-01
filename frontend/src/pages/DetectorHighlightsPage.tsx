import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { DocumentItem, DetectorHighlight, DocumentBlock } from '../types';
import {
  ShieldAlert,
  FileCheck2,
  AlertTriangle,
  Upload,
  Link,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  Search,
  } from 'lucide-react';

interface Props {
  document: DocumentItem | null;
  onRefreshDocument?: () => void;
}

export const DetectorHighlightsPage: React.FC<Props> = ({ document: doc, onRefreshDocument }) => {
  const [highlights, setHighlights] = useState<DetectorHighlight[]>([]);
  const [blocks, setBlocks] = useState<DocumentBlock[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedHighlight, setSelectedHighlight] = useState<DetectorHighlight | null>(null);
  const [targetBlockId, setTargetBlockId] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = async () => {
    if (!doc) return;
    setLoading(true);
    setError(null);
    try {
      const [hls, struct] = await Promise.all([
        api.listDetectorHighlights(doc.id),
        api.getDocumentStructure(doc.id)
      ]);
      setHighlights(hls);
      setBlocks(struct.blocks);
    } catch (e: any) {
      setError(e.message || 'Failed to load detector highlights');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [doc?.id]);

  const handleUploadPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!doc || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setUploading(true);
    setError(null);
    try {
      await api.uploadDetectorPdf(doc.id, file);
      if (onRefreshDocument) onRefreshDocument();
      await loadData();
    } catch (e: any) {
      setError(e.message || 'Failed to upload detector PDF');
    } finally {
      setUploading(false);
    }
  };

  const handleManualMap = async (highlightId: string, blockId: string) => {
    if (!blockId) return;
    try {
      await api.manuallyMapHighlight(highlightId, blockId);
      await loadData();
      setSelectedHighlight(null);
    } catch (e: any) {
      alert(e.message || 'Failed to map highlight');
    }
  };

  if (!doc) {
    return (
      <div className="p-8 text-center text-zinc-500">
        Please select a document from the dashboard to review detector highlights.
      </div>
    );
  }

  const filteredHighlights = highlights.filter(h => {
    if (filterStatus === 'matched' && h.mapping_status !== 'matched' && h.mapping_status !== 'manually_corrected') return false;
    if (filterStatus === 'unmapped' && (h.mapping_status === 'matched' || h.mapping_status === 'manually_corrected')) return false;
    if (searchQuery && !h.highlight_text.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const matchedCount = highlights.filter(h => h.mapping_status === 'matched' || h.mapping_status === 'manually_corrected').length;
  const unmappedCount = highlights.length - matchedCount;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {error && <p role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-800">{error}</p>}
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-amber-500" />
            External Detector Highlights & DOCX Alignment
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Imported third-party AI detector reports (e.g. ZeroGPT, Turnitin) aligned with native Word paragraphs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="relative cursor-pointer bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium px-4 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 shadow-sm">
            <Upload className="w-4 h-4" />
            <span>{uploading ? 'Processing PDF...' : 'Import Detector PDF'}</span>
            <input
              type="file"
              accept=".pdf"
              className="sr-only"
              onChange={handleUploadPdf}
              disabled={uploading}
            />
          </label>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 border border-zinc-300 dark:border-zinc-700 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-zinc-600 dark:text-zinc-300"
            title="Refresh Highlights"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Critical Methodology & Scientific Disclaimer */}
      <div className="p-4 bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-xl space-y-2">
        <div className="flex items-center gap-2 text-amber-800 dark:text-amber-300 font-medium text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>Scientific Disclaimer & Diagnostic Distinction</span>
        </div>
        <p className="text-xs text-amber-900/80 dark:text-amber-300/80 leading-relaxed">
          <strong>External detector outputs do not constitute proof of AI authorship or academic misconduct.</strong> The imported percentage is the external service’s reported judgment; this application does not know its proprietary features or classification rules. Manuscript Integrity Studio displays external highlights solely as a diagnostic lens to assist authors in reviewing clarity, citations, and empirical evidence.
        </p>
      </div>

      {/* Truncation Warning Alert */}
      {doc.is_truncated && (
        <div className="p-4 bg-red-50/80 dark:bg-red-950/20 border border-red-200 dark:border-red-900/40 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-red-800 dark:text-red-300">
              Detector Character Truncation Detected
            </p>
            <p className="text-red-700/90 dark:text-red-400/90 leading-relaxed">
              The extracted report indicates limited input coverage. Content outside the analyzed scope must not be treated as checked. Consult the extracted report metadata for available character and word counts.
            </p>
          </div>
        </div>
      )}

      {/* Summary Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Report Source</span>
          <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
            {doc.detector_name || (highlights.length > 0 ? highlights[0].detector_name : 'No Report Loaded')}
          </p>
          <span className="text-xs text-zinc-400">Third-party service</span>
        </div>

        <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Detector Score</span>
          <p className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">
            {doc.detector_score != null ? `${doc.detector_score.toFixed(1)}%` : 'N/A'}
          </p>
          <span className="text-xs text-zinc-400">External reported percentage</span>
        </div>

        <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Passages Aligned</span>
          <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {matchedCount} / {highlights.length}
          </p>
          <span className="text-xs text-zinc-400">
            {highlights.length > 0 ? `${Math.round((matchedCount / highlights.length) * 100)}% mapped to DOCX` : '0%'}
          </span>
        </div>

        <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Unmapped Highlights</span>
          <p className="text-xl font-bold text-zinc-700 dark:text-zinc-300 mt-1">
            {unmappedCount}
          </p>
          <span className="text-xs text-zinc-400">Require manual matching</span>
        </div>
      </div>

      {/* Highlights List & Management */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-zinc-50/50 dark:bg-zinc-800/30">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
              Extracted Yellow Highlights ({filteredHighlights.length})
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search highlighted text..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-zinc-400"
              />
            </div>

            <select
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
              className="text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg px-2.5 py-1.5 text-zinc-700 dark:text-zinc-300"
            >
              <option value="all">All Highlights</option>
              <option value="matched">Matched to DOCX</option>
              <option value="unmapped">Unmapped / Low Confidence</option>
            </select>
          </div>
        </div>

        {highlights.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <ShieldAlert className="w-10 h-10 text-zinc-300 dark:text-zinc-700 mx-auto" />
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{doc.detector_name ? 'No text highlights extracted' : 'No Detector PDF Imported'}</h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
              Upload a ZeroGPT or Turnitin PDF export using the button above to extract yellow vector highlights and align them with your manuscript paragraphs.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800 max-h-[600px] overflow-y-auto">
            {filteredHighlights.map((hl) => {
              const mappedBlock = blocks.find(b => b.id === hl.block_id);
              const isMatched = hl.mapping_status === 'matched' || hl.mapping_status === 'manually_corrected';

              return (
                <div key={hl.id} className="p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                        PDF Page {hl.page_number} · {hl.extraction_strategy}
                      </span>
                      {isMatched ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Mapping confidence {Math.round(hl.match_confidence * 100)}%
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border border-zinc-300 dark:border-zinc-700 flex items-center gap-1">
                          <HelpCircle className="w-3 h-3" />
                          Unmapped
                        </span>
                      )}
                      {hl.mapping_status === 'manually_corrected' && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">
                          manual
                        </span>
                      )}
                    </div>

                    <button
                      onClick={() => {
                        setSelectedHighlight(selectedHighlight?.id === hl.id ? null : hl);
                        setTargetBlockId(hl.block_id || '');
                      }}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                    >
                      <Link className="w-3.5 h-3.5" />
                      {selectedHighlight?.id === hl.id ? 'Close Re-map' : 'Re-map to DOCX Block'}
                    </button>
                  </div>

                  {/* Highlight text */}
                  <div className="p-3 bg-amber-50/40 dark:bg-amber-950/20 border-l-4 border-amber-400 text-zinc-800 dark:text-zinc-200 text-xs font-serif leading-relaxed rounded-r-lg">
                    "{hl.highlight_text}"
                  </div>

                  {/* Mapped Block Info */}
                  {mappedBlock && (
                    <div className="text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-2 pl-2">
                      <FileCheck2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                      <span className="font-mono text-[11px] font-medium text-zinc-700 dark:text-zinc-300">
                        {mappedBlock.section_id} ({mappedBlock.id}):
                      </span>
                      <span className="truncate max-w-xl text-zinc-600 dark:text-zinc-400">
                        {mappedBlock.current_text}
                      </span>
                    </div>
                  )}

                  {/* Manual Mapping Selector Interface */}
                  {selectedHighlight?.id === hl.id && (
                    <div className="p-3 bg-zinc-100 dark:bg-zinc-800 rounded-lg space-y-2 text-xs">
                      <label className="font-semibold text-zinc-700 dark:text-zinc-300">
                        Select DOCX Paragraph to Align With:
                      </label>
                      <div className="flex items-center gap-2">
                        <select
                          value={targetBlockId}
                          onChange={e => setTargetBlockId(e.target.value)}
                          className="flex-1 bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2 text-xs text-zinc-800 dark:text-zinc-200"
                        >
                          <option value="">-- Choose Target Paragraph --</option>
                          {blocks.map(b => (
                            <option key={b.id} value={b.id}>
                              [{b.section_id}] {b.current_text.substring(0, 80)}...
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => handleManualMap(hl.id, targetBlockId)}
                          disabled={!targetBlockId}
                          className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:opacity-50 text-xs font-medium"
                        >
                          Confirm Map
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
