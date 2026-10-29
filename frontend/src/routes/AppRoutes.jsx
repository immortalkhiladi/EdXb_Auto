import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute.jsx';
import DashboardLayout from '../layouts/DashboardLayout.jsx';
import { useAuth } from '../context/AuthContext.jsx';

import Login from '../pages/Login.jsx';
import Dashboard from '../pages/Dashboard.jsx';
import Documents from '../pages/Documents.jsx';
import AllDocuments from '../pages/AllDocuments.jsx';
import ResetPassword from '../pages/ResetPassword.jsx';
import AdminConsole from '../pages/AdminConsole.jsx';
import Settings from '../pages/Settings.jsx';
import ToolFrame from '../pages/ToolFrame.jsx';
import Unauthorized from '../pages/Unauthorized.jsx';
import NotFound from '../pages/NotFound.jsx';

// Entry point: signed-out visitors land on the login page, signed-in users on the dashboard.
function RootRedirect() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* Entry point + public auth pages */}
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/unauthorized" element={<Unauthorized />} />

      {/* Authenticated Client Filing Portal Routes (role-checked per page via utils/rbac.js) */}
      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route element={<ProtectedRoute pageKey="dashboard" />}>
            <Route path="/dashboard" element={<Dashboard />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="documents" />}>
            <Route path="/documents" element={<Documents />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="allDocuments" />}>
            <Route path="/all-documents" element={<AllDocuments />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="redline" />}>
            <Route path="/redline-gofiler" element={<ToolFrame toolId="redline" title="Redline to GoFiler HTML" />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="gofilerhtml" />}>
            <Route path="/html-converter" element={<ToolFrame toolId="gofilerhtml" title="GoFiler HTML Converter" />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="converter" />}>
            <Route path="/converter" element={<ToolFrame toolId="converter" title="PPT & PDF Converter" />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="secforms" />}>
            <Route path="/sec-forms" element={<ToolFrame toolId="secforms" title="SEC Form Type Dashboard" />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="admin" />}>
            <Route path="/admin" element={<AdminConsole />} />
          </Route>
          <Route element={<ProtectedRoute pageKey="settings" />}>
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>
      </Route>

      {/* 404 Route */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
