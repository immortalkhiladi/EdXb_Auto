import { useState } from 'react';
import { KeyRound, X, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authService } from '../../services/authService.js';
import { errorMessage } from '../../services/api.js';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Step 1 of a password reset: asks for the account email and has the server send a signed, expiring, single-use link.
// (Step 2 is pages/ResetPassword.jsx.) Nothing here ever sees or shows an existing password.
export default function ForgotPasswordModal({ onClose }) {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const value = email.trim();
    if (!EMAIL_RE.test(value)) {
      setError('Please enter a valid email address (for example name@company.com).');
      return;
    }
    setBusy(true);
    try {
      const res = await authService.forgotPassword(value);
      setDone(res.message || 'A password reset link has been sent to your email address.');
    } catch (err) {
      const offline = !err?.response;
      setError(offline
        ? 'Could not reach the server. Check your connection and try again.'
        : errorMessage(err, 'We could not start the password reset. Please try again later.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-3xl bg-white dark:bg-slate-900 p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4 text-slate-900 dark:text-slate-100">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-slate-900 dark:text-white" />
            <h3 className="text-base font-bold">Password Reset</h3>
          </div>
          <button type="button" onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-slate-800 dark:hover:text-slate-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        {done ? (
          <>
            <div className="p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 text-emerald-800 dark:text-emerald-300 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{done} Open the link in the email to choose a new password.</span>
            </div>
            <div className="flex justify-end pt-2">
              <button type="button" onClick={onClose} className="px-5 py-2 rounded-xl ea-primary text-white text-xs font-bold shadow-md">Close</button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Enter the email address registered to your account. We will email you a link to choose a new password.
            </p>
            {error && (
              <div className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2.5">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
                <span>{error}</span>
              </div>
            )}
            <input
              type="email" name="reset-email-field" autoComplete="off" autoFocus value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com"
              className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs sm:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300"
            />
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800">Cancel</button>
              <button type="submit" disabled={busy} className="px-5 py-2 rounded-xl ea-primary text-white text-xs font-bold shadow-md disabled:opacity-50">
                {busy ? 'Sending…' : 'Send reset link'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
