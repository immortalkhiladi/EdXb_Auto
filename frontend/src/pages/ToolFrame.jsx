import { useEffect, useRef, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { documentService } from '../services/documentService.js';
import { errorMessage } from '../services/api.js';
import { TOOL_SLUGS, API_BASE_URL } from '../utils/constants.js';

// Hosts a tool UI inside a sandboxed iframe (same-origin so localStorage, nested preview frames, print and downloads work;
// the session cookie is HttpOnly and the tool pages are first-party code).
// When the tool produces a file, the tool page posts it here and THIS component uploads it to the backend
// with the user's session, so every result is stored privately and appears in My Documents.
export default function ToolFrame({ toolId, title }) {
  const slug = TOOL_SLUGS[toolId];
  const frameRef = useRef(null);
  const [jobs, setJobs] = useState([]);
  const { refreshUser } = useAuth();
  const [allowed, setAllowed] = useState(null); // null = checking

  // The admin may have changed this user's tools since sign-in: re-check before showing the tool (the server re-checks anyway).
  useEffect(() => {
    let cancelled = false;
    refreshUser(true).then((u) => { if (!cancelled) setAllowed(!u || u.role !== 'USER' || (u.tools || []).includes(slug)); });
    return () => { cancelled = true; };
  }, [slug, refreshUser]);

  useEffect(() => {
    const update = (id, patch) => setJobs((js) => js.map((j) => (j.id === id ? { ...j, ...patch } : j)));
    const onMessage = async (e) => {
      const m = e.data;
      if (e.source !== frameRef.current?.contentWindow || !m || m.source !== 'ff-tool' || m.tool !== slug) return;
      if (!(m.blob instanceof Blob)) return;
      const id = `${Date.now()}-${Math.random()}`;
      setJobs((js) => [{ id, name: String(m.name || 'output'), state: 'uploading', progress: 0 }, ...js].slice(0, 5));
      try {
        const out = new File([m.blob], String(m.name || 'output'), { type: m.blob.type });
        const orig = m.original instanceof Blob ? new File([m.original], m.original.name || 'input', { type: m.original.type }) : null;
        await documentService.upload(slug, out, orig, (p) => update(id, { progress: p }));
        update(id, { state: 'saved' });
      } catch (err) {
        update(id, { state: 'failed', message: errorMessage(err, 'Could not save this file to your documents.') });
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [slug]);

  if (allowed === false) return <Navigate to="/unauthorized" replace />;
  if (allowed === null) return <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-purple-500" /></div>;

  return (
    <div className="space-y-2">
      {jobs.length > 0 && (
        <div className="rounded-xl ff-card border border-slate-200 dark:border-purple-900/30 p-3 text-xs space-y-1.5">
          {jobs.map((j) => (
            <div key={j.id} className="flex items-center gap-2">
              {j.state === 'uploading' && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
              {j.state === 'saved' && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
              {j.state === 'failed' && <AlertCircle className="h-4 w-4 text-rose-500" />}
              <span className="font-semibold text-slate-800 dark:text-slate-100 truncate">{j.name}</span>
              <span className="text-slate-500 dark:text-slate-400">
                {j.state === 'uploading' && `Saving to My Documents… ${j.progress}%`}
                {j.state === 'saved' && <>Saved to <Link to="/documents" className="underline text-slate-900 dark:text-white">My Documents</Link></>}
                {j.state === 'failed' && j.message}
              </span>
            </div>
          ))}
        </div>
      )}
      <iframe
        ref={frameRef}
        title={title}
        src={`${API_BASE_URL}/tools/${slug}/frame`}
        sandbox="allow-scripts allow-same-origin allow-downloads allow-modals allow-popups allow-forms"
        className="w-full rounded-xl border border-slate-200 dark:border-purple-950/40 bg-white"
        style={{ height: 'calc(100vh - 6rem)', minHeight: 600 }}
      />
    </div>
  );
}
