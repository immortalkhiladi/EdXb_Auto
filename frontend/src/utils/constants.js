// Same-origin by default ('/api': Django serves the UI, or Vite proxies it in dev).
// For split hosting (UI and API on different origins) set VITE_API_BASE_URL at BUILD time,
// e.g. https://api.example.com/api . It is a public address, not a secret.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export const ROLES = { ADMIN: 'ADMIN', USER: 'USER' };

export const DOCUMENT_STATUSES = ['completed', 'processing', 'failed'];

// Maps the sidebar/route tool ids to the backend tool slugs (defined once in rbac.js).
export { TOOL_PAGE_SLUG as TOOL_SLUGS } from './rbac.js';
