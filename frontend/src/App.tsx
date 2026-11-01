import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { api, errorMessage } from './services/api';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { AnalysisProgress } from './components/AnalysisProgress';
import { useStudioStore } from './store/useStudioStore';

// Main Pages
import { HomePage } from './pages/HomePage';
import { DocumentsPage } from './pages/DocumentsPage';
import { NewDocumentWizard } from './pages/NewDocumentWizard';
import { DocumentWorkspace } from './pages/DocumentWorkspace';
import { AccountPage } from './pages/AccountPage';
import { AdminPortal } from './pages/AdminPortal';

const AppLayout: React.FC = () => {
  const { activeDocument } = useStudioStore();
  const [error, setError] = useState('');

  useEffect(() => {
    const onError = (event: Event) => setError((event as CustomEvent<string>).detail);
    const onRejection = (event: PromiseRejectionEvent) => {
      event.preventDefault();
      setError(errorMessage(event.reason));
    };
    window.addEventListener('studio-error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('studio-error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      <Navbar />
      {error && (
        <div
          role="alert"
          className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-xs text-rose-900 flex items-center justify-between gap-4 z-40 sticky top-16"
        >
          <span>{error}</span>
          <button onClick={() => setError('')} className="underline shrink-0 font-medium">
            Dismiss
          </button>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <AnalysisProgress />
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/home" element={<HomePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/new" element={<NewDocumentWizard />} />
            <Route path="/documents/:id" element={<DocumentWorkspace />} />
            <Route path="/documents/:id/:subtab" element={<DocumentWorkspace />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/admin" element={<AdminPortal />} />

            {/* Legacy URL Redirects */}
            <Route path="/dashboard" element={<Navigate to="/" replace />} />
            <Route path="/editor" element={<Navigate to="/documents" replace />} />
            <Route path="/settings" element={<Navigate to="/account" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
};

export default App;
