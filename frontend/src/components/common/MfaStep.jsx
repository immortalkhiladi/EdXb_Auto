import { useEffect, useState } from 'react';
import { ShieldCheck, AlertCircle } from 'lucide-react';
import { authService } from '../../services/authService.js';
import { useAuth } from '../../context/AuthContext.jsx';

// Second login step. mode = 'mfa_required' (enter code) | 'mfa_setup_required' (enrol authenticator app first).
export default function MfaStep({ mode, onDone, onCancel }) {
  const { verifyMfa } = useAuth();
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (mode === 'mfa_setup_required') {
      authService.mfaSetup().then(setSetup).catch(() => setError('Could not start MFA setup. Please sign in again.'));
    }
  }, [mode]);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    const res = await verifyMfa(code.trim());
    setBusy(false);
    if (res.success) onDone();
    else setError(res.message);
  };

  return (
    <form onSubmit={submit} className="space-y-4" autoComplete="off">
      <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white">
        <ShieldCheck className="h-5 w-5 text-slate-900 dark:text-white" />
        {mode === 'mfa_setup_required' ? 'Set up two-factor authentication' : 'Two-factor authentication'}
      </div>

      {mode === 'mfa_setup_required' ? (
        <div className="text-xs text-slate-600 dark:text-slate-400 space-y-2">
          <p>Administrator accounts require an authenticator app (Microsoft Authenticator, Google Authenticator, 1Password…).</p>
          <p>Add a new account using this setup key, then enter the 6-digit code it shows:</p>
          {setup ? (
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 font-mono text-[13px] break-all select-all text-slate-900 dark:text-slate-100">
              {setup.secret}
            </div>
          ) : (
            <div className="text-slate-400">Generating key…</div>
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-600 dark:text-slate-400">Enter the 6-digit code from your authenticator app.</p>
      )}

      {error && (
        <div className="p-3 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2.5">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <input
        autoFocus
        inputMode="numeric"
        pattern="[0-9]{6}"
        maxLength={6}
        required
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
        placeholder="123456"
        className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-center tracking-[0.5em] text-lg font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300"
      />
      <button
        type="submit"
        disabled={busy || code.length !== 6 || (mode === 'mfa_setup_required' && !setup)}
        className="w-full py-3 rounded-xl text-sm font-extrabold text-white ea-primary shadow-lg shadow-rose-500/25 disabled:opacity-50 cursor-pointer"
      >
        {busy ? 'Verifying…' : mode === 'mfa_setup_required' ? 'Confirm and sign in' : 'Verify'}
      </button>
      <button type="button" onClick={onCancel} className="w-full text-xs font-semibold text-slate-500 hover:text-slate-900 dark:hover:text-white cursor-pointer">
        Back to sign in
      </button>
    </form>
  );
}
