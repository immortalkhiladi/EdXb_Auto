import DocumentsTable from '../components/documents/DocumentsTable.jsx';

// ADMIN and MD only (route guard in AppRoutes + role check on the server API).
export default function AllDocuments() {
  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">All Documents</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Documents processed by every user. Filter by User ID to narrow the list.
        </p>
      </div>
      <DocumentsTable admin />
    </div>
  );
}
