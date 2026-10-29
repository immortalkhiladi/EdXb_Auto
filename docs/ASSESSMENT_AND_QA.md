# Repository assessment, change log and QA report — EDGAR Agents LLC rebrand (26 Oct 2026)

## 1. Assessment of the repository as received

| Area | Finding |
| --- | --- |
| Frontend | React 19, Vite 8, Tailwind CSS 4 (`@tailwindcss/vite`), react-router 7, lucide-react, axios. Entry `frontend/src/main.jsx`; routes in `src/routes/AppRoutes.jsx`; UI access rules in `src/utils/rbac.js`. |
| Backend | Django 5.2 + gunicorn, PostgreSQL via psycopg2 (SQLite for local/tests), Argon2id passwords, TOTP MFA, WhiteNoise serving `frontend/dist`. Entry `backend/manage.py` / `config/wsgi.py`; API in `backend/portal/urls.py`. |
| Auth | Session cookie (HttpOnly, SameSite=Strict) + CSRF header; roles ADMIN / MD / USER; per-user tool assignment (`UserToolAccess`); lockout, rate limits, audit log. |
| Database | `config/settings/base.py` reads `DB_*`; production refuses `localhost` and insecure settings. Files stored in PostgreSQL chunks (`StoredFile`). |
| Deployment | `render.yaml` blueprint, `deploy/render/build.sh`, `backend/startup.sh`, health endpoint `/api/health`. VM scripts in `deploy/vm/`. |
| Tests | 66 pytest tests (`backend/tests`), 3 `node --test` files (16 assertions) in `frontend/src/utils`. |
| Git | **Not a Git repository** (no `.git`); nothing has ever been committed, so there is no history to scrub. |
| Secrets | `backend/.env` is present but identical to `.env.example` (local placeholder values only). No keys/tokens/certificates found. |

### What was broken
* `backend/portal/tools.py` registered **five** tools but only **three** HTML files existed (`10-D_Exhibit_Builder.html`
  and `ex103_excel_to_xml.html` are missing). Opening those two tools raised `FileNotFoundError` (HTTP 500), the sidebar
  and dashboard still advertised them, and the test-suite expected them.
* The whole UI, emails, MFA issuer, metadata, logo, contact details and marketing copy were Federal Filings LLC.
* `frontend/src/assets/images/login_skyscraper_bg_*.jpg` (1 MB) and `QuoteModal.jsx` (a fake quote form with no
  backend) were Federal Filings marketing content.
* `render.yaml` provisioned a paid persistent disk that the database storage backend does not use.
* `README.md` claimed seeded users get random passwords; `seed_users` actually sets fixed dev passwords.

### The "Backend Tools" (all client-side HTML, verified by inspection)
| Tool | Purpose | Inputs | Outputs | Dependencies | Runs | Env vars / auth |
| --- | --- | --- | --- | --- | --- | --- |
| `Redline_to_GoFiler_HTML_v2.html` | applies Word Track-Changes redlines to an existing GoFiler HTML | `.docx` + `.htm/.html` | updated HTML, review/manual-change reports | in-page JS, Google Fonts, `localStorage` (prefs) | browser | none; served only to signed-in users with the tool assigned |
| `GoFiler HTML Converter.html` | converts Word documents to GoFiler-coded SEC HTML | `.docx` (`.htm/.html` allowed) | HTML + processing report | JSZip (cdnjs), Google Fonts, `localStorage` | browser | same |
| `PDF converter.html` | converts decks/PDFs to EDGAR HTML packages | `.pdf .pptx .ppt` | `.zip` package | JSZip + pdf.js (cdnjs), Google Fonts | browser | same |
| `SEC_Form_Type_Dashboard.html` (attached, newly integrated) | SEC form reference cards, 4-way comparison, 2026-rule notes, filing-fee and XBRL training, **upload validator** | `.htm .html .txt .xml .zip` (validator) | none (on-screen results only) | JSZip (cdnjs), inline `onclick` handlers | browser | same |

None of the tools needs a server process, OS package, licensed software or network call to the SEC — they are fully
cloud-compatible and are served through the existing sandboxed-iframe mechanism (`views/tools.py`, `tool_bridge.js`).
The dashboard uses no storage and makes no network requests; the converters' `localStorage` preferences are unavailable
inside the opaque-origin sandbox and degrade silently (as before).

## 2. Changes implemented

**Tool registry / integration**
* `backend/portal/tools.py`: removed the two missing tools; added `sec-form-dashboard` → `backend/tools/SEC_Form_Type_Dashboard.html`
  (copied from the attachment with the artifact preview wrapper stripped). Label of `html-converter` → "GoFiler HTML Converter".
* `backend/portal/migrations/0005_sec_form_dashboard_access.py`: existing USER accounts receive the new tool (admin can revoke).
* `backend/portal/management/commands/seed_users.py`: example limited user now gets the first two current tools.
* Frontend: `utils/rbac.js` (pages + slug map), `components/layout/Sidebar.jsx`, `pages/Dashboard.jsx`, `routes/AppRoutes.jsx`
  (route `/sec-forms`), `components/admin/ToolAccessPanel.jsx` text.
* Tests updated: `backend/tests/{conftest,test_documents,test_tool_access,test_platform,test_access_and_passwords}.py`,
  `frontend/src/utils/rbac.test.js`.

**Rebrand**
* Strings: `frontend/index.html` (title, meta, `noindex`), `Logo.jsx` (new EA monogram + "EDGAR Agents LLC" wordmark,
  tagline "File with confidence" from the public site), `Navbar.jsx`, `Topbar.jsx` (help text), `Settings.jsx`,
  `NotFound.jsx`, `data/teamData.js` (only verified public identifiers: website + LinkedIn), `backend/portal/views/auth.py`
  (MFA issuer, reset email), `config/settings/base.py` (`DEFAULT_FROM_EMAIL`), `.env`/`.env.example`/`.env.production.example`,
  `package.json`/lockfile name, `render.yaml` service/DB names, `public/theme-init.js` + `ThemeContext.jsx` storage key.
