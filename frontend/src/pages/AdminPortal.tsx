import React, { useEffect, useState } from 'react';
import {
  ShieldAlert,
  Server,
  Key,
  Cpu,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Lock,
  Layers,
  Activity
} from 'lucide-react';
import { api, errorMessage } from '../services/api';
import { AppSettings } from '../types';

export const AdminPortal: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [openaiKey, setOpenaiKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      api.getMe().catch(() => null),
      api.getSettings().catch(() => null),
      api.getHealth().catch(() => null),
    ])
      .then(([userData, settingsData, healthData]) => {
        if (cancelled) return;
        setUser(userData);
        setSettings(settingsData);
        setHealth(healthData);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api.updateSettings({
        ...settings,
        openai_api_key: openaiKey || undefined,
        gemini_api_key: geminiKey || undefined,
      });
      setSettings(await api.getSettings());
      setOpenaiKey('');
      setGeminiKey('');
      setMessage('Administrative settings saved successfully.');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleTestProvider = async () => {
    if (!settings) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await api.testProvider(settings.default_llm_provider);
      if (result.available) {
        setMessage(`${result.provider}: Connection verified and operational.`);
      } else {
        setError(`${result.provider}: Connection unavailable. Please check endpoint and credentials.`);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-sm text-slate-500">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        Verifying administrator authorization…
      </div>
    );
  }

  // Access check
  if (!user?.is_admin) {
    return (
      <div className="p-12 max-w-lg mx-auto text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
          <Lock className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">Access Restricted</h2>
        <p className="text-xs text-slate-500 leading-relaxed">
          The Admin Portal is restricted to authorized platform administrators. Regular student accounts do not have access to server infrastructure controls.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="pb-6 border-b border-slate-200 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Admin Portal</h1>
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-900 text-white">
              Restricted
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Configure server-wide LLM providers, credentials, FinOps cost controls, and worker health.
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="underline">Dismiss</button>
        </div>
      )}

      {message && (
        <div role="status" className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center justify-between">
          <span>{message}</span>
          <button onClick={() => setMessage('')} className="underline">Dismiss</button>
        </div>
      )}

      {/* System Health Overview */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-xs">
        <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-600" />
          <span>Infrastructure Telemetry</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-400 text-[10px] uppercase font-bold">Backend Status</span>
            <div className="font-bold text-slate-900 mt-1 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>{health?.status || 'Online'}</span>
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-400 text-[10px] uppercase font-bold">LibreOffice Headless</span>
            <div className="font-bold text-slate-900 mt-1">
              {health?.libreoffice ? 'Installed & Ready' : 'Unavailable (DOCX Only)'}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-400 text-[10px] uppercase font-bold">Default Provider</span>
            <div className="font-bold text-slate-900 mt-1 uppercase font-mono">
              {health?.default_provider || 'Local Rules'}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-slate-400 text-[10px] uppercase font-bold">Environment</span>
            <div className="font-bold text-slate-900 mt-1 uppercase font-mono">
              {health?.environment || 'Production'}
            </div>
          </div>
        </div>
      </div>

      {/* LLM Provider Configuration */}
      {settings && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5 shadow-xs">
          <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-indigo-600" />
            <span>AI Provider & Language Model Engine</span>
          </h2>

          <div className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Default Model Provider</label>
              <select
                value={settings.default_llm_provider}
                onChange={(e) => setSettings({ ...settings, default_llm_provider: e.target.value as any })}
                className="w-full border border-slate-200 rounded-lg p-2.5 outline-none focus:border-indigo-500"
              >
                <option value="no_llm">Deterministic Local Rules (Zero API Cost)</option>
                <option value="ollama">Ollama (Self-Hosted Local Instance)</option>
                <option value="openai">OpenAI / OpenAI-Compatible Endpoint</option>
                <option value="gemini">Google Gemini API</option>
              </select>
            </div>

            {settings.default_llm_provider === 'gemini' && (
              <div className="space-y-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Gemini Model</label>
                  <input
                    type="text"
                    value={settings.gemini_model || 'gemini-1.5-flash'}
                    onChange={(e) => setSettings({ ...settings, gemini_model: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Gemini API Key {settings.has_gemini_key && '(Stored in secure environment)'}
                  </label>
                  <input
                    type="password"
                    placeholder="Enter new API key or leave blank to preserve"
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
              </div>
            )}

            {settings.default_llm_provider === 'openai' && (
              <div className="space-y-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Endpoint Base URL</label>
                  <input
                    type="text"
                    value={settings.openai_base_url || 'https://api.openai.com/v1'}
                    onChange={(e) => setSettings({ ...settings, openai_base_url: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Model Name</label>
                  <input
                    type="text"
                    value={settings.openai_model || 'gpt-4o-mini'}
                    onChange={(e) => setSettings({ ...settings, openai_model: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    OpenAI API Key {settings.has_openai_key && '(Stored in secure environment)'}
                  </label>
                  <input
                    type="password"
                    placeholder="Enter new API key or leave blank to preserve"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
              </div>
            )}

            {settings.default_llm_provider === 'ollama' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Ollama Host</label>
                  <input
                    type="text"
                    value={settings.ollama_host || 'http://localhost:11434'}
                    onChange={(e) => setSettings({ ...settings, ollama_host: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Ollama Model</label>
                  <input
                    type="text"
                    value={settings.ollama_model || 'llama3.2'}
                    onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg p-2 bg-white outline-none"
                  />
                </div>
              </div>
            )}

            {/* Offline privacy toggle */}
            <div className="pt-2">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.offline_only}
                  onChange={(e) => setSettings({ ...settings, offline_only: e.target.checked })}
                  className="mt-0.5"
                />
                <div>
                  <span className="font-semibold text-slate-800">Enforce Strict Offline Mode</span>
                  <p className="text-slate-500 text-[11px] mt-0.5">
                    Prohibits any outbound requests to external AI APIs. Analysis will rely exclusively on deterministic linguistic rules.
                  </p>
                </div>
              </label>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-slate-100">
            <button
              disabled={busy}
              onClick={handleTestProvider}
              className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold transition"
            >
              Test Connection
            </button>
            <button
              disabled={busy}
              onClick={handleSave}
              className="flex items-center gap-1.5 px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition"
            >
              <Save size={13} />
              <span>{busy ? 'Saving…' : 'Save Configuration'}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
export default AdminPortal;
