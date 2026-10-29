import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { KeyRound, Eye, EyeOff, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authService } from '../services/authService.js';
import { errorMessage } from '../services/api.js';
import { passwordError, PASSWORD_HINT } from '../utils/passwordPolicy.js';

const field = 'w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300';

// Step 2 of a password reset: reached from the emailed link (/reset-password?uid=…&token=…).
export default function ResetPassword() {
  const [params] = useSearchParams();
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const problem = passwordError(password);
    if (problem) return setError(problem);
    if (password !== confirm) return setError('The two passwords do not match.');
    setBusy(true);
    try {
      const res = await authService.resetPassword(uid, token, password);
      setDone(res.message || 'Your password has been reset.');
      setPassword(''); setConfirm('');
    } catch (err) {
      setError(err?.response ? errorMessage(err, 'We could not reset your password. Please try again.') : 'Could not reach the server. Check your connection and try again.');
    } finally {
      setBusy(false);
    }
  };

  const linkMissing = !uid || !token;

  return (
    <div className="min-h-screen ff-page flex items-center justify-center p-4 text-slate-900 dark:text-slate-100">
      <div className="w-full max-w-[430px] rounded-3xl ff-card p-7 sm:p-9 shadow-2xl border space-y-5">
        <div className="space-y-2 text-center">
          <div className="inline-flex p-3 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white border border-rose-500/20">
            <KeyRound className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-black text-slate-950 dark:text-white tracking-tight">Choose a new password</h1>
        </div>

        {done ? (
          <>
            <div className="p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 text-emerald-800 dark:text-emerald-300 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" /><span>{done}</span>
            </div>
            <Link to="/login" className="block w-full text-center py-3 rounded-xl text-sm font-extrabold text-white ea-primary">Go to Sign In</Link>
          </>
        ) : linkMissing ? (
          <>
            <div className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" /><span>This password reset link is incomplete. Please use the full link from your email, or request a new one.</span>
            </div>
            <Link to="/login" className="block text-center text-xs font-semibold text-slate-900 dark:text-white hover:underline">Back to Sign In</Link>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate autoComplete="off">
            <p className="text-xs text-slate-500 dark:text-slate-400">{PASSWORD_HINT}</p>
            {error && (
              <div className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" /><span>{error}</span>
              </div>
            )}
            <div className="relative">
              <input type={show ? 'text' : 'password'} autoComplete="new-password" placeholder="New password" value={password} onChange={(e) => setPassword(e.target.value)} className={`${field} pr-11`} />
              <button type="button" onClick={() => setShow(!show)} title={show ? 'Hide password' : 'Show password'} className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer">
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <input type={show ? 'text' : 'password'} autoComplete="new-password" placeholder="Confirm new password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={field} />
            <button type="submit" disabled={busy} className="w-full py-3 rounded-xl text-sm font-extrabold text-white ea-primary disabled:opacity-50 cursor-pointer">
              {busy ? 'Saving…' : 'Reset password'}
            </button>
            <Link to="/login" className="block text-center text-xs font-semibold text-slate-500 hover:text-slate-900 dark:hover:text-white">Back to Sign In</Link>
          </form>
        )}
      </div>
    </div>
  );
}
