import { useCallback, useEffect, useRef, useState } from 'react';
import { Search, Eye, Download, Trash2, ChevronLeft, ChevronRight, FileText, X } from 'lucide-react';
import StatusBadge from '../common/StatusBadge.jsx';
import ConfirmDialog from '../common/ConfirmDialog.jsx';
import Modal from '../common/Modal.jsx';
import { documentService } from '../../services/documentService.js';
import { errorMessage } from '../../services/api.js';
import { formatDate, formatFileSize } from '../../utils/formatters.js';
import { useAuth } from '../../context/AuthContext.jsx';

const input =
  'px-3 py-2 rounded-xl bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300';
const PAGE_SIZE = 10;
const th = 'px-2 xl:px-3 py-3 font-semibold';
const td = 'px-2 xl:px-3 py-2.5';
// Column widths in % (each set adds up to 100). Order: Document, [Owner], Tool, Original, Output, Type·Size, Processed, Status, Actions.
const COLS_USER = [15, 12, 15, 15, 10, 12, 11, 10];
const COLS_ALL = [13, 8, 11, 13, 13, 9, 11, 11, 11];

// admin=false: "My Documents" (server returns only the caller's files).
// admin=true : every user's documents, with a User filter (server enforces the ADMIN / MD role).
export default function DocumentsTable({ admin = false }) {
  const { hasRole } = useAuth();
  // Own documents can always be deleted; in the all-users view only ADMIN may delete (MD is view/download only; the API enforces it too).
  const canDelete = !admin || hasRole('ADMIN');
  const cols = admin ? COLS_ALL : COLS_USER;
  const colCount = cols.length;
  const [filters, setFilters] = useState({ q: '', tool: '', status: '', user: '', date_from: '', date_to: '' });
  const [applied, setApplied] = useState(filters);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, tools: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [preview, setPreview] = useState(null);

  const reqId = useRef(0); // only the newest request may update the table (responses can arrive out of order)
  const load = useCallback(async () => {
    const id = ++reqId.current;
    setLoading(true);
    setError('');
    try {
      const d = await documentService.list({ ...applied, page, page_size: PAGE_SIZE }, admin);
      if (id === reqId.current) setData(d);
    } catch (err) {
      if (id === reqId.current) setError(errorMessage(err, 'Unable to load documents.'));
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }, [applied, page, admin]);

  useEffect(() => { load(); }, [load]);

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));
  const apply = (e) => { e?.preventDefault(); setPage(1); setApplied(filters); };
  const reset = () => {
    const empty = { q: '', tool: '', status: '', user: '', date_from: '', date_to: '' };
    setFilters(empty); setApplied(empty); setPage(1);
  };
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  // e.g. the last row of the last page was deleted: go back to the last page that still exists
  useEffect(() => { if (!loading && page > pages) setPage(pages); }, [loading, page, pages]);

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await documentService.remove(toDelete.id);
      setToDelete(null);
      await load();
    } catch (err) {
      setError(errorMessage(err, 'Delete failed.'));
      setToDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const previewable = (d) => d.has_output && ['pdf', 'htm', 'html', 'xml', 'txt', 'csv', 'zip'].includes(d.file_type);

  return (
    <div className="space-y-4">
      <form onSubmit={apply} className="flex flex-wrap items-end gap-2">
        <div className="relative">
          <Search className="h-4 w-4 absolute left-3 top-2.5 text-slate-400" />
          <input value={filters.q} onChange={set('q')} placeholder="Search file name…" className={`${input} pl-9 w-56`} />
        </div>
        <select value={filters.tool} onChange={set('tool')} className={input}>
          <option value="">All tools</option>
          {Object.entries(data.tools || {}).map(([slug, label]) => <option key={slug} value={slug}>{label}</option>)}
        </select>
        <select value={filters.status} onChange={set('status')} className={input}>
          <option value="">All statuses</option>
          <option value="completed">Completed</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
        {admin && <input value={filters.user} onChange={set('user')} placeholder="User ID (e.g. user01)" className={`${input} w-40`} />}
        <label className="text-[11px] text-slate-500">From <input type="date" value={filters.date_from} onChange={set('date_from')} className={input} /></label>
        <label className="text-[11px] text-slate-500">To <input type="date" value={filters.date_to} onChange={set('date_to')} className={input} /></label>
        <button type="submit" className="px-4 py-2 rounded-xl text-xs font-bold text-white ea-primary cursor-pointer">Apply</button>
        <button type="button" onClick={reset} className="px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 cursor-pointer">Reset</button>
      </form>

      {error && <div className="text-xs font-semibold text-rose-600 dark:text-rose-400">{error}</div>}

      {/* Fits the available width (no horizontal scrollbar) from tablet up: fixed column layout, wrapping / ellipsis.
          Phones (< md) cannot fit 8-9 columns, so only there the card scrolls sideways instead of squashing the data. */}
      <div className="w-full max-w-full min-w-0 rounded-2xl ff-card border border-slate-200 dark:border-purple-900/30 md:overflow-hidden max-md:overflow-x-auto">
        <table className="w-full max-w-full table-fixed text-[11px] xl:text-xs max-md:min-w-[760px]">
          <colgroup>
            {cols.map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}
          </colgroup>
          <thead>
            <tr className="text-left text-[10px] xl:text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <th className={th}>Document</th>
              {admin && <th className={th}>Owner</th>}
              <th className={th}>Tool</th>
              <th className={th}>Original file</th>
              <th className={th}>Output file</th>
              <th className={th}>Type · Size</th>
              <th className={th}>Processed</th>
              <th className={th}>Status</th>
              <th className={`${th} text-right`}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={colCount} className="px-4 py-10 text-center text-slate-400">Loading…</td></tr>}
            {!loading && data.items.length === 0 && (
              <tr><td colSpan={colCount} className="px-4 py-12 text-center text-slate-400">
                <FileText className="h-6 w-6 mx-auto mb-2 opacity-60" />No documents found.
              </td></tr>
            )}
            {!loading && data.items.map((d) => (
              <tr key={d.id} className="border-b border-slate-100 dark:border-slate-800/60 last:border-0 align-top">
                <td className={`${td} font-semibold text-slate-900 dark:text-white truncate`} title={d.document_name}>{d.document_name}</td>
                {admin && <td className={`${td} text-slate-600 dark:text-slate-300 truncate`} title={d.owner?.username}>{d.owner?.username}</td>}
                <td className={`${td} text-slate-600 dark:text-slate-300 break-words`}>{d.tool_label}</td>
                <td className={`${td} text-slate-600 dark:text-slate-300 truncate`} title={d.original_filename || ''}>{d.original_filename || '—'}</td>
                <td className={`${td} text-slate-600 dark:text-slate-300 truncate`} title={d.output_filename || ''}>{d.output_filename || '—'}</td>
                <td className={`${td} text-slate-600 dark:text-slate-300 break-words`}>{(d.file_type || '—').toUpperCase()} · {formatFileSize(d.output_size)}</td>
                <td className={`${td} text-slate-600 dark:text-slate-300 break-words`}>{formatDate(d.created_at)}</td>
                <td className={td}>
                  <div className="max-w-full [&>span]:max-w-full [&>span]:px-1.5 [&>span]:text-[10px] xl:[&>span]:px-2.5 xl:[&>span]:text-xs"><StatusBadge status={d.status} /></div>
                  {d.error_summary && <div className="mt-1 text-[11px] text-rose-600 dark:text-rose-400 break-words">{d.error_summary}</div>}
                </td>
                <td className={td}>
                  <div className="flex flex-wrap justify-end gap-0.5">
                    <button title={previewable(d) ? 'View' : 'Preview not available for this file type'} disabled={!previewable(d)}
                      onClick={() => setPreview(d)} className="p-1.5 rounded-lg text-slate-500 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer"><Eye className="h-4 w-4" /></button>
                    <a title="Download output" href={d.has_output ? documentService.downloadUrl(d.id) : undefined}
                      className={`p-1.5 rounded-lg ${d.has_output ? 'text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-slate-800' : 'opacity-30 pointer-events-none'}`}><Download className="h-4 w-4" /></a>
                    {d.has_original && (
                      <a title="Download original" href={documentService.downloadUrl(d.id, 'original')}
                        className="px-1.5 py-1.5 rounded-lg text-[10px] font-bold text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-slate-800">ORIG</a>
                    )}
                    {canDelete && (
                      <button title="Delete" onClick={() => setToDelete(d)} className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-rose-50 dark:hover:bg-slate-800 cursor-pointer"><Trash2 className="h-4 w-4" /></button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>{data.total} document{data.total === 1 ? '' : 's'}</span>
        <div className="flex items-center gap-2">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 disabled:opacity-40 cursor-pointer"><ChevronLeft className="h-4 w-4" /></button>
          <span>Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)} className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 disabled:opacity-40 cursor-pointer"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={confirmDelete}
        isLoading={deleting}
        title="Delete document?"
        message={`"${toDelete?.document_name}" will be removed from the list. Stored files are permanently deleted after the retention period.`}
        confirmText="Delete"
      />

      <Modal isOpen={!!preview} onClose={() => setPreview(null)} title={preview?.output_filename || 'Preview'} maxWidth="max-w-5xl">
        {preview && (
          <iframe
            title="Document preview"
            src={documentService.viewUrl(preview.id)}
            {...(preview.file_type === 'pdf' ? {} : { sandbox: '' })}
            className="w-full h-[70vh] rounded-xl border border-slate-200 dark:border-slate-800 bg-white"
          />
        )}
      </Modal>
    </div>
  );
}
