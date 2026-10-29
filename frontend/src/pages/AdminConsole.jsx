import { useCallback, useEffect, useState } from 'react';
import { LayoutDashboard, FileText, Users, ScrollText, SlidersHorizontal } from 'lucide-react';
import DocumentsTable from '../components/documents/DocumentsTable.jsx';
import Modal from '../components/common/Modal.jsx';
import ConfirmDialog from '../components/common/ConfirmDialog.jsx';
import ToolAccessPanel from '../components/admin/ToolAccessPanel.jsx';
import StatusBadge from '../components/common/StatusBadge.jsx';
import { adminService } from '../services/documentService.js';
import { errorMessage } from '../services/api.js';
import { formatDate, formatFileSize } from '../utils/formatters.js';
import { passwordError, PASSWORD_HINT } from '../utils/passwordPolicy.js';

const input = 'px-3 py-2 rounded-xl bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300';
const btn = 'px-3 py-1.5 rounded-lg text-[11px] font-bold cursor-pointer';
const card = 'rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30';

function Overview() {
  const [o, setO] = useState(null);
  useEffect(() => { adminService.overview().then(setO).catch(() => {}); }, []);
  if (!o) return <div className="text-xs text-slate-400">Loading…</div>;
  const tile = (label, value) => (
    <div className={`${card} p-4`}><div className="text-xl font-black text-slate-900 dark:text-white">{value}</div><div className="text-[11px] font-semibold text-slate-500 mt-1">{label}</div></div>
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tile('Active / total users', `${o.users.active} / ${o.users.total}`)}
        {tile('Documents', o.documents.total)}
        {tile('Storage used', formatFileSize(o.storage_bytes))}
        {tile('Failed logins (24h)', o.failed_logins_24h)}
      </div>
      <div className="grid lg:grid-cols-3 gap-3">
        <div className={`${card} p-4 text-xs space-y-2`}>
          <h3 className="font-bold text-slate-900 dark:text-white text-sm">System health</h3>
          {Object.entries(o.health).map(([k, v]) => (
            <div key={k} className="flex justify-between"><span className="capitalize text-slate-600 dark:text-slate-300">{k}</span><StatusBadge status={v === 'ok' ? 'active' : 'error'} /></div>
          ))}
        </div>
        <div className={`${card} p-4 text-xs space-y-1.5`}>
          <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-1">Documents by tool</h3>
          {Object.keys(o.documents.by_tool).length === 0 && <span className="text-slate-400">No documents yet.</span>}
          {Object.entries(o.documents.by_tool).map(([k, v]) => (
            <div key={k} className="flex justify-between text-slate-600 dark:text-slate-300"><span>{k}</span><b>{v}</b></div>
          ))}
        </div>
        <div className={`${card} p-4 text-xs space-y-1.5`}>
          <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-1">Documents by status</h3>
          {Object.entries(o.documents.by_status).map(([k, v]) => (
            <div key={k} className="flex justify-between text-slate-600 dark:text-slate-300"><StatusBadge status={k} /><b>{v}</b></div>
          ))}
        </div>
      </div>
      <div className={`${card} p-4`}>
        <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-2">Recent failed jobs</h3>
        {o.recent_failed_jobs.length === 0 ? <p className="text-xs text-slate-400">None 🎉</p> : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800/70 text-xs">
            {o.recent_failed_jobs.map((d) => (
              <li key={d.id} className="py-2 flex justify-between gap-3">
                <span className="text-slate-700 dark:text-slate-200"><b>{d.owner.username}</b> · {d.tool_label} · {d.output_filename}<br /><span className="text-rose-600 dark:text-rose-400">{d.error_summary}</span></span>
                <span className="text-slate-500 whitespace-nowrap">{formatDate(d.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [msg, setMsg] = useState('');
  const [create, setCreate] = useState(null);
  const [reset, setReset] = useState(null);
  const [del, setDel] = useState(null); // user pending delete confirmation
  const [deleting, setDeleting] = useState(false);
  const load = useCallback(() => adminService.users().then(setUsers).catch((e) => setMsg(errorMessage(e))), []);
  useEffect(() => { load(); }, [load]);

  const act = async (id, body, ok) => {
    setMsg('');
    try { await adminService.updateUser(id, body); setMsg(ok); await load(); }
    catch (e) { setMsg(errorMessage(e)); }
  };
  const confirmDelete = async () => {
    setDeleting(true); setMsg('');
    try { const r = await adminService.deleteUser(del.id); setUsers((list) => list.filter((x) => x.id !== del.id)); setMsg(r?.message || 'User deleted.'); }
    catch (e) { setMsg(errorMessage(e)); }
    finally { setDeleting(false); setDel(null); }
  };
  const submitCreate = async (e) => {
    e.preventDefault();
    const problem = passwordError(create.password);
    if (problem) { setCreate((c) => ({ ...c, error: problem })); return; }
    try { await adminService.createUser(create); setCreate(null); setMsg('User created.'); await load(); }
    catch (err) { setCreate((c) => ({ ...c, error: errorMessage(err) })); }
  };
  const submitReset = async (e) => {
    e.preventDefault();
    const problem = passwordError(reset.password);
    if (problem) { setReset((r) => ({ ...r, error: problem })); return; }
    try { await adminService.updateUser(reset.id, { new_password: reset.password }); setReset(null); setMsg('Password reset. The user was signed out everywhere.'); }
    catch (err) { setReset((r) => ({ ...r, error: errorMessage(err) })); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">{msg}</span>
        <button className={`${btn} text-white ea-primary`} onClick={() => setCreate({ username: '', full_name: '', email: '', password: '', role: 'USER' })}>+ New user</button>
      </div>
      <div className={`${card} overflow-x-auto`}>
        <table className="w-full text-xs">
          <thead><tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200 dark:border-slate-800">
            {['User ID', 'Name', 'Role', 'Status', 'MFA', 'Docs', 'Last login', ''].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 dark:border-slate-800/60 last:border-0">
                <td className="px-4 py-3 font-mono font-semibold text-slate-900 dark:text-white">{u.username}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{u.full_name}<div className="text-[11px] text-slate-400">{u.email}</div></td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{u.role}</td>
                <td className="px-4 py-3"><StatusBadge status={u.locked ? 'locked' : u.is_active ? 'active' : 'inactive'} /></td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{u.mfa_enabled ? 'On' : 'Off'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{u.document_count}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">{formatDate(u.last_login_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1 justify-end">
                    <button className={`${btn} ${u.is_active ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300' : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'}`}
                      onClick={() => act(u.id, { is_active: !u.is_active }, u.is_active ? 'User deactivated.' : 'User activated.')}>{u.is_active ? 'Deactivate' : 'Activate'}</button>
                    <button className={`${btn} bg-rose-600 text-white`} onClick={() => setDel(u)}>Delete</button>
                    <button className={`${btn} bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200`} onClick={() => setReset({ id: u.id, username: u.username, password: '' })}>Reset password</button>
                    {u.locked && <button className={`${btn} bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300`} onClick={() => act(u.id, { unlock: true }, 'Account unlocked.')}>Unlock</button>}
                    {u.mfa_enabled && <button className={`${btn} bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200`} onClick={() => act(u.id, { reset_mfa: true }, 'MFA reset.')}>Reset MFA</button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog isOpen={!!del} onClose={() => !deleting && setDel(null)} onConfirm={confirmDelete} isLoading={deleting}
        title="Delete user" confirmText="Delete"
        message={`Permanently delete ${del?.username}? This also removes their ${del?.document_count || 0} document(s) and cannot be undone.`} />
      <Modal isOpen={!!create} onClose={() => setCreate(null)} title="Create user">
        {create && (
          <form onSubmit={submitCreate} className="space-y-3">
            {[['username', 'User ID (letters, digits, . _ -)'], ['full_name', 'Full name'], ['email', 'Email'], ['password', 'Initial password (4–6 chars: A–Z, 0–9, special)']].map(([k, ph]) => (
              <input key={k} required type={k === 'password' ? 'password' : 'text'} autoComplete="off" placeholder={ph} value={create[k]} onChange={(e) => setCreate({ ...create, [k]: e.target.value })} className={`${input} w-full`} />
            ))}
            <select value={create.role} onChange={(e) => setCreate({ ...create, role: e.target.value })} className={`${input} w-full`}><option value="USER">USER</option><option value="MD">MD</option><option value="ADMIN">ADMIN</option></select>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">{PASSWORD_HINT}</p>
            {create.error && <div className="text-xs text-rose-600">{create.error}</div>}
            <button className={`${btn} w-full py-2.5 text-white ea-primary`}>Create</button>
          </form>
        )}
      </Modal>
      <Modal isOpen={!!reset} onClose={() => setReset(null)} title={`Reset password · ${reset?.username}`}>
        {reset && (
          <form onSubmit={submitReset} className="space-y-3">
            <input required type="password" autoComplete="new-password" placeholder="New password" value={reset.password} onChange={(e) => setReset({ ...reset, password: e.target.value })} className={`${input} w-full`} />
            <p className="text-[11px] text-slate-500 dark:text-slate-400">{PASSWORD_HINT}</p>
            {reset.error && <div className="text-xs text-rose-600">{reset.error}</div>}
            <button className={`${btn} w-full py-2.5 text-white ea-primary`}>Reset password</button>
          </form>
        )}
      </Modal>
    </div>
  );
}

function AuditTab() {
  const [f, setF] = useState({ actor: '', action: '', outcome: '' });
  const [applied, setApplied] = useState(f);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0 });
  useEffect(() => { adminService.auditLogs({ ...applied, page, page_size: 25 }).then(setData).catch(() => {}); }, [applied, page]);
  const pages = Math.max(1, Math.ceil(data.total / 25));
  return (
    <div className="space-y-3">
      <form onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(f); }} className="flex flex-wrap gap-2">
        <input className={`${input} w-40`} placeholder="Actor (user ID)" value={f.actor} onChange={(e) => setF({ ...f, actor: e.target.value })} />
        <input className={`${input} w-48`} placeholder="Action prefix (e.g. auth.)" value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} />
        <select className={input} value={f.outcome} onChange={(e) => setF({ ...f, outcome: e.target.value })}><option value="">Any outcome</option><option value="success">success</option><option value="failure">failure</option><option value="denied">denied</option></select>
        <button className={`${btn} text-white ea-primary`}>Apply</button>
      </form>
      <div className={`${card} overflow-x-auto`}>
        <table className="w-full text-xs">
          <thead><tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200 dark:border-slate-800">
            {['Time', 'Actor', 'Action', 'Resource', 'Outcome', 'IP', 'Detail'].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {data.items.map((r) => (
              <tr key={r.id} className="border-b border-slate-100 dark:border-slate-800/60 last:border-0 align-top text-slate-600 dark:text-slate-300">
                <td className="px-4 py-2.5 whitespace-nowrap">{formatDate(r.created_at)}</td>
                <td className="px-4 py-2.5 font-mono">{r.actor || '—'}</td>
                <td className="px-4 py-2.5 font-semibold text-slate-900 dark:text-white">{r.action}</td>
                <td className="px-4 py-2.5 font-mono text-[11px]">{r.resource_type ? `${r.resource_type}:${(r.resource_id || '').slice(0, 8)}` : '—'}</td>
                <td className="px-4 py-2.5"><StatusBadge status={r.outcome === 'success' ? 'completed' : 'failed'} /></td>
                <td className="px-4 py-2.5">{r.ip}</td>
                <td className="px-4 py-2.5 max-w-[260px]">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{data.total} events</span>
        <div className="flex items-center gap-2">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)} className={`${btn} bg-slate-100 dark:bg-slate-800 disabled:opacity-40`}>Prev</button>
          <span>Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)} className={`${btn} bg-slate-100 dark:bg-slate-800 disabled:opacity-40`}>Next</button>
        </div>
      </div>
    </div>
  );
}

const TABS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'documents', label: 'All Documents', icon: FileText },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'tools', label: 'Tool Access', icon: SlidersHorizontal },
  { id: 'audit', label: 'Audit Log', icon: ScrollText },
];

export default function AdminConsole() {
  const [tab, setTab] = useState('overview');
  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">Admin Console</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Every action here is performed through admin-only APIs and recorded in the audit log.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${tab === id ? 'bg-purple-600 text-white shadow-md shadow-purple-900/30' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60'}`}>
            <Icon className="h-4 w-4" />{label}
          </button>
        ))}
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'documents' && <DocumentsTable admin />}
      {tab === 'users' && <UsersTab />}
      {tab === 'tools' && <ToolAccessPanel />}
      {tab === 'audit' && <AuditTab />}
    </div>
  );
}
