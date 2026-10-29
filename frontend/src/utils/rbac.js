// UI-level page access (usability only). The BACKEND enforces the real permissions on every request.
export const APP_ROLES = ['ADMIN', 'MD', 'USER'];

export const PAGES = {
  dashboard:   { path: '/dashboard' },
  documents:   { path: '/documents' },
  allDocuments: { path: '/all-documents' },
  redline:     { path: '/redline-gofiler' },
  gofilerhtml: { path: '/html-converter' },
  converter:   { path: '/converter' },
  secforms:    { path: '/sec-forms' },
  admin:       { path: '/admin' },
  settings:    { path: '/settings' },
};

const USER_PAGES = ['dashboard', 'documents', 'redline', 'gofilerhtml', 'converter', 'secforms', 'settings'];

export const ROLE_PAGES = {
  ADMIN: [...USER_PAGES, 'allDocuments', 'admin'], // everything, incl. every user's documents and user management
  MD: [...USER_PAGES, 'allDocuments'],             // every user's documents (view/download), no user management
  USER: USER_PAGES,                                // own documents only
};

// Tool pages -> backend tool slugs. A USER also needs the tool to be assigned to them (user.tools, set by the ADMIN);
// ADMIN and MD always have every tool. The backend enforces this independently on every request.
export const TOOL_PAGE_SLUG = {
  redline: 'redline-to-gofiler-html',
  gofilerhtml: 'html-converter',
  converter: 'ppt-pdf-converter',
  secforms: 'sec-form-dashboard',
};

export function canAccessPage(role, pageKey, tools) {
  const r = String(role || '').toUpperCase();
  if (!(ROLE_PAGES[r] || []).includes(pageKey)) return false;
  const slug = TOOL_PAGE_SLUG[pageKey];
  if (!slug || r === 'ADMIN' || r === 'MD') return true;
  return Array.isArray(tools) && tools.includes(slug);
}
