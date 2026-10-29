import DocumentsTable from '../components/documents/DocumentsTable.jsx';

export default function Documents() {
  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">My Documents</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Files processed with your account. Only you (and system administrators) can open them.
        </p>
      </div>
      <DocumentsTable />
    </div>
  );
}
