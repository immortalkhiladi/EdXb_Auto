import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileStack, FileCode2, GitCompare, BookOpenCheck, FileText, CheckCircle2, AlertTriangle, ShieldCheck, Users, HardDrive } from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import { documentService, adminService } from '../services/documentService.js';
import StatusBadge from '../components/common/StatusBadge.jsx';
import { formatDate, formatFileSize } from '../utils/formatters.js';

const TOOLS = [
  { page: 'redline', name: 'Redline to GoFiler HTML', path: '/redline-gofiler', icon: GitCompare, desc: 'Apply Word redlines to GoFiler HTML.' },
  { page: 'gofilerhtml', name: 'GoFiler HTML Converter', path: '/html-converter', icon: FileCode2, desc: 'Convert Word documents to GoFiler HTML.' },
  { page: 'converter', name: 'PPT & PDF Converter', path: '/converter', icon: FileStack, desc: 'Convert slides and PDFs for EDGAR.' },
  { page: 'secforms', name: 'SEC Form Type Dashboard', path: '/sec-forms', icon: BookOpenCheck, desc: 'Form reference, comparisons and filing checks.' },
];

function Stat({ icon: Icon, label, value, tone = 'purple' }) {
  const tones = {
    purple: 'text-purple-600 bg-purple-50 dark:bg-purple-500/10 dark:text-purple-300',
    green: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10 dark:text-emerald-300',
    rose: 'text-rose-600 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-300',
  };
  return (
    <div className="p-4 rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30 flex items-center gap-3">
      <div className={`p-2.5 rounded-xl ${tones[tone]}`}><Icon className="h-5 w-5" /></div>
      <div>
        <div className="text-xl font-black text-slate-900 dark:text-white leading-none">{value}</div>
        <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 mt-1">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, hasRole, hasAccess } = useAuth();
  const myTools = TOOLS.filter((t) => hasAccess(t.page)); // only the tools this account may use
  const [counts, setCounts] = useState({ total: 0, completed: 0, failed: 0 });
  const [recent, setRecent] = useState([]);
  const [overview, setOverview] = useState(null);

  // Depends on the account and role only: `hasRole` is a new function on every AuthProvider render, which re-sent these
  // 3-4 requests each time the user switched back to the tab.
  const isAdmin = hasRole('ADMIN');
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [all, ok, bad] = await Promise.all([
          documentService.list({ page_size: 5 }),
          documentService.list({ status: 'completed', page_size: 1 }),
          documentService.list({ status: 'failed', page_size: 1 }),
        ]);
        if (cancelled) return;
        setRecent(all.items);
        setCounts({ total: all.total, completed: ok.total, failed: bad.total });
        if (isAdmin) {
          const o = await adminService.overview();
          if (!cancelled) setOverview(o);
        }
      } catch { /* the global handler deals with expired sessions */ }
    })();
    return () => { cancelled = true; };
  }, [user?.id, isAdmin]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
          Welcome{user?.full_name ? `, ${user.full_name}` : ''}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Your filing workspace. Pick a tool to start; every result is saved to My Documents.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat icon={FileText} label="My documents" value={counts.total} />
        <Stat icon={CheckCircle2} label="Completed" value={counts.completed} tone="green" />
        <Stat icon={AlertTriangle} label="Failed" value={counts.failed} tone="rose" />
        <Stat icon={ShieldCheck} label="Signed in as" value={user?.username} />
      </div>

      {overview && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Administration</h2>
            <Link to="/admin" className="text-xs font-bold text-slate-900 dark:text-white hover:underline">Open Admin Console →</Link>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat icon={Users} label="Active users" value={`${overview.users.active} / ${overview.users.total}`} />
            <Stat icon={FileText} label="All documents" value={overview.documents.total} />
            <Stat icon={HardDrive} label="Storage used" value={formatFileSize(overview.storage_bytes)} />
            <Stat icon={AlertTriangle} label="Failed logins (24h)" value={overview.failed_logins_24h} tone={overview.failed_logins_24h ? 'rose' : 'green'} />
          </div>
        </div>
      )}

      {myTools.length === 0 && (
        <div className="p-4 rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30 text-sm text-slate-500 dark:text-slate-400">
          No tools have been assigned to your account yet. Please contact your administrator.
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {myTools.map(({ name, path, icon: Icon, desc }) => (
          <Link key={path} to={path} className="p-4 rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30 hover:border-slate-900 dark:hover:border-slate-300 transition-colors group">
            <Icon className="h-6 w-6 text-purple-600 dark:text-purple-400 transition-colors" />
            <div className="mt-3 text-sm font-bold text-slate-900 dark:text-white">{name}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{desc}</div>
          </Link>
        ))}
      </div>

      <div className="rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">Recent documents</h2>
          <Link to="/documents" className="text-xs font-bold text-slate-900 dark:text-white hover:underline">View all →</Link>
        </div>
        {recent.length === 0 ? (
          <p className="text-xs text-slate-400 py-6 text-center">No documents yet. Run one of the tools above.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800/70">
            {recent.map((d) => (
              <li key={d.id} className="py-2.5 flex items-center justify-between gap-3 text-xs">
                <div className="min-w-0">
                  <div className="font-semibold text-slate-900 dark:text-white truncate">{d.document_name}</div>
                  <div className="text-slate-500 dark:text-slate-400">{d.tool_label} · {formatDate(d.created_at)}</div>
                </div>
                <StatusBadge status={d.status} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
