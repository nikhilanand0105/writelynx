import { useEffect, useState } from 'react';
import { Save, ShieldCheck } from 'lucide-react';
import { api, errorMessage } from '../services/api';
import { AppSettings } from '../types';
import { useStudioStore } from '../store/useStudioStore';

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [openaiKey, setOpenaiKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.getSettings().then(setSettings).catch(error => setError(errorMessage(error))); }, []);
  const save = async () => {
    if (!settings) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await api.updateSettings({ ...settings, openai_api_key: openaiKey || undefined, gemini_api_key: geminiKey || undefined });
      setSettings(await api.getSettings());
      setOpenaiKey(''); setGeminiKey('');
      setMessage('Settings saved.'); useStudioStore.getState().triggerRefresh();
    } catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  };
  const test = async () => {
    if (!settings) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.testProvider(settings.default_llm_provider);
      if (result.available) setMessage(`${result.provider}: connection available with saved settings.`);
      else setError(`${result.provider}: connection unavailable. Save your configuration, then retry.`);
    } catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  };
  if (!settings) return <div className="p-8" role="status">{error || 'Loading settings…'}</div>;
  const update = (key: keyof AppSettings, value: string | boolean) => { setSettings({ ...settings, [key]: value }); setMessage(''); };
  const field = (key: 'ollama_host' | 'ollama_model' | 'openai_model' | 'openai_base_url' | 'gemini_model', label: string) => <label className="block text-sm">{label}<input value={String(settings[key] || '')} onChange={event => update(key, event.target.value)} className="block w-full mt-1 p-2 border rounded-lg" /></label>;
  return <div className="p-8 max-w-4xl mx-auto space-y-6">
    <div><h2 className="text-2xl font-bold">Studio Settings</h2><p className="text-sm text-slate-600 mt-1">Choose the editing provider and whether document text may leave this computer.</p></div>
    {error && <p role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800">{error}</p>}
    {message && <p role="status" className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800">{message}</p>}
    <section className="p-6 bg-white border rounded-xl space-y-4">
      <h3 className="font-semibold flex gap-2"><ShieldCheck size={20} /> Privacy boundary</h3>
      <label className="flex gap-3 items-start text-sm"><input type="checkbox" checked={settings.offline_only} onChange={event => update('offline_only', event.target.checked)} className="mt-1" /><span><strong>Local processing only</strong><span className="block text-slate-600 mt-1">Enabled by default. Remote model requests are blocked. Disable only if you authorize sending relevant manuscript passages and evidence to your selected provider.</span></span></label>
      {!settings.offline_only && <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-3">Remote processing is authorized when you save this setting. Review the provider and endpoint before running analysis.</p>}
    </section>
    <section className="p-6 bg-white border rounded-xl space-y-5">
      <label className="block text-sm font-semibold">Language model provider<select className="block mt-2 w-full border rounded-lg p-2 font-normal" value={settings.default_llm_provider} onChange={event => update('default_llm_provider', event.target.value)}>
        <option value="no_llm">No LLM — local rules</option><option value="ollama">Ollama</option><option value="openai">OpenAI-compatible API / custom provider</option><option value="gemini">Gemini API</option>
      </select></label>
      {settings.default_llm_provider === 'no_llm' && <p className="text-sm text-slate-600">Uses deterministic editorial checks. It cannot establish authorship or invent missing research evidence.</p>}
      {settings.default_llm_provider === 'ollama' && <div className="grid gap-4 md:grid-cols-2">{field('ollama_host', 'Ollama host URL')}{field('ollama_model', 'Ollama model')}</div>}
      {settings.default_llm_provider === 'openai' && <div className="space-y-4">{field('openai_base_url', 'OpenAI-compatible endpoint URL')}{field('openai_model', 'Model name')}<label className="block text-sm">API key {settings.has_openai_key && '(already configured)'}<input type="password" autoComplete="new-password" value={openaiKey} onChange={event => setOpenaiKey(event.target.value)} placeholder="Leave blank to keep saved key" className="block w-full mt-1 border rounded-lg p-2" /></label></div>}
      {settings.default_llm_provider === 'gemini' && <div className="space-y-4">{field('gemini_model', 'Gemini model')}<label className="block text-sm">API key {settings.has_gemini_key && '(already configured)'}<input type="password" autoComplete="new-password" value={geminiKey} onChange={event => setGeminiKey(event.target.value)} placeholder="Leave blank to keep saved key" className="block w-full mt-1 border rounded-lg p-2" /></label></div>}
      <div className="flex flex-wrap justify-between gap-3"><button disabled={busy} onClick={test} className="border rounded-lg px-4 py-2 text-sm">Test saved configuration</button><button disabled={busy} onClick={save} className="px-5 py-2 rounded-lg text-white bg-indigo-600 flex items-center gap-2 text-sm"><Save size={16} />{busy ? 'Working…' : 'Save Studio Settings'}</button></div>
    </section>
    <p className="text-sm text-slate-600">PDF conversion: {settings.libreoffice_available ? 'LibreOffice available' : 'LibreOffice unavailable. DOCX export remains available.'}</p>
  </div>;
}
