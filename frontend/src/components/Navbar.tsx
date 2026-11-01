import React, { useEffect, useState } from 'react';
import { ShieldCheck, FileText, Plus, UserCheck, LogIn, LogOut } from 'lucide-react';
import { useStudioStore } from '../store/useStudioStore';
import { api } from '../services/api';

interface UserProfile {
  id: string;
  email: string;
  registration_number?: string;
  full_name?: string;
  active_entitlements_count: number;
}

export const Navbar: React.FC = () => {
  const { activeDocument, setActiveTab } = useStudioStore();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    api.getMe()
      .then((data) => setUser(data))
      .catch(() => setUser(null));

    // Initialize Google Identity Services if available on window
    const win = window as any;
    if (win.google?.accounts?.id) {
      try {
        win.google.accounts.id.initialize({
          client_id: '1092837465-mock.apps.googleusercontent.com',
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

    // Interactive Institutional Login Modal for staging/testing
    const emailPrompt = window.prompt(
      'Sign in with your VIT Student Google Account:\nEnter your institutional email (e.g., 21bce1001@vitstudent.ac.in):',
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
    } catch {
      setUser(null);
    }
  };

  return (
    <header className="h-16 border-b border-slate-200 bg-white px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-indigo-900 flex items-center justify-center text-white shadow-sm">
          <ShieldCheck className="w-5 h-5 text-indigo-400" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-slate-900 tracking-tight text-base">
              Writelynx
            </h1>
            <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
              VIT Student SaaS
            </span>
          </div>
          <p className="text-xs text-slate-500">
            VIT-Exclusive Academic Manuscript Studio & Integrity Verification
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* User Student Authentication Pill */}
        {user ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-50 border border-indigo-100 text-xs">
              <UserCheck className="w-4 h-4 text-indigo-600" />
              <span className="font-medium text-indigo-950 font-mono">
                {user.registration_number || user.email.split('@')[0].toUpperCase()}
              </span>
              <span className="text-indigo-200">|</span>
              <span className="text-indigo-600 bg-indigo-100/80 px-1.5 py-0.5 rounded font-medium">
                {user.active_entitlements_count} slots
              </span>
            </div>
            <button
              onClick={handleSignOut}
              title="Sign Out"
              className="text-slate-400 hover:text-rose-600 p-1 rounded transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={handleSignIn}
            disabled={isLoggingIn}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition shadow-xs"
          >
            <LogIn className="w-3.5 h-3.5 text-indigo-400" />
            <span>{isLoggingIn ? 'Connecting...' : 'Sign In with VIT Google'}</span>
          </button>
        )}

        {/* Active Document Indicator */}
        {activeDocument ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-xs">
            <FileText className="w-4 h-4 text-indigo-600" />
            <span className="font-medium text-slate-800 max-w-[180px] truncate">
              {activeDocument.filename}
            </span>
            <span className="text-slate-400">|</span>
            <span className="text-slate-600">{activeDocument.word_count.toLocaleString()} words</span>
          </div>
        ) : (
          <span className="text-xs text-slate-600 italic">No document selected</span>
        )}

        <button
          onClick={() => setActiveTab('new_analysis')}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium transition shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>New Analysis</span>
        </button>
      </div>
    </header>
  );
};
