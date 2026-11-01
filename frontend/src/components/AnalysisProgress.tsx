import { useEffect, useState } from 'react';
import { api, errorMessage } from '../services/api';
import { useStudioStore } from '../store/useStudioStore';

type Status = Awaited<ReturnType<typeof api.getAnalysisStatus>>;
export function AnalysisProgress() {
  const { activeDocument, triggerRefresh } = useStudioStore();
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!activeDocument || activeDocument.processing_status !== 'analyzing') { setStatus(null); return; }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api.getAnalysisStatus(activeDocument.id);
        if (stopped) return;
        setStatus(next);
        setError('');
        if (next.status !== 'analyzing') {
          const document = await api.getDocument(activeDocument.id);
          if (stopped) return;
          useStudioStore.getState().setActiveDocument(document);
          triggerRefresh();
          if (next.job?.error) setError(next.job.error);
        } else timer = setTimeout(poll, 1500);
      } catch (err) { if (!stopped) { setError(errorMessage(err)); timer = setTimeout(poll, 5000); } }
    };
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [activeDocument?.id, activeDocument?.processing_status, triggerRefresh]);
  if (activeDocument?.processing_status !== 'analyzing' && !error) return null;
  const progress = status?.job?.progress;
  return <section className="mx-4 my-3 p-4 border border-indigo-200 bg-indigo-50 rounded-xl text-sm" aria-live="polite">
    <div className="flex justify-between gap-3"><span>{status?.job?.stage || 'Waiting for analysis status…'}</span>
      {status?.job?.id && <button disabled={busy || status.job.cancel_requested} onClick={async () => { setBusy(true); try { await api.cancelJob(status.job!.id); setStatus({ ...status, job: { ...status.job!, cancel_requested: true } }); } finally { setBusy(false); } }} className="underline">{status.job.cancel_requested ? 'Cancellation requested' : 'Cancel analysis'}</button>}
    </div>
    {typeof progress === 'number' && <progress aria-label="Analysis progress" max={100} value={progress} className="w-full mt-2" />}
    {error && <p role="alert" className="mt-2 text-rose-800">{error}</p>}
  </section>;
}
