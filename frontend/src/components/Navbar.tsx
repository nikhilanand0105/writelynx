import React, { useEffect, useState } from 'react';
import { ShieldCheck, FileText, Plus, UserCheck, LogIn } from 'lucide-react';
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

  useEffect(() => {
    api.getMe()
      .then((data) => setUser(data))
      .catch(() => setUser(null));
  }, []);

  const handleMockSignIn = async () => {
    const regNo = window.prompt('Enter your VIT Registration Number (e.g., 21BCE1001):', '21BCE1001');
    if (!regNo) return;
    const cleanReg = regNo.trim().toUpperCase();
    try {
      const res = await api.googleLogin(`mock-token:${cleanReg}:${cleanReg.toLowerCase()}@vitstudent.ac.in`);
      setUser(res.user);
    } catch (err: any) {
      alert(err.message || 'Login failed');
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
        ) : (
          <button
            onClick={handleMockSignIn}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition"
          >
            <LogIn className="w-3.5 h-3.5 text-slate-500" />
            <span>VIT Student Sign In</span>
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