* Removed: `FederalFilingsLogo.jsx`, `QuoteModal.jsx`, the skyscraper background image, Federal Filings phone/CIK/address.
* Design system: `frontend/src/index.css` — `@theme` tokens (`--color-ink-*`) remap the legacy `purple-*`/`orange-*`
  brand utilities to a neutral ink palette; new `.ea-primary` surface replaces the orange→rose→purple gradient
  (19 occurrences across 10 files); `rose` remains the error/destructive colour, `emerald` success. Neon page/sidebar
  backgrounds replaced by neutral surfaces (light + dark).
* `pages/Login.jsx` rewritten: two-panel enterprise layout (brand panel + form), labelled inputs, show/hide password
  (`aria-pressed`), forgot-password, MFA step, virtual keypad and assistance dialog retained; loading/error/active-session
  states; responsive (single column below `lg`); dialogs carry `role="dialog"`/`aria-modal`.
* Kept on purpose: internal identifiers `ff-tool` (postMessage source), `ff:session-expired` event, `ff-page/ff-card/ff-side/ff-nav-glass`
  CSS class names (not user-visible; renaming them touches ~15 files and the backend test that asserts the bridge is injected).
* Not changed: `docs/CHANGES.md` and `docs/TEST_RESULTS.md` are historical records of earlier releases.

**Deployment readiness**
* `render.yaml`: disk removed (files live in PostgreSQL), names rebranded.
* `.github/workflows/ci.yml`: pytest + `npm test` + `npm run build` on every push.
* `docs/DEPLOYMENT_GUIDE.md` (new), `README.md` (rewritten), `docs/RENDER_DEPLOYMENT.md`, `docs/ARCHITECTURE.md`,
  `docs/OPERATIONS.md`, `README_POSTGRESQL.md` aligned; `.gitignore` tidied.
* Removed from the deliverable: `backend/.venv` (a Windows virtualenv, 93 MB) and `__pycache__` directories.

## 3. QA — what was actually run in this session

The build sandbox **could not reach PyPI or the npm registry** (package downloads refused by the egress policy), so
Django and the Vite toolchain could not be installed. Consequently:

| Check | Result |
| --- | --- |
| `node --test` (devtoolsGuard, passwordPolicy, rbac) | **16/16 passed** |
| esbuild compile of the whole React app (`src/main.jsx`, JSX + import resolution, externals for npm packages) | **passed**, 0 errors; bundle contains no "Federal" string |
| `python -m py_compile` of every backend `.py` file | **passed** |
| Tool registry ↔ files on disk | all four HTML files present |
| Grep for `Federal Filings` / `FederalFiling` / `Fedfyler` / `federalfilings` outside historical docs | **0 matches** in source |
| Grep for the removed slugs/pages (`ex103`, `10d-`, `exhibit10d`) in source and tests | **0 matches** |
| Backend pytest suite (66 tests) | **NOT RUN here** (Django not installable) — run `cd backend && pip install -r requirements-dev.txt && python -m pytest tests -q`; CI runs it on the first push |
| `npm run build` (Vite/Tailwind production build) | **NOT RUN here** — run `cd frontend && npm ci && npm run build`; CI runs it |
| Visual check of login/dashboard, mobile layout, browser console | **NOT performed** (no build) — see acceptance checklist in `DEPLOYMENT_GUIDE.md` §7.5 |
| pip-audit / npm audit | not run (no registry access) — part of `deploy/render/pre-release-check.sh` |

Expectations for the first CI run: the test edits mirror the slug/label changes one-to-one; the only behavioural
change under test is that `html-converter` is now the default tool in `conftest.process()` with a `.docx` original.
If a test fails, it is most likely in `test_documents.py` around original-file validation (`macro.docx` with Excel
contents must still be rejected with 422 — it is, by the OOXML content check).

## 4. Pre-existing issues not addressed (documented, unrelated to this change)
* DevTools deterrents are cosmetic (documented in `docs/SECURITY.md`).
* The tool pages load JSZip/pdf.js/fonts from public CDNs; an offline/air-gapped deployment would need them vendored.
* `backend/tools/*.html` are large single files (0.3–0.7 MB) maintained outside the React build; no tests cover their internals.
* Seeded dev passwords are well-known (refused under production settings, but do not run `seed_users` against a production DB).

## 5. Status
* GitHub publishing: **not performed** (no repository/credentials in this session) — exact steps in the guide §6.
* Production deployment: **not performed** (requires the user's Render account and would incur cost) — guide §7.
* Brand inputs still needed from EDGAR Agents LLC: official colour values, logo SVG (light + dark), support phone/email
  for the assistance dialog, production domain and DNS access, SMTP credentials for password-reset email.

## 6. Update 28 Oct 2026 — tool frames
* Tools were dead inside the portal (no downloads/print, blank comparison): the opaque-origin sandbox broke `localStorage`
  and nested preview frames. Fixed by adding `allow-same-origin` (iframe + CSP) and `frame-src 'self' blob: data:` —
  full explanation in `docs/TOOL_FRAME_FIX.md`. Test updated.
* `GoFiler HTML Converter.html` and `Redline_to_GoFiler_HTML_v2.html` replaced with the newly supplied versions
  (preview wrapper stripped, wrapped as standalone documents).
* Remaining 10-D / ex103 mentions removed from migration 0003 constants and historical docs.
