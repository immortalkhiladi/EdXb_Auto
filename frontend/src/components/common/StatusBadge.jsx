export default function StatusBadge({ status }) {
  if (!status) return null;

  const normalized = status.toString().toLowerCase().trim();

  let styles = 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/60 dark:text-slate-300 dark:border-slate-700/50';
  let dotColor = 'bg-slate-500 dark:bg-slate-400';

  if (normalized === 'processed' || normalized === 'completed' || normalized === 'active') {
    styles = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/30';
    dotColor = 'bg-emerald-500 dark:bg-emerald-400';
  } else if (normalized === 'pending' || normalized === 'queued') {
    styles = 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/30';
    dotColor = 'bg-amber-500 dark:bg-amber-400';
  } else if (normalized === 'processing' || normalized === 'uploading' || normalized === 'validating') {
    styles = 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/30';
    dotColor = 'bg-blue-500 dark:bg-blue-400 animate-pulse';
  } else if (normalized === 'requires review' || normalized === 'requires_review') {
    styles = 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-500/10 dark:text-purple-300 dark:border-purple-500/30';
    dotColor = 'bg-purple-500 dark:bg-purple-400';
  } else if (normalized === 'failed' || normalized === 'inactive' || normalized === 'error') {
    styles = 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/30';
    dotColor = 'bg-rose-500 dark:bg-rose-400';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border backdrop-blur-sm ${styles}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      <span>{status}</span>
    </span>
  );
}
