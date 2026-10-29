import api, { errorMessage, clearCsrf } from './api.js';

export const authService = {
  async login(username, password) {
    try {
      const { data } = await api.post('/auth/login', { username, password });
      clearCsrf(); // session was rotated by the server
      return { success: true, status: data.status, user: data.user };
    } catch (err) {
      return { success: false, message: errorMessage(err, 'Unable to sign in. Please check your credentials.') };
    }
  },
  async mfaSetup() {
    const { data } = await api.post('/auth/mfa/setup');
    return data; // { secret, otpauth_uri }
  },
  async mfaVerify(code) {
    try {
      const { data } = await api.post('/auth/mfa/verify', { code });
      clearCsrf();
      return { success: true, user: data.user };
    } catch (err) {
      return { success: false, message: errorMessage(err, 'Invalid or expired code.') };
    }
  },
  async logout() {
    try { await api.post('/auth/logout'); } catch { /* session may already be gone */ }
    clearCsrf();
  },
  async getCurrentUser() {
    try {
      const { data } = await api.get('/auth/me');
      return data.user;
    } catch (err) {
      // session expired / revoked: tell the app so it returns to the login page instead of showing a stale UI
      if (err?.response?.status === 401) window.dispatchEvent(new Event('ff:session-expired'));
      return null;
    }
  },
  // Forgot password: emails a signed, expiring, single-use link. Throws on error (use errorMessage(err)).
  async forgotPassword(email) {
    const { data } = await api.post('/auth/forgot-password', { email });
    return data;
  },
  async resetPassword(uid, token, newPassword) {
    const { data } = await api.post('/auth/reset-password', { uid, token, new_password: newPassword });
    return data;
  },
  async changePassword(currentPassword, newPassword) {
    const { data } = await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return data;
  },
};
