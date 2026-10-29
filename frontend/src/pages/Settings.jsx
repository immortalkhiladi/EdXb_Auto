import { useState } from 'react';
import {
  User,
  Shield,
  Palette,
  Bell,
  Check,
  AlertCircle,
  Sun,
  Moon,
  Laptop
} from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import { useTheme } from '../context/ThemeContext.jsx';
import { authService } from '../services/authService.js';
import { errorMessage } from '../services/api.js';
import { passwordError, PASSWORD_HINT } from '../utils/passwordPolicy.js';

export default function Settings() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();

  const [activeTab, setActiveTab] = useState('profile');

  // Security tab state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMsg, setPasswordMsg] = useState({ text: '', isError: false });
  const [savingPassword, setSavingPassword] = useState(false);

  // Notifications tab state
  const [notifs, setNotifs] = useState({
    processing: true,
    security: true,
    digest: false
  });

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setPasswordMsg({ text: '', isError: false });

    const problem = passwordError(newPassword);
    if (problem) {
      setPasswordMsg({ text: problem, isError: true });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ text: 'New passwords do not match.', isError: true });
      return;
    }

    setSavingPassword(true);
    try {
      await authService.changePassword(currentPassword, newPassword);
      setPasswordMsg({ text: 'Password changed successfully.', isError: false });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setPasswordMsg({
        text: errorMessage(err, 'Error updating password'),
        isError: true
      });
    } finally {
      setSavingPassword(false);
    }
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'notifications', label: 'Notifications', icon: Bell }
  ];

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
          Account &amp; System Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Configure personal preferences, credentials, and notification triggers.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                isActive
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-900/30'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="p-6 rounded-3xl ff-card border border-slate-200 dark:border-purple-900/30 shadow-sm dark:shadow-xl space-y-6 transition-colors">
          <div className="flex items-center gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
            <div className="h-16 w-16 rounded-2xl ea-primary flex items-center justify-center text-white text-2xl font-black shadow-md">
              {(user?.full_name || user?.username || 'U').charAt(0).toUpperCase()}
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">{user?.full_name}</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-mono">{user?.username}</p>
              <span className="mt-1.5 inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/40">
                {user?.role}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-slate-500 dark:text-slate-400 font-bold uppercase mb-1">Full Name</label>
              <input
                type="text"
                disabled
                value={user?.full_name || ''}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-slate-500 dark:text-slate-400 font-bold uppercase mb-1">Corporate Email</label>
              <input
                type="email"
                disabled
                value={user?.email || ''}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 cursor-not-allowed font-mono"
              />
            </div>
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="p-6 rounded-3xl ff-card border border-slate-200 dark:border-purple-900/30 shadow-sm dark:shadow-xl space-y-6 transition-colors">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Change Password</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {PASSWORD_HINT}
            </p>
          </div>

          {passwordMsg.text && (
            <div
              className={`p-3.5 rounded-xl text-xs flex items-center gap-2 ${
                passwordMsg.isError
                  ? 'bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 text-rose-700 dark:text-rose-300'
                  : 'bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300'
              }`}
            >
              {passwordMsg.isError ? <AlertCircle className="h-4 w-4" /> : <Check className="h-4 w-4" />}
              <span>{passwordMsg.text}</span>
            </div>
          )}

          <form onSubmit={handlePasswordSubmit} className="space-y-4 max-w-md text-xs">
            <div>
              <label className="block text-slate-600 dark:text-slate-400 font-bold uppercase mb-1">Current Password</label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-purple-900/40 text-slate-900 dark:text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-slate-600 dark:text-slate-400 font-bold uppercase mb-1">New Password</label>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-purple-900/40 text-slate-900 dark:text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-slate-600 dark:text-slate-400 font-bold uppercase mb-1">Confirm New Password</label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-purple-900/40 text-slate-900 dark:text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <button
              type="submit"
              disabled={savingPassword}
              className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
            >
              {savingPassword ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        </div>
      )}

      {/* Appearance Tab */}
      {activeTab === 'appearance' && (
        <div className="p-6 rounded-3xl ff-card border border-slate-200 dark:border-purple-900/30 shadow-sm dark:shadow-xl space-y-6 transition-colors">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Interface Theme</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Select between the dark theme and the light theme.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button
              type="button"
              onClick={() => setTheme('dark')}
              className={`p-4 rounded-2xl border text-left transition-all cursor-pointer ${
                theme === 'dark'
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-2 ring-purple-500/50'
                  : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <Moon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                {theme === 'dark' && <Check className="h-4 w-4 text-purple-600 dark:text-purple-400" />}
              </div>
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">Dark Theme</h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Deep navy &amp; glowing violet</p>
            </button>

            <button
              type="button"
              onClick={() => setTheme('light')}
              className={`p-4 rounded-2xl border text-left transition-all cursor-pointer ${
                theme === 'light'
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-2 ring-purple-500/50'
                  : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <Sun className="h-5 w-5 text-amber-500" />
                {theme === 'light' && <Check className="h-4 w-4 text-purple-600 dark:text-purple-400" />}
              </div>
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">Light Theme</h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">High-contrast clean workspace</p>
            </button>

            <button
              type="button"
              onClick={() => setTheme('system')}
              className={`p-4 rounded-2xl border text-left transition-all cursor-pointer ${
                theme === 'system'
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-2 ring-purple-500/50'
                  : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <Laptop className="h-5 w-5 text-blue-500" />
                {theme === 'system' && <Check className="h-4 w-4 text-purple-600 dark:text-purple-400" />}
              </div>
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">System Preference</h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Synchronizes with OS</p>
            </button>
          </div>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="p-6 rounded-3xl ff-card border border-slate-200 dark:border-purple-900/30 shadow-sm dark:shadow-xl space-y-4 transition-colors">
          <div className="pb-3 border-b border-slate-100 dark:border-slate-800">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Notification Triggers</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Manage pipeline alert preferences.</p>
          </div>

          <div className="space-y-3">
            <label className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 cursor-pointer">
              <div>
                <h4 className="text-xs font-bold text-slate-900 dark:text-white">Processing Complete Alerts</h4>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">Receive toasts when batch files complete.</p>
              </div>
              <input
                type="checkbox"
                checked={notifs.processing}
                onChange={(e) => setNotifs({ ...notifs, processing: e.target.checked })}
                className="h-4 w-4 rounded bg-slate-100 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-purple-600 focus:ring-purple-500"
              />
            </label>

            <label className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 cursor-pointer">
              <div>
                <h4 className="text-xs font-bold text-slate-900 dark:text-white">Security &amp; Auth Alerts</h4>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">Notify upon new session logins or password updates.</p>
              </div>
              <input
                type="checkbox"
                checked={notifs.security}
                onChange={(e) => setNotifs({ ...notifs, security: e.target.checked })}
                className="h-4 w-4 rounded bg-slate-100 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-purple-600 focus:ring-purple-500"
              />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
