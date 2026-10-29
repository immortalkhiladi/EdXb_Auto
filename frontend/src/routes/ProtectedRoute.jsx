import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

export default function ProtectedRoute({ allowedRoles, pageKey }) {
  const { isAuthenticated, loading, user, hasAccess } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const userRole = user?.role?.toUpperCase();
    const hasRole = allowedRoles.map((r) => r.toUpperCase()).includes(userRole);
    if (!hasRole) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  if (pageKey && !hasAccess(pageKey)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
}
