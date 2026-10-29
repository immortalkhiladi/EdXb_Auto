import { useState, useRef, useEffect } from 'react';
import {
  HelpCircle,
  Menu,
  ChevronDown,
  User as UserIcon,
  Shield,
  Settings,
  LogOut,
  CheckCircle2,
  FileCheck
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';
import ThemeToggle from '../common/ThemeToggle.jsx';
import Modal from '../common/Modal.jsx';

export default function Topbar({ onToggleSidebar }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const menuRef = useRef(null);

  // Close menus on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between ff-nav-glass px-6 transition-colors duration-200">
      {/* Left: Mobile hamburger */}
      <div className="flex items-center gap-4 flex-1">
        <button
          onClick={onToggleSidebar}
          type="button"
          aria-label="Open sidebar"
          className="p-2 rounded-xl text-navy-100 hover:text-white hover:bg-white/10 lg:hidden"
        >
          <Menu className="h-6 w-6" />
        </button>

      </div>

      {/* Right: Actions & User Avatar */}
      <div className="flex items-center gap-3">
        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Help Icon */}
        <button
          onClick={() => setHelpOpen(true)}
          type="button"
          aria-label="Help and Documentation"
          className="p-2.5 rounded-xl text-navy-100 hover:text-white hover:bg-white/10 border border-white/15 transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
        </button>

        {/* User Profile Dropdown */}
        <div className="relative ml-2" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-3 p-1.5 rounded-xl hover:bg-white/10 transition-all border border-transparent hover:border-white/15"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl ea-primary font-bold text-sm shadow-md">
              {(user?.full_name || user?.username || 'U').charAt(0).toUpperCase()}
            </div>
            <div className="hidden sm:flex flex-col text-left">
              <span className="text-sm font-bold text-white tracking-tight leading-none">
                {user?.full_name || user?.username}
              </span>
              <span className="text-[11px] font-semibold text-turquoise-400 mt-0.5">
                {{ ADMIN: 'Administrator', MD: 'MD' }[user?.role] || 'User'}
              </span>
            </div>
            <ChevronDown className="h-4 w-4 text-navy-200 hidden sm:block" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-2xl ff-card border border-slate-200 dark:border-purple-800/40 shadow-2xl p-2 z-50 animate-fade-in">
              <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Signed in as</p>
                <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{user?.username}</p>
              </div>

              <div className="mt-1 space-y-0.5">
                <button
                  onClick={() => { setUserMenuOpen(false); navigate('/settings'); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300 hover:text-purple-700 dark:hover:text-white hover:bg-purple-50 dark:hover:bg-slate-800/70 transition-colors"
                >
                  <UserIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                  <span>Profile</span>
                </button>
                <button
                  onClick={() => { setUserMenuOpen(false); navigate('/settings'); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300 hover:text-purple-700 dark:hover:text-white hover:bg-purple-50 dark:hover:bg-slate-800/70 transition-colors"
                >
                  <Settings className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                  <span>Settings</span>
                </button>
                <button
                  onClick={() => { setUserMenuOpen(false); navigate('/settings'); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300 hover:text-purple-700 dark:hover:text-white hover:bg-purple-50 dark:hover:bg-slate-800/70 transition-colors"
                >
                  <Shield className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                  <span>Security</span>
                </button>
                <div className="border-t border-slate-100 dark:border-slate-800/80 my-1" />
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-rose-600 dark:text-rose-400 hover:text-rose-700 dark:hover:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Help Modal */}
      <Modal isOpen={helpOpen} onClose={() => setHelpOpen(false)} title="EDGAR Agents LLC — Help">
        <div className="space-y-4 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
          <p>
            Welcome to the <strong className="text-slate-900 dark:text-white">EDGAR Agents LLC</strong> automation portal — the SEC document conversion and EDGAR workflow suite. Pick a tool from the sidebar; every result is saved privately under My Documents. For account or access questions, contact your administrator.
          </p>
          <div className="pt-2 flex justify-end">
            <button
              onClick={() => setHelpOpen(false)}
              className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs"
            >
              Got it
            </button>
          </div>
        </div>
      </Modal>
    </header>
  );
}
