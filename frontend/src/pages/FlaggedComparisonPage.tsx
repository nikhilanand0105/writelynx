import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { DocumentItem, FlaggedVsUnflaggedResponse } from '../types';
import {
  AlertTriangle,
  Info,
  RefreshCw,
  Scale,
  Sparkles,
  } from 'lucide-react';

interface Props {
  document: DocumentItem | null;
}

export const FlaggedComparisonPage: React.FC<Props> = ({ document: doc }) => {
  const [data, setData] = useState<FlaggedVsUnflaggedResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!doc) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getFlaggedVsUnflaggedComparison(doc.id);
      setData(res);
    } catch (e: any) {
      setError(e.message || 'Failed to compute flagged vs. unflagged comparison');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [doc?.id]);

  if (!doc) {
    return (
      <div className="p-8 text-center text-zinc-500">
        Please select a document from the dashboard to review descriptive metrics.
      </div>
    );
  }

  const flagged = data?.highlighted_passages;
  const unflagged = data?.unhighlighted_passages;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {error && <p role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-800">{error}</p>}
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <Scale className="w-6 h-6 text-indigo-500" />
            Flagged vs. Unflagged Descriptive Comparison
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Empirical comparative analysis between external detector-highlighted passages and baseline manuscript text.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="p-2 border border-zinc-300 dark:border-zinc-700 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-zinc-600 dark:text-zinc-300 self-start md:self-auto"
          title="Refresh Metrics"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Mandatory Transparent Disclaimer */}
      <div className="p-5 bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-300 dark:border-zinc-700 rounded-xl space-y-2">
        <div className="flex items-center gap-2 text-zinc-900 dark:text-zinc-100 font-semibold text-sm">
          <Info className="w-4 h-4 text-blue-500 flex-shrink-0" />
          <span>Scope of this comparison</span>
        </div>
        <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
          {data?.disclaimer ||
            "Descriptive comparisons reflect observable stylistic metrics only. Observable writing characteristics do not prove AI authorship. Differences may reflect section genre, formulaic academic structure, or technical domain vocabulary."}
        </p>
      </div>

      <p className="text-xs text-slate-600">Other manuscript text may include passages outside the external report’s coverage. Absence of an imported highlight does not mean the detector checked or cleared a passage.</p>
      {/* Sample Size Warning */}
      {data?.sample_size_warning && (
        <div className="p-4 bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-amber-800 dark:text-amber-300">
              Sample Size Limitation
            </p>
            <p className="text-amber-700/90 dark:text-amber-400/90 leading-relaxed">
              {data.sample_size_warning}
            </p>
          </div>
        </div>
      )}

      {loading && (
        <div className="p-12 text-center text-zinc-500">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-indigo-500" />
          Computing computational linguistic metrics...
        </div>
      )}

      {!loading && data && (
        <>
          {/* Side by side comparison table */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                Descriptive Statistical Contrast
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50 text-zinc-600 dark:text-zinc-400">
                    <th className="p-3.5 font-semibold">Linguistic Property</th>
                    <th className="p-3.5 font-semibold text-amber-600 dark:text-amber-400">
                      External Flagged ({data.detector_name})
                    </th>
                    <th className="p-3.5 font-semibold text-zinc-700 dark:text-zinc-300">
                      Other Manuscript Text
                    </th>
                    <th className="p-3.5 font-semibold text-zinc-500">Observation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Evaluated Passages</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.passage_count || 0}
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.passage_count || 0}
                    </td>
                    <td className="p-3.5 text-zinc-500">Total document block distribution</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Total Word Count</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.word_count || 0}
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.word_count || 0}
                    </td>
                    <td className="p-3.5 text-zinc-500">Evaluated token volume</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Avg Sentence Length</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.avg_sentence_length_words.toFixed(1)} words
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.avg_sentence_length_words.toFixed(1)} words
                    </td>
                    <td className="p-3.5 text-zinc-500">Syntactic complexity index</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Technical Term Density</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.technical_term_density_pct.toFixed(1)}%
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.technical_term_density_pct.toFixed(1)}%
                    </td>
                    <td className="p-3.5 text-zinc-500">Domain-specific jargon vs vocabulary</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Citation Presence</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.citation_presence_pct.toFixed(1)}%
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.citation_presence_pct.toFixed(1)}%
                    </td>
                    <td className="p-3.5 text-zinc-500">Percentage of sentences with citations</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Readability Grade (Flesch-Kincaid)</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.readability_fk_grade.toFixed(1)}
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.readability_fk_grade.toFixed(1)}
                    </td>
                    <td className="p-3.5 text-zinc-500">Academic graduate reading level</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Enumerated / List Items</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.enumerated_items_count || 0}
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.enumerated_items_count || 0}
                    </td>
                    <td className="p-3.5 text-zinc-500">Structured ordinal markers</td>
                  </tr>

                  <tr>
                    <td className="p-3.5 font-medium text-zinc-900 dark:text-zinc-100">Unsupported Assertions</td>
                    <td className="p-3.5 font-mono font-semibold text-amber-600 dark:text-amber-400">
                      {flagged?.unsupported_assertions_count || 0}
                    </td>
                    <td className="p-3.5 font-mono text-zinc-700 dark:text-zinc-300">
                      {unflagged?.unsupported_assertions_count || 0}
                    </td>
                    <td className="p-3.5 text-zinc-500">Claims lacking citations or empirical evidence</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Observable Correlations Section */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm space-y-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-500" />
              Observable Diagnostic Insights
            </h3>

            {data.observable_correlations && data.observable_correlations.length > 0 ? (
              <ul className="space-y-2.5">
                {data.observable_correlations.map((corr, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-500 mt-1.5 flex-shrink-0" />
                    <span>{corr}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-zinc-500">
                No descriptive differences were reported. This is not a statistical significance test.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
};
