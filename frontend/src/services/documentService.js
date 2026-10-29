import api from './api.js';
import { API_BASE_URL } from '../utils/constants.js';

export const documentService = {
  async list(params = {}, admin = false) {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));
    const { data } = await api.get(admin ? '/admin/documents' : '/documents', { params: clean });
    return data;
  },
  remove: (id) => api.delete(`/documents/${id}`),
  viewUrl: (id, kind = 'output') => `${API_BASE_URL}/documents/${id}/view?kind=${kind}`,
  downloadUrl: (id, kind = 'output') => `${API_BASE_URL}/documents/${id}/download?kind=${kind}`,
  async upload(slug, output, original, onProgress) {
    const form = new FormData();
    form.append('output', output, output.name);
    if (original) form.append('original', original, original.name);
    const { data } = await api.post(`/process/${slug}`, form, {
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
    });
    return data.document;
  },
};

export const adminService = {
  overview: async () => (await api.get('/admin/overview')).data,
  users: async () => (await api.get('/admin/users')).data.items,
  createUser: async (body) => (await api.post('/admin/users', body)).data.user,
  updateUser: async (id, body) => (await api.patch(`/admin/users/${id}`, body)).data.user,
  deleteUser: async (id) => (await api.delete(`/admin/users/${id}`)).data,
  toolAccess: async () => (await api.get('/admin/tool-access')).data,
  saveToolAccess: async (changes) => (await api.put('/admin/tool-access', { changes })).data,
  auditLogs: async (params) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));
    return (await api.get('/admin/audit-logs', { params: clean })).data;
  },
};
