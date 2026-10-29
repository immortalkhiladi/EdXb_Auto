"""The workflow tools. Each one is a self-contained browser page in backend/tools/ (all processing happens in the
user's browser); their UIs are served only to authenticated users (views/tools.py) and their outputs are recorded
through POST /api/process/<slug>. Their processing logic is unchanged."""
from dataclasses import dataclass

from .validation import SUPPORTED


@dataclass(frozen=True)
class Tool:
    slug: str
    label: str
    html_file: str
    input_exts: frozenset
    output_exts: frozenset = frozenset(SUPPORTED)


TOOLS = {
    t.slug: t
    for t in [
        Tool("redline-to-gofiler-html", "Redline to GoFiler HTML", "Redline_to_GoFiler_HTML_v2.html", frozenset({".htm", ".html", ".docx"})),
        Tool("html-converter", "GoFiler HTML Converter", "GoFiler HTML Converter.html", frozenset({".htm", ".html", ".docx"})),
        Tool("ppt-pdf-converter", "PPT and PDF Converter", "PDF converter.html", frozenset({".pdf", ".pptx", ".ppt"})),
        # Reference / validator dashboard: it reads uploads for checks and never produces a download.
        Tool("sec-form-dashboard", "SEC Form Type Dashboard", "SEC_Form_Type_Dashboard.html",
             frozenset({".htm", ".html", ".txt", ".xml", ".zip"})),
    ]
}
