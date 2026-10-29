import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, AlertCircle, Search } from 'lucide-react';
import { adminService } from '../../services/documentService.js';
import { errorMessage } from '../../services/api.js';

const card = 'rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30';
const same = (a, b) => a.length === b.length && a.every((x) => b.includes(x));

// Admin Console > Tool Access: the ADMIN decides which tools each USER may use.
// ADMIN and MD accounts always have all tools (shown ticked and locked). The backend enforces every permission;
// this screen only edits them (saved through PUT /api/admin/tool-access, ADMIN only).
export default function ToolAccessPanel() {
  const [data, setData] = useState(null);          // { tools: [{slug,label}], users: [...] } as stored on the server
  const [draft, setDraft] = useState({});          // userId -> slugs[] being edited
  const [q, setQ] = useState('');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);      // { ok: boolean, text }

  const load = useCallback(async () => {
    try {
      const d = await adminService.toolAccess();
      setData(d);
      setDraft(Object.fromEntries(d.users.map((u) => [u.id, u.tools])));
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, 'Could not load tool access.') });
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!notice?.ok) return undefined;
    const t = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  const changed = useMemo(
    () => (data ? data.users.filter((u) => u.role === 'USER' && !same(u.tools, draft[u.id] || [])) : []),
    [data, draft],
  );
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.users || []).filter((u) => !needle || u.username.includes(needle) || u.full_name.toLowerCase().includes(needle));
  }, [data, q]);

  const toggle = (u, slug) => {
    setNotice(null);
    setDraft((d) => {
      const cur = d[u.id] || [];
      return { ...d, [u.id]: cur.includes(slug) ? cur.filter((s) => s !== slug) : [...cur, slug] };
    });
  };

  const reset = () => {
    setDraft(Object.fromEntries(data.users.map((u) => [u.id, u.tools])));
    setNotice(null);
  };

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const res = await adminService.saveToolAccess(changed.map((u) => ({ user_id: u.id, tools: draft[u.id] })));
      await load();
      setNotice({ ok: true, text: res.message || 'Tool access saved.' });
    } catch (err) {
      setNotice({ ok: false, text: errorMessage(err, 'Could not save tool access. Nothing was changed.') });
    } finally {
      setSaving(false);
    }
  };

  if (!data) return <div className="text-xs text-slate-400">{notice ? '' : 'Loading…'}{notice && <Banner notice={notice} />}</div>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-slate-500 dark:text-slate-400 max-w-xl">
          Tick the tools each user may use, then press <b>Save Changes</b>. Changes apply immediately, also to users who are signed in.
          ADMIN and MD accounts always have every tool.
        </div>
        <div className="relative">
          <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search user…"
            className="pl-8 pr-3 py-2 rounded-xl bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300" />
        </div>
      </div>

      {notice && <Banner notice={notice} />}

      <div className={`${card} overflow-x-auto`}>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <th className="px-3 py-3 font-semibold">User ID</th>
              <th className="px-3 py-3 font-semibold">Name</th>
              <th className="px-3 py-3 font-semibold">Role</th>
              {data.tools.map((t) => <th key={t.slug} className="px-3 py-3 font-semibold text-center">{t.label}</th>)}
              <th className="px-3 py-3 font-semibold text-center">Assigned</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={4 + data.tools.length} className="px-4 py-10 text-center text-slate-400">No users found.</td></tr>}
            {rows.map((u) => {
              const locked = u.role !== 'USER';
              const sel = locked ? data.tools.map((t) => t.slug) : (draft[u.id] || []);
              const dirty = !locked && !same(u.tools, sel);
              return (
                <tr key={u.id} className={`border-b border-slate-100 dark:border-slate-800/60 last:border-0 ${dirty ? 'bg-amber-50/70 dark:bg-amber-500/5' : ''} ${u.is_active ? '' : 'opacity-60'}`}>
                  <td className="px-3 py-2.5 font-semibold text-slate-900 dark:text-white">{u.username}{!u.is_active && <span className="ml-1 text-[10px] text-slate-400">(inactive)</span>}</td>
                  <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300">{u.full_name}</td>
                  <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300">{u.role}</td>
                  {data.tools.map((t) => (
                    <td key={t.slug} className="px-3 py-2.5 text-center">
                      <input type="checkbox" className="h-4 w-4 accent-purple-600 disabled:opacity-50" checked={sel.includes(t.slug)} disabled={locked || saving}
                        onChange={() => toggle(u, t.slug)} aria-label={`${u.username}: ${t.label}`} title={locked ? 'ADMIN and MD always have all tools' : t.label} />
                    </td>
                  ))}
                  <td className="px-3 py-2.5 text-center text-slate-500 dark:text-slate-400">{locked ? 'All (role)' : `${sel.length} / ${data.tools.length}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className="text-[11px] text-slate-500 dark:text-slate-400">{changed.length ? `${changed.length} user(s) with unsaved changes` : 'No unsaved changes'}</span>
        <button type="button" onClick={reset} disabled={!changed.length || saving}
          className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 disabled:opacity-40 cursor-pointer">Reset</button>
        <button type="button" onClick={save} disabled={!changed.length || saving}
          className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-purple-600 hover:bg-purple-500 shadow-md disabled:opacity-40 cursor-pointer">{saving ? 'Saving…' : 'Save Changes'}</button>
      </div>
    </div>
  );
}

function Banner({ notice }) {
  const ok = notice.ok;
  const Icon = ok ? CheckCircle2 : AlertCircle;
  return (
    <div role={ok ? 'status' : 'alert'} className={`p-3 rounded-xl border text-xs flex items-center gap-2.5 ${ok
      ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/40 text-emerald-800 dark:text-emerald-300'
      : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300'}`}>
      <Icon className="h-4 w-4 shrink-0" /><span>{notice.text}</span>
    </div>
  );
}
