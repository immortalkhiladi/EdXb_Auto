"""Upload validation: inspects file CONTENT (signatures, archive structure), not just names."""
import codecs
import io
import re
import zipfile
from dataclasses import dataclass

from django.conf import settings

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# extension -> (media type used when served, previewable inline?)
MEDIA = {
    ".pdf": ("application/pdf", True),
    ".htm": ("text/html", True),
    ".html": ("text/html", True),
    ".xml": ("text/plain", True),   # served as text, never executed
    ".txt": ("text/plain", True),
    ".csv": ("text/plain", True),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False),
    ".xlsm": ("application/vnd.ms-excel.sheet.macroEnabled.12", False),
    ".xls": ("application/vnd.ms-excel", False),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", False),
    ".ppt": ("application/vnd.ms-powerpoint", False),
    ".zip": ("application/zip", True),   # inline = rendered package preview (views/documents.py)
}
SUPPORTED = set(MEDIA)
OOXML_MARKER = {".xlsx": "xl/", ".xlsm": "xl/", ".docx": "word/", ".pptx": "ppt/"}


class ValidationError(Exception):
    """Message is safe to show to the client."""


@dataclass
class Checked:
    filename: str
    ext: str
    data: bytes


def max_upload_bytes() -> int:
    return settings.MAX_UPLOAD_MB * 1024 * 1024


def safe_filename(name) -> str:
    """Basename only; strips path components, control chars and odd symbols; keeps the extension."""
    name = (name or "file").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"[^A-Za-z0-9._ ()\-]", "_", name).strip(" .") or "file"
    if len(name) > 150:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 150 - len(ext) - 1] + dot + ext) if dot else name[:150]
    return name


def ext_of(name: str) -> str:
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


def read_limited(upload, limit: int | None = None) -> bytes:
    """Reads an uploaded file chunk by chunk and aborts as soon as the size limit is exceeded."""
    limit = limit or max_upload_bytes()
    buf = bytearray()
    for chunk in upload.chunks():
        buf.extend(chunk)
        if len(buf) > limit:
            raise ValidationError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.")
    return bytes(buf)


def _check_zip(data) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data)
        infos = zf.infolist()
    except zipfile.BadZipFile:
        raise ValidationError("File is not a valid archive/Office document.")
    if len(infos) > settings.MAX_ZIP_ENTRIES:
        raise ValidationError("Archive contains too many entries.")
    total = 0
    for i in infos:
        n = i.filename
        if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
            raise ValidationError("Archive contains unsafe paths.")
        total += i.file_size
        if i.compress_size and i.file_size / max(i.compress_size, 1) > 1000:
            raise ValidationError("Archive compression ratio is suspicious.")
    if total > settings.MAX_ZIP_UNCOMPRESSED_MB * 1024 * 1024:
        raise ValidationError("Archive expands to too large a size.")
    return zf


def check_content(filename: str, data: bytes, allowed: set | None = None) -> Checked:
    name = safe_filename(filename)
    ext = ext_of(name)
    if ext not in SUPPORTED or (allowed is not None and ext not in allowed):
        raise ValidationError(f"File type '{ext or 'unknown'}' is not allowed here.")
    if not data:
        raise ValidationError("File is empty.")

    if ext == ".pdf":
        if not data.lstrip()[:5] == b"%PDF-":
            raise ValidationError("File content is not a PDF.")
    elif ext in OOXML_MARKER or ext == ".zip":
        if data[:4] != b"PK\x03\x04":
            raise ValidationError("File content does not match its extension.")
        zf = _check_zip(data)
        names = zf.namelist()
        if ext in OOXML_MARKER and not ("[Content_Types].xml" in names and any(n.startswith(OOXML_MARKER[ext]) for n in names)):
            raise ValidationError("File is not a valid Office document.")
    elif ext in (".xls", ".ppt"):
        if data[:8] != OLE:
            raise ValidationError("File content does not match its extension.")
    elif ext in (".htm", ".html", ".xml", ".txt", ".csv"):
        if b"\x00" in data[:8192]:
            raise ValidationError("File content does not look like text.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        if ext in (".htm", ".html", ".xml") and not text.lstrip().startswith(("<", "\ufeff")):
            raise ValidationError("File content does not look like markup.")
    return Checked(name, ext, data)


@dataclass
class CheckedFile:
    filename: str
    ext: str
    size: int


HEAD = 8192


def check_upload(upload, filename: str | None = None, allowed: set | None = None) -> CheckedFile:
    """Same rules as check_content, but inspects the uploaded file in place (size from the upload, a small head for
    signatures, the zip index for archives) so the file is never read into memory or copied just to be validated."""
    name = safe_filename(filename or upload.name)
    limit = max_upload_bytes()
    size = upload.size
    if size > limit:
        raise ValidationError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.")
    ext = ext_of(name)
    if ext not in SUPPORTED or (allowed is not None and ext not in allowed):
        raise ValidationError(f"File type '{ext or 'unknown'}' is not allowed here.")
    if not size:
        raise ValidationError("File is empty.")

    upload.seek(0)
    head = upload.read(HEAD)
    upload.seek(0)
    if ext == ".pdf":
        if not head.lstrip()[:5] == b"%PDF-":
            raise ValidationError("File content is not a PDF.")
    elif ext in OOXML_MARKER or ext == ".zip":
        if head[:4] != b"PK\x03\x04":
            raise ValidationError("File content does not match its extension.")
        zf = _check_zip(upload)
        names = zf.namelist()
        if ext in OOXML_MARKER and not ("[Content_Types].xml" in names and any(n.startswith(OOXML_MARKER[ext]) for n in names)):
            raise ValidationError("File is not a valid Office document.")
        upload.seek(0)
    elif ext in (".xls", ".ppt"):
        if head[:8] != OLE:
            raise ValidationError("File content does not match its extension.")
    elif ext in (".htm", ".html", ".xml", ".txt", ".csv"):
        if b"\x00" in head:
            raise ValidationError("File content does not look like text.")
        try:  # tolerant of a multi-byte character cut off at the end of the head
            text = codecs.getincrementaldecoder("utf-8-sig")().decode(head)
        except UnicodeDecodeError:
            text = head.decode("latin-1")
        if ext in (".htm", ".html", ".xml") and not text.lstrip().startswith(("<", "\ufeff")):
            raise ValidationError("File content does not look like markup.")
    return CheckedFile(name, ext, size)
