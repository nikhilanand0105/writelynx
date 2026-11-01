import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  Home,
  FileText,
  User,
  Plus,
  Sparkles,
  Layers,
  History,
  ShieldCheck,
  ShieldAlert,
  HelpCircle,
  LogOut,
  ArrowLeft
} from 'lucide-react';
import { useStudioStore, WorkspaceTab } from '../store/useStudioStore';
import { api } from '../services/api';

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    activeDocument,
    workspaceTab,
    setWorkspaceTab,
  } = useStudioStore();
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    api.getMe()
      .then((data) => setUser(data))
      .catch(() => setUser(null));
  }, []);

  const path = location.pathname;
  const isDocumentWorkspace =
    path.startsWith('/documents/') && path !== '/documents/new';

  return (
    <aside className="w-64 border-r border-slate-200 bg-white flex flex-col justify-between h-[calc(100vh-4rem)] sticky top-16 select-none shrink-0 overflow-y-auto">
      <div className="p-4 space-y-6">
        {/* Prominent Primary Action: NEW DOCUMENT */}
        <div>
          <button
            onClick={() => navigate('/documents/new')}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-xs transition"
          >
            <Plus className="w-4 h-4" />
            <span>New Document</span>
          </button>
        </div>

        {/* Primary Student Navigation (At most 3 items) */}
        <div className="space-y-1">
          <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Navigation
          </div>

          <Link
            to="/"
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
              path === '/' || path === '/home'
                ? 'bg-indigo-50 text-indigo-900 font-semibold'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <Home
              className={`w-4 h-4 ${
                path === '/' || path === '/home' ? 'text-indigo-600' : 'text-slate-400'
              }`}
            />
            <span>Home</span>
          </Link>

          <Link
            to="/documents"
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
              path === '/documents'
                ? 'bg-indigo-50 text-indigo-900 font-semibold'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <FileText
              className={`w-4 h-4 ${
                path === '/documents' ? 'text-indigo-600' : 'text-slate-400'
              }`}
            />
            <span>My Documents</span>
          </Link>

          <Link
            to="/account"
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
              path === '/account'
                ? 'bg-indigo-50 text-indigo-900 font-semibold'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <User
              className={`w-4 h-4 ${
                path === '/account' ? 'text-indigo-600' : 'text-slate-400'
              }`}
            />
            <span>Account</span>
          </Link>
        </div>

        {/* Contextual Document Workspace Navigation (Only visible when document is open) */}
        {isDocumentWorkspace && activeDocument && (
          <div className="pt-4 border-t border-slate-100 space-y-1">
            <div className="px-3 py-1 flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Workspace
              </span>
              <button
                onClick={() => navigate('/documents')}
                className="text-[10px] text-indigo-600 hover:underline flex items-center gap-0.5"
              >
                <ArrowLeft className="w-2.5 h-2.5" />
                <span>All docs</span>
              </button>
            </div>

            <div className="px-3 py-1.5 text-xs font-semibold text-slate-800 truncate" title={activeDocument.filename}>
              {activeDocument.filename}
            </div>

            <button
              onClick={() => {
                setWorkspaceTab('review');
                navigate(`/documents/${activeDocument.id}`);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition ${
                workspaceTab === 'review'
                  ? 'bg-slate-900 text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>Review</span>
            </button>

            <button
              onClick={() => {
                setWorkspaceTab('checks');
                navigate(`/documents/${activeDocument.id}`);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition ${
                workspaceTab === 'checks'
                  ? 'bg-slate-900 text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Sources & Checks</span>
            </button>

            <button
              onClick={() => {
                setWorkspaceTab('history');
                navigate(`/documents/${activeDocument.id}`);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition ${
                workspaceTab === 'history'
                  ? 'bg-slate-900 text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <History className="w-4 h-4 text-indigo-400" />
              <span>History</span>
            </button>
          </div>
        )}
      </div>

      {/* Bottom Footer Area */}
      <div className="p-4 border-t border-slate-100 space-y-3">
        {/* Protected Admin Portal Link (Only for admins) */}
        {user?.is_admin && (
          <Link
            to="/admin"
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition ${
              path === '/admin'
                ? 'bg-slate-900 text-white'
                : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            <span>Admin Portal</span>
          </Link>
        )}

        {/* Student Support */}
        <div className="text-[11px] text-slate-400 px-3">
          VIT Academic Studio · v1.0
        </div>
      </div>
    </aside>
  );
};
export default Sidebar;
