import React, { useEffect, useState } from 'react';
import { api, errorMessage } from './services/api';
import { AnalysisProgress } from './components/AnalysisProgress';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { useStudioStore } from './store/useStudioStore';
import { DashboardPage } from './pages/DashboardPage';
import { NewAnalysisPage } from './pages/NewAnalysisPage';
import { EditorPage } from './pages/EditorPage';
import { DetectorHighlightsPage } from './pages/DetectorHighlightsPage';
import { ReportComparisonPage } from './pages/ReportComparisonPage';
import { FlaggedComparisonPage } from './pages/FlaggedComparisonPage';
import { EvidenceReviewPage } from './pages/EvidenceReviewPage';
import { OverlapReviewPage } from './pages/OverlapReviewPage';
import { CitationReviewPage } from './pages/CitationReviewPage';
import { WritingQualityPage } from './pages/WritingQualityPage';
import { RevisionHistoryPage } from './pages/RevisionHistoryPage';
import { ExportCenterPage } from './pages/ExportCenterPage';
import { SettingsPage } from './pages/SettingsPage';

export const App: React.FC = () => {
  const { activeTab, activeDocument, triggerRefresh } = useStudioStore();

  const [error, setError] = useState('');
  useEffect(() => {
    const onError = (event: Event) => setError((event as CustomEvent<string>).detail);
    const onRejection = (event: PromiseRejectionEvent) => { event.preventDefault(); setError(errorMessage(event.reason)); };
    window.addEventListener('studio-error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => { window.removeEventListener('studio-error', onError); window.removeEventListener('unhandledrejection', onRejection); };
  }, []);
  useEffect(() => {
    const id = activeDocument?.id;
    if (id) api.getDocument(id).then(doc => {
      if (useStudioStore.getState().activeDocumentId === id) useStudioStore.getState().setActiveDocument(doc);
    }).catch(() => {});
  }, [useStudioStore(state => state.refreshTrigger)]);

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardPage />;
      case 'new_analysis':
        return <NewAnalysisPage />;
      case 'editor':
        return <EditorPage />;
      case 'detector_highlights':
        return <DetectorHighlightsPage document={activeDocument} onRefreshDocument={triggerRefresh} />;
      case 'report_comparison':
        return <ReportComparisonPage document={activeDocument} />;
      case 'flagged_comparison':
        return <FlaggedComparisonPage document={activeDocument} />;
      case 'evidence':
        return <EvidenceReviewPage document={activeDocument} />;
      case 'overlap':
        return <OverlapReviewPage />;
      case 'citation':
        return <CitationReviewPage />;
      case 'quality':
        return <WritingQualityPage />;
      case 'revisions':
        return <RevisionHistoryPage />;
      case 'export':
        return <ExportCenterPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      <Navbar />
      {error && <div role="alert" className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-sm text-rose-900 flex items-center justify-between gap-4"><span>{error}</span><button onClick={() => setError('')} className="underline shrink-0">Dismiss</button></div>}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main key={activeDocument?.id} className="flex-1 min-w-0 overflow-y-auto">
          <AnalysisProgress />
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
