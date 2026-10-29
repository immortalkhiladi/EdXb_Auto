import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { authService } from '../services/authService.js';
import { canAccessPage } from '../utils/rbac.js';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  // The user lives only in memory. The session itself is an HttpOnly cookie that scripts cannot read.
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const inflight = useRef(null);
  const lastRefresh = useRef({ at: 0, user: null });

  useEffect(() => {
    let cancelled = false;
    authService.getCurrentUser().then((u) => {
      if (!cancelled) {
        setUser(u);
        setLoading(false);
      }
    });
    const expired = () => setUser(null);
    window.addEventListener('ff:session-expired', expired);
    return () => {
      cancelled = true;
      window.removeEventListener('ff:session-expired', expired);
    };
  }, []);

  // Returns { success, status } where status is 'ok' | 'mfa_required' | 'mfa_setup_required'.
  const login = useCallback(async (username, password) => {
    const res = await authService.login(username, password);
    lastRefresh.current = { at: 0, user: null };
    if (res.success && res.status === 'ok') setUser(res.user);
    return res;
  }, []);

  const verifyMfa = useCallback(async (code) => {
    const res = await authService.mfaVerify(code);
    lastRefresh.current = { at: 0, user: null };
    if (res.success) setUser(res.user);
    return res;
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    lastRefresh.current = { at: 0, user: null };
    setUser(null);
  }, []);

  // Re-reads the account (role + assigned tools) so a change made by the admin shows up without signing in again.
  // A failed request keeps the current user (an expired session is handled by the 'ff:session-expired' event).
  const refreshUser = useCallback((force = false) => {
    if (inflight.current) return inflight.current; // share one request between simultaneous callers
    if (!force && Date.now() - lastRefresh.current.at < 5000 && lastRefresh.current.user) return Promise.resolve(lastRefresh.current.user);
    inflight.current = authService.getCurrentUser().then((u) => {
      lastRefresh.current = { at: Date.now(), user: u };
      if (u) setUser(u);
      return u;
    }).finally(() => { inflight.current = null; });
    return inflight.current;
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    const onVisible = () => { if (document.visibilityState === 'visible') refreshUser(); };
    window.addEventListener('focus', onVisible);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('focus', onVisible);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [user?.id, refreshUser]); // eslint-disable-line react-hooks/exhaustive-deps

  const hasRole = (allowedRoles) => {
    if (!user?.role) return false;
    const list = Array.isArray(allowedRoles) ? allowedRoles : [allowedRoles];
    return list.map((r) => r.toUpperCase()).includes(user.role.toUpperCase());
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        verifyMfa,
        logout,
        hasRole,
        refreshUser,
        hasAccess: (pageKey) => canAccessPage(user?.role, pageKey, user?.tools),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
