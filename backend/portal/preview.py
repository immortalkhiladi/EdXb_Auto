"""Read-only previews of stored output files. Nothing is regenerated or written back: the stored bytes are only
re-packaged for display (charset label; for ZIP packages, the HTML inside with its images embedded)."""
import io
import re
import zipfile
from html import escape
from posixpath import dirname, join, normpath
from urllib.parse import unquote

IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".bmp": "image/bmp", ".webp": "image/webp"}
MAX_ENTRY = 25 * 1024 * 1024
MAX_TOTAL = 80 * 1024 * 1024
_IMG_SRC = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*)(["\']?)([^"\'\s>]+)\2', re.I | re.S)
_BODY = re.compile(r"<body\b[^>]*>(.*)</body\s*>", re.I | re.S)


def decode_text(data: bytes) -> tuple[str, str]:
    """(text, charset): UTF-8 when the bytes are valid UTF-8, otherwise Windows-1252 (superset of Latin-1)."""
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "windows-1252"


def _inline_images(html: str, zf: zipfile.ZipFile, base: str, budget: list) -> str:
    def repl(m):
        src = unquote(m.group(3).split("#")[0].split("?")[0])
        if src.lower().startswith(("data:", "http:", "https:", "//")):
            return m.group(0)
        path = normpath(join(base, src)).lstrip("/")
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        try:
            info = zf.getinfo(path)
        except KeyError:
            return m.group(0)
        if ext not in IMAGE_MEDIA or info.file_size > MAX_ENTRY or budget[0] + info.file_size > MAX_TOTAL:
            return m.group(0)
        budget[0] += info.file_size
        import base64
        uri = f"data:{IMAGE_MEDIA[ext]};base64,{base64.b64encode(zf.read(info)).decode()}"
        return f'{m.group(1)}"{uri}"'
    return _IMG_SRC.sub(repl, html)


def zip_preview(data: bytes) -> bytes | None:
    """HTML page showing the .htm/.html file(s) of an output package, images embedded. None when the package holds no HTML."""
    zf = zipfile.ZipFile(io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data)
    pages = sorted((i for i in zf.infolist() if not i.is_dir() and i.filename.lower().endswith((".htm", ".html"))
                    and i.file_size <= MAX_ENTRY), key=lambda i: i.filename.lower())
    if not pages:
        return None
    budget = [0]
    parts = []
    for i in pages:
        html, _ = decode_text(zf.read(i))
        parts.append((i.filename, _inline_images(html, zf, dirname(i.filename), budget)))
    if len(parts) == 1:
        return parts[0][1].encode("utf-8")
    out = ['<!DOCTYPE html><html><head><meta charset="utf-8"><title>Package preview</title></head><body>']
    for n, (name, html) in enumerate(parts):
        m = _BODY.search(html)
        out.append(f'<div style="font:12px Arial,sans-serif;color:#555;background:#eee;padding:4px 8px;margin:{0 if n == 0 else 16}px 0 8px">'
                   f'{escape(name)}</div>{m.group(1) if m else html}')
    out.append("</body></html>")
    return "".join(out).encode("utf-8")
