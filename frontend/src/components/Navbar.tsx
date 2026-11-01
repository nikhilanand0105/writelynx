import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  FileText,
  Plus,
  UserCheck,
  LogIn,
  LogOut,
  ChevronRight,
  Download
} from 'lucide-react';
import { useStudioStore } from '../store/useStudioStore';
import { api, downloadFile } from '../services/api';

interface UserProfile {
  id: string;
  email: string;
  registration_number?: string;
  full_name?: string;
  is_admin?: boolean;
  active_entitlements_count: number;
}

export const Navbar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { activeDocument } = useStudioStore();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    api.getMe()
      .then((data) => setUser(data))
      .catch(() => setUser(null));

    // Initialize Google Identity Services if available on window
    const win = window as any;
    const googleClientId =
      import.meta.env.VITE_GOOGLE_CLIENT_ID || '1092837465-mock.apps.googleusercontent.com';

    if (win.google?.accounts?.id) {
      try {
        win.google.accounts.id.initialize({
          client_id: googleClientId,
          hosted_domain: 'vitstudent.ac.in',
          callback: async (response: any) => {
            if (response.credential) {
              try {
                setIsLoggingIn(true);
                const res = await api.googleLogin(response.credential);
                setUser(res.user);
              } catch (err: any) {
                alert(err.message || 'Google authentication failed.');
              } finally {
                setIsLoggingIn(false);
              }
            }
          },
        });
      } catch (e) {
        console.warn('Google GSI initialization notice:', e);
      }
    }
  }, []);

  const handleSignIn = async () => {
    const win = window as any;
    if (win.google?.accounts?.id) {
      win.google.accounts.id.prompt();
      return;
    }

    const isDevMockAllowed =
      import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCK_AUTH === 'true';

    if (!isDevMockAllowed) {
      alert(
        'Google Sign-In is initializing or blocked by an ad-blocker. Please ensure Google scripts are allowed and you are signed into your official VIT Google account (@vitstudent.ac.in).'
      );
      return;
    }

    // Dev/Test Mock Institutional Login Prompt
    const emailPrompt = window.prompt(
      'Sign in with your VIT Student Google Account (Test Mode):\nEnter your institutional email (e.g., 21bce1001@vitstudent.ac.in):',
      '21bce1001@vitstudent.ac.in'
    );
    if (!emailPrompt) return;
    const cleanEmail = emailPrompt.trim().toLowerCase();
    if (!cleanEmail.endsWith('@vitstudent.ac.in')) {
      alert('Access Restricted: You must use an official @vitstudent.ac.in email address.');
      return;
    }

    try {
      setIsLoggingIn(true);
      const res = await api.googleLogin(`mock-token:${cleanEmail}`);
      setUser(res.user);
    } catch (err: any) {
      alert(err.message || 'Sign in failed.');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await api.logout();
      setUser(null);
      navigate('/');
    } catch {
      setUser(null);
      navigate('/');
    }
  };

  const path = location.pathname;
  const isDocumentWorkspace = path.startsWith('/documents/') && path !== '/documents/new';

  return (
    <header className="h-16 border-b border-slate-200 bg-white px-4 md:px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Brand & Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <Link to="/" className="flex items-center gap-2.5 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-indigo-950 flex items-center justify-center text-white shadow-xs">
            <ShieldCheck className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-slate-900 tracking-tight text-base">
                Writelynx
              </span>
              <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                VIT
              </span>
            </div>
          </div>
        </Link>

        {/* Dynamic Breadcrumbs */}
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400 pl-3 border-l border-slate-200 min-w-0">
          {path === '/' || path === '/home' ? (
            <span className="text-slate-600 font-medium">Home</span>
          ) : path === '/documents' ? (
            <span className="text-slate-600 font-medium">My Documents</span>
          ) : path === '/documents/new' ? (
            <>
              <Link to="/documents" className="hover:text-slate-700">My Documents</Link>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span className="text-slate-600 font-medium">New Document</span>
            </>
          ) : isDocumentWorkspace && activeDocument ? (
            <>
              <Link to="/documents" className="hover:text-slate-700">My Documents</Link>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span className="text-slate-700 font-medium truncate max-w-[200px]">
                {activeDocument.filename}
              </span>
            </>
          ) : path === '/account' ? (
            <span className="text-slate-600 font-medium">Account</span>
          ) : path === '/admin' ? (
            <span className="text-slate-600 font-medium">Admin Portal</span>
          ) : null}
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3 shrink-0">
        {/* User Student Authentication Pill */}
        {user ? (
          <div className="flex items-center gap-2">
            <Link
              to="/account"
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100/70 border border-indigo-100 text-xs transition"
            >
              <UserCheck className="w-4 h-4 text-indigo-600" />
              <span className="font-bold text-indigo-950 font-mono text-[11px]">
                {user.registration_number || user.email.split('@')[0].toUpperCase()}
              </span>
              <span className="text-indigo-200">|</span>
              <span className="text-indigo-600 bg-indigo-100/80 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                {user.active_entitlements_count} slots
              </span>
            </Link>
            <button
              onClick={handleSignOut}
              title="Sign Out"
              className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={handleSignIn}
            disabled={isLoggingIn}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition shadow-xs"
          >
            <LogIn className="w-3.5 h-3.5 text-indigo-400" />
            <span>{isLoggingIn ? 'Connecting...' : 'Sign In with VIT Google'}</span>
          </button>
        )}

        {/* Global New Document CTA (when not on /documents/new) */}
        {path !== '/documents/new' && (
          <button
            onClick={() => navigate('/documents/new')}
            className="hidden sm:flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Document</span>
          </button>
        )}
      </div>
    </header>
  );
};
export default Navbar;
