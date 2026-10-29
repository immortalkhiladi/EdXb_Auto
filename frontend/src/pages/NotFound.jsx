import { FileQuestion, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6 space-y-4">
      <div className="p-4 rounded-3xl bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-500/20 shadow-sm dark:shadow-2xl">
        <FileQuestion className="h-12 w-12" />
      </div>
      <h1 className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white">404 — Page Not Found</h1>
      <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-md leading-relaxed">
        The page or URL requested does not exist in the EDGAR Agents LLC portal.
      </p>
      <button
        onClick={() => navigate('/dashboard')}
        className="mt-4 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shadow-md"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Return to Dashboard</span>
      </button>
    </div>
  );
}
