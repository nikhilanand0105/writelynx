import { useEffect, useRef, useState } from 'react';
import { renderAsync } from 'docx-preview';
import { downloadFile, errorMessage } from '../services/api';

export function OriginalPreview({ documentId }: { documentId: string }) {
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const abort = new AbortController();
    setLoading(true); setError('');
    const render = async () => {
      try {
        const response = await fetch(`/api/documents/${documentId}/original`, { signal: abort.signal });
        if (!response.ok) throw new Error(`Original preview unavailable (${response.status}).`);
        const blob = await response.blob();
        if (container.current && !abort.signal.aborted) await renderAsync(blob, container.current, undefined, { inWrapper: true, ignoreWidth: false, ignoreHeight: false, breakPages: true, useBase64URL: true });
      } catch (error) { if (!abort.signal.aborted) setError(errorMessage(error)); }
      finally { if (!abort.signal.aborted) setLoading(false); }
    };
    void render(); return () => abort.abort();
  }, [documentId]);
  return <div className="space-y-3"><p className="text-xs text-slate-600">Browser approximation of the immutable upload. Some Word fields and layout features may render differently.</p><button onClick={() => downloadFile(`/api/documents/${documentId}/original`)} className="underline text-indigo-700 text-xs">Download original DOCX</button>{loading && <p role="status" className="text-sm">Rendering original document…</p>}{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}<div ref={container} className="overflow-auto max-w-full" /></div>;
}
