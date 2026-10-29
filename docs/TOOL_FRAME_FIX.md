# Why the tools were "dead" inside the portal, and how it was fixed

## 1. How a tool page reaches the browser

```
React page  /html-converter  (pages/ToolFrame.jsx)
   └─ <iframe sandbox="…" src="/api/tools/html-converter/frame">
         └─ Django  views/tools.py::tool_frame
               • reads  backend/tools/GoFiler HTML Converter.html
               • injects tool_bridge.js (forwards generated files to the parent page)
               • answers with a Content-Security-Policy header that ALSO contains a `sandbox` directive
```

So the tool document is sandboxed **twice**: by the `sandbox` attribute on the iframe and by the `sandbox` directive
in the response's CSP. The browser applies the *intersection* — a capability must be allowed by both.
(It is not `dangerouslySetInnerHTML`: the HTML is a real document, so its `<script>` tags do run.)

## 2. The root cause

Both sandboxes were deliberately missing **`allow-same-origin`**. That gives the tool an *opaque origin*
(`origin: null`). It was meant as defence in depth (the tool cannot read the portal's cookies or DOM), but the tools
need things that an opaque origin does not have:

| What the tool does | What happens with an opaque origin |
| --- | --- |
| `localStorage.getItem(...)` on start-up (saved preferences) | throws `SecurityError` → the start-up script aborts → **every button is dead**, including downloads and print |
| Side-by-side / preview panes: nested `<iframe sandbox="allow-same-origin" srcdoc=…>` | the response CSP had `default-src 'none'` and **no `frame-src`** → nested frames are blocked → **blank comparison** |
| `window.print()` | needs `allow-modals` — this one was already present |
| Blob downloads (`<a download href="blob:…">`) | `allow-downloads` was present, but the click handlers were never bound because of the crash above |

Quickest proof: open `/api/tools/html-converter/frame` directly in a new tab (signed in) — the page works, because
only the iframe + CSP combination removes the origin.

## 3. The fix (3 lines)

**`backend/portal/views/tools.py` — `tool_csp()`**
```diff
-"sandbox allow-scripts allow-downloads allow-modals allow-popups allow-forms; "
+"sandbox allow-scripts allow-same-origin allow-downloads allow-modals allow-popups allow-forms; "
 ...
-"font-src https://fonts.gstatic.com data:; img-src data: blob:; worker-src blob:; "
+"font-src https://fonts.gstatic.com data:; img-src data: blob:; worker-src blob:; frame-src 'self' blob: data:; "
```

**`frontend/src/pages/ToolFrame.jsx`**
```diff
-sandbox="allow-scripts allow-downloads allow-modals allow-popups allow-forms"
+sandbox="allow-scripts allow-same-origin allow-downloads allow-modals allow-popups allow-forms"
```

**`backend/tests/test_platform.py`** — the test that asserted `allow-same-origin` is *absent* now asserts it is
present together with `frame-src 'self' blob: data:`.

Everything else stays: `default-src 'none'`, `connect-src blob: data:` (the tool cannot call the API or the
internet), `frame-ancestors` (only the portal may embed the page), `Cache-Control: private, no-store`, the
authentication check, and the bridge that uploads results to *My Documents*.

## 4. Why this is still safe

* The tool pages are **first-party files from this repository**, not user uploads. Same-origin gives them the same
  power as the React app itself — no more.
* The session cookie is **HttpOnly** (unreadable from JavaScript) and the `connect-src` directive still forbids
  network calls from inside the tool frame.
* User-uploaded documents (the *View* previews under My Documents) are a different code path
  (`views/documents.py`) and keep their strict `sandbox` **without** `allow-same-origin`.

## 5. Replacing / updating a tool file

The artifact exports you download from Claude come wrapped in a preview skeleton
(`<!doctype html><html><head>…</head><body>` + the tool's own markup starting at `<title>` + `</body></html>`).
Keep only the tool's own markup and wrap it in a plain document, e.g.

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body>
<title>GoFiler HTML Converter</title> … (the exported content) …
</body></html>
```
then save it over `backend/tools/<name>.html`. Django re-reads the file when its modification time changes (no restart
needed locally; Render redeploys on push). If a new tool loads a library from another CDN, add that host to
`script-src` / `style-src` in `tool_csp()`.

## 6. How to verify

1. `cd backend && python -m pytest tests -q` (the CSP test) and `cd frontend && npm run build`.
2. Sign in → open **GoFiler HTML Converter** → convert a `.docx` → the download must start **and** the file must appear
   under *My Documents*; the preview pane must render; **Print** must open the print dialog.
3. Open **Redline to GoFiler HTML** → load a redline + HTML → side-by-side comparison must render.
4. Browser console (F12 is blocked in production builds — use `npm run dev`, where the deterrent is off):
   no `SecurityError` / `Refused to frame` messages.
