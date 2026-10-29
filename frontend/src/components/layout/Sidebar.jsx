import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileCode2,
  FileStack,
  GitCompare,
  FileText,
  Files,
  BookOpenCheck,
  ShieldCheck,
  Settings,
  X
} from 'lucide-react';
import Logo from '../common/Logo.jsx';
import { useAuth } from '../../context/AuthContext.jsx';

export default function Sidebar({ isOpen, onClose }) {
  const { hasAccess } = useAuth();

  const navItems = [
    { name: 'Dashboard', page: 'dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Documents', page: 'documents', path: '/documents', icon: FileText },
    { name: 'All Documents', page: 'allDocuments', path: '/all-documents', icon: Files },
    { name: 'Redline to GoFiler HTML', page: 'redline', path: '/redline-gofiler', icon: GitCompare },
    { name: 'GoFiler HTML Converter', page: 'gofilerhtml', path: '/html-converter', icon: FileCode2 },
    { name: 'PPT & PDF Converter', page: 'converter', path: '/converter', icon: FileStack },
    { name: 'SEC Form Type Dashboard', page: 'secforms', path: '/sec-forms', icon: BookOpenCheck },
    { name: 'Admin Console', page: 'admin', path: '/admin', icon: ShieldCheck },
    { name: 'Settings', page: 'settings', path: '/settings', icon: Settings },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 dark:bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 w-64 flex flex-col ff-side shadow-sm dark:shadow-none transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo Header */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-white/10">
          <NavLink to="/dashboard" onClick={onClose}>
            <Logo showTagline={true} className="[&_span]:text-white" />
          </NavLink>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-navy-200 hover:text-white lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
          <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-navy-300">
            Menu
          </p>

          {navItems.map((item) => {
            if (!hasAccess(item.page)) {
              return null;
            }

            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3.5 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all duration-200 group ${
                    isActive
                      ? 'ea-primary shadow-sm font-bold'
                      : 'text-navy-100 hover:text-white hover:bg-white/10'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-5 w-5 transition-transform duration-200 group-hover:scale-110 ${
                        isActive ? 'text-navy-800' : 'text-navy-300 group-hover:text-turquoise-400'
                      }`}
                    />
                    <span>{item.name}</span>
                    {isActive && (
                      <div className="ml-auto h-1.5 w-1.5 rounded-full bg-navy-800" />
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </aside>
    </>
  );
}
