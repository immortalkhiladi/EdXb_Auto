import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Keyboard as KeyboardIcon, ArrowRight, ShieldCheck, AlertCircle, X, HelpCircle, KeyRound, User as UserIcon, Linkedin, ExternalLink } from 'lucide-react';
import Navbar from '../components/layout/Navbar.jsx';
import Logo from '../components/common/Logo.jsx';
import MfaStep from '../components/common/MfaStep.jsx';
import ForgotPasswordModal from '../components/common/ForgotPasswordModal.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { companyContactInfo } from '../data/teamData.js';
import api from '../services/api.js';
import { formatDate } from '../utils/formatters.js';

const FIELD =
  'w-full pl-10 pr-20 py-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300 focus:border-transparent transition-colors';

const SERVICES = ['EDGAR conversion', 'XBRL tagging', 'Typesetting', 'Printing'];

export default function Login() {
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [armed, setArmed] = useState({ userId: false, password: false }); // inputs stay read-only until focused so browsers can't auto-fill them
  const [showPassword, setShowPassword] = useState(false);
  const [step, setStep] = useState('credentials'); // credentials | mfa_required | mfa_setup_required
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [virtualKeypadOpen, setVirtualKeypadOpen] = useState(false);
  const [activeInputForPad, setActiveInputForPad] = useState('password');
  const [troubleModal, setTroubleModal] = useState(false);
  const [resetPasswordModal, setResetPasswordModal] = useState(false);
  const [updates, setUpdates] = useState([]); // company updates maintained in backend/portal/linkedin_updates.json

  useEffect(() => {
    api.get('/linkedin-updates').then((r) => setUpdates(r.data.items || [])).catch(() => {});
  }, []);

  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setLoading(true);
    try {
      const result = await login(userId.trim(), password);
      if (result && result.success) {
        if (result.status === 'ok') navigate('/dashboard');
        else setStep(result.status); // MFA step
        setPassword('');
      } else {
        setErrorMessage(result?.message || 'Authentication error. Please check your credentials.');
      }
    } catch {
      setErrorMessage('Authentication error. Please try again or contact your administrator.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeypadPress = (val) => {
    const set = activeInputForPad === 'userId' ? setUserId : setPassword;
    if (val === 'CLEAR') set('');
    else if (val === 'BACK') set((prev) => prev.slice(0, -1));
    else set((prev) => prev + val);
  };

  return (
    <div className="min-h-screen ff-page text-slate-900 dark:text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 flex flex-col items-center justify-center gap-6 px-4 sm:px-6 pt-20 pb-10">
        <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xl">
          {/* Brand panel */}
          <section className="hidden lg:flex flex-col justify-between p-10 bg-navy-800 text-white">
            <Logo size="large" className="[&_span]:text-white" />
            <div className="space-y-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-turquoise-400">Automation portal</p>
              <h1 className="text-3xl font-extrabold tracking-tight leading-tight">
                SEC filing documents,<br />prepared with confidence.
              </h1>
              <p className="text-sm text-slate-300 leading-relaxed max-w-sm">
                Convert, redline and validate EDGAR documents in one secure workspace. Every result is stored privately under your account.
              </p>
              <ul className="flex flex-wrap gap-2">
                {SERVICES.map((s) => (
                  <li key={s} className="px-3 py-1 rounded-full border border-turquoise-500/40 text-xs font-semibold text-turquoise-100">{s}</li>
                ))}
              </ul>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              <span>Authorized users only · Sessions expire after inactivity</span>
            </div>
          </section>

          {/* Sign-in form */}
          <section className="p-6 sm:p-10">
            <div className="lg:hidden mb-6"><Logo /></div>
            <h2 className="text-2xl font-extrabold tracking-tight text-slate-950 dark:text-white">Sign in</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Use the User ID and password issued by your administrator.</p>

            {isAuthenticated && (
              <div role="status" className="mt-5 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 text-emerald-800 dark:text-emerald-300 text-sm flex items-center justify-between gap-3">
                <span className="truncate">Signed in as <b>{user?.full_name || user?.username}</b></span>
                <button type="button" onClick={() => navigate('/dashboard')} className="font-bold underline shrink-0">Open dashboard →</button>
              </div>
            )}

            {errorMessage && (
              <div role="alert" className="mt-5 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 text-sm flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
                <span>{errorMessage}</span>
              </div>
            )}

            {step !== 'credentials' ? (
              <div className="mt-6">
                <MfaStep mode={step} onDone={() => navigate('/dashboard')} onCancel={() => { setStep('credentials'); setPassword(''); }} />
              </div>
            ) : (
              <form onSubmit={handleLoginSubmit} autoComplete="off" className="mt-6 space-y-5">
                <div className="space-y-1.5">
                  <label htmlFor="login-user" className="block text-sm font-semibold text-slate-700 dark:text-slate-300">User ID</label>
                  <div className="relative">
                    <UserIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" aria-hidden="true" />
                    <input
                      id="login-user"
                      type="text"
                      name="login-id-field"
                      autoComplete="off"
                      autoCorrect="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      readOnly={!armed.userId}
                      onFocus={() => setArmed((a) => ({ ...a, userId: true }))}
                      required
                      value={userId}
                      onChange={(e) => setUserId(e.target.value)}
                      placeholder="User ID or email"
                      className={FIELD}
                    />
                    <button
                      type="button"
                      onClick={() => { setActiveInputForPad('userId'); setVirtualKeypadOpen(true); }}
                      aria-label="Open virtual keypad for User ID"
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    >
                      <KeyboardIcon className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="login-password" className="block text-sm font-semibold text-slate-700 dark:text-slate-300">Password</label>
                    <button type="button" onClick={() => setResetPasswordModal(true)} className="text-xs font-semibold text-slate-700 dark:text-slate-300 hover:underline">
                      Forgot password?
                    </button>
                  </div>
                  <div className="relative">
                    <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" aria-hidden="true" />
                    <input
                      id="login-password"
                      type={showPassword ? 'text' : 'password'}
                      name="login-secret-field"
                      autoComplete="new-password"
                      readOnly={!armed.password}
                      onFocus={() => setArmed((a) => ({ ...a, password: true }))}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      className={FIELD}
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                        aria-pressed={showPassword}
                        className="p-1 text-slate-400 hover:text-slate-900 dark:hover:text-white"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveInputForPad('password'); setVirtualKeypadOpen(true); }}
                        aria-label="Open virtual keypad for password"
                        className="p-1 text-slate-400 hover:text-slate-900 dark:hover:text-white"
                      >
                        <KeyboardIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  aria-busy={loading}
                  className="ea-primary w-full py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <span>{loading ? 'Signing in…' : 'Sign in'}</span>
                  {!loading && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
                </button>

                <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                  <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />Encrypted connection</span>
                  <button type="button" onClick={() => setTroubleModal(true)} className="font-semibold hover:text-slate-900 dark:hover:text-white">Need assistance?</button>
                </div>
              </form>
            )}
          </section>
        </div>

        {/* Company updates (manually maintained list + link to the LinkedIn page) */}
        <section aria-labelledby="updates-title" className="w-full max-w-5xl rounded-2xl border border-navy-100 dark:border-navy-600 bg-white dark:bg-navy-800 p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 id="updates-title" className="text-base font-extrabold tracking-tight text-navy-800 dark:text-white flex items-center gap-2">
              <Linkedin className="h-5 w-5 text-turquoise-500" aria-hidden="true" />Latest from EDGAR Agents LLC
            </h2>
            <a href={companyContactInfo.linkedin} target="_blank" rel="noreferrer" className="ea-primary inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold">
              Follow us on LinkedIn <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          </div>
          {updates.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-navy-200">Visit our LinkedIn page for the latest news.</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {updates.map((u) => (
                <li key={u.link || u.title} className="rounded-xl border border-navy-100 dark:border-navy-600 bg-navy-50 dark:bg-navy-900 p-4 flex flex-col gap-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-turquoise-600 dark:text-turquoise-400">{u.date ? formatDate(u.date) : ''}</span>
                  <span className="text-sm font-bold text-navy-800 dark:text-white">{u.title}</span>
                  <p className="text-xs text-slate-600 dark:text-navy-200 leading-relaxed">{u.text}</p>
                  {u.link && <a href={u.link} target="_blank" rel="noreferrer" className="mt-auto text-xs font-semibold text-turquoise-700 dark:text-turquoise-300 hover:underline">Read more →</a>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      {/* Virtual keypad (digits only): protects against keyloggers for numeric IDs/PINs */}
      {virtualKeypadOpen && (
        <div role="dialog" aria-modal="true" aria-labelledby="keypad-title" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="w-full max-w-sm rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 id="keypad-title" className="text-sm font-bold flex items-center gap-2">
                <KeyboardIcon className="h-5 w-5" aria-hidden="true" />
                Virtual keypad · {activeInputForPad === 'password' ? 'Password' : 'User ID'}
              </h3>
              <button type="button" onClick={() => setVirtualKeypadOpen(false)} aria-label="Close keypad" className="p-1 rounded-lg text-slate-400 hover:text-slate-900 dark:hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm font-bold">
              {['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'].map((num) => (
                <button key={num} type="button" onClick={() => handleKeypadPress(num)} className="py-3 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-900 hover:text-white dark:hover:bg-white dark:hover:text-slate-900 transition-colors">
                  {num}
                </button>
              ))}
              <button type="button" onClick={() => handleKeypadPress('BACK')} className="py-3 rounded-xl bg-slate-200 dark:bg-slate-700 text-xs font-bold">BACK</button>
              <button type="button" onClick={() => handleKeypadPress('CLEAR')} className="py-3 rounded-xl bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-xs font-bold">CLEAR</button>
            </div>
            <button type="button" onClick={() => setVirtualKeypadOpen(false)} className="ea-primary w-full py-2.5 rounded-xl font-bold text-xs">Done</button>
          </div>
        </div>
      )}

      {/* Assistance */}
      {troubleModal && (
        <div role="dialog" aria-modal="true" aria-labelledby="help-title" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 id="help-title" className="text-base font-bold flex items-center gap-2"><HelpCircle className="h-5 w-5" aria-hidden="true" />Trouble signing in?</h3>
              <button type="button" onClick={() => setTroubleModal(false)} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-900 dark:hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>
            <ul className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed list-disc pl-5 space-y-1">
              <li>Accounts are created by an EDGAR Agents LLC administrator — there is no self-service sign-up.</li>
              <li>Use <b>Forgot password?</b> to receive a reset link at your registered email address.</li>
              <li>After several failed attempts the account is locked temporarily; ask your administrator to unlock it.</li>
            </ul>
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs space-y-1">
              <div className="font-bold text-slate-900 dark:text-white">{companyContactInfo.name}</div>
              <a href={companyContactInfo.website} target="_blank" rel="noreferrer" className="block underline">{companyContactInfo.website}</a>
              <a href={companyContactInfo.linkedin} target="_blank" rel="noreferrer" className="block underline">LinkedIn</a>
            </div>
            <div className="flex justify-end">
              <button type="button" onClick={() => setTroubleModal(false)} className="ea-primary px-5 py-2 rounded-xl text-xs font-bold">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Forgot password: emails a signed, expiring, single-use reset link */}
      {resetPasswordModal && <ForgotPasswordModal onClose={() => setResetPasswordModal(false)} />}
    </div>
  );
}
