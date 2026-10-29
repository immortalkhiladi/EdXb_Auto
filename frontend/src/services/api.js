import axios from 'axios';
import { API_BASE_URL } from '../utils/constants.js';

// Authentication = Django server-side session in an HttpOnly, SameSite=Strict cookie (JavaScript cannot read it).
// CSRF protection = Django's token, fetched from GET /auth/csrf and sent in the X-CSRFToken header on writes.
let csrfToken = null;
let csrfPromise = null;

export function clearCsrf() {
  csrfToken = null; // the token rotates when the session changes (login / logout)
}

export async function fetchCsrf(force = false) {
  if (csrfToken && !force) return csrfToken;
  if (!csrfPromise || force) {
    csrfPromise = axios
      .get(`${API_BASE_URL}/auth/csrf`, { withCredentials: true })
      .then((r) => (csrfToken = r.data.csrfToken))
      .finally(() => { csrfPromise = null; });
  }
  return csrfPromise;
}

const api = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

api.interceptors.request.use(async (config) => {
  const method = (config.method || 'get').toLowerCase();
  if (!['get', 'head', 'options'].includes(method)) {
    config.headers['X-CSRFToken'] = await fetchCsrf();
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config;
    const status = error.response?.status;
    // token went stale (session rotated in another tab, etc.): fetch a new one and retry once
    if (status === 403 && error.response?.data?.detail === 'CSRF verification failed.' && cfg && !cfg._csrfRetried) {
      cfg._csrfRetried = true;
      clearCsrf();
      // The CSRF token lives in the session: when the session itself has expired, re-sending (e.g. a large upload)
      // would only end in 401. Check first and go to the login page instead.
      try {
        await axios.get(`${API_BASE_URL}/auth/me`, { withCredentials: true });
      } catch (e) {
        if (e?.response?.status === 401) window.dispatchEvent(new Event('ff:session-expired'));
        return Promise.reject(error);
      }
      cfg.headers['X-CSRFToken'] = await fetchCsrf(true);
      return api(cfg);
    }
    const url = cfg?.url || '';
    if (status === 401 && !url.startsWith('/auth/')) {
      window.dispatchEvent(new Event('ff:session-expired'));
    }
    return Promise.reject(error);
  }
);

export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const d = err?.response?.data?.detail;
  if (typeof d === 'string') return d;
  return fallback;
}

export default api;
