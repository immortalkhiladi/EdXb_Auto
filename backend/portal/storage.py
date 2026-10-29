"""Private object storage. Files are addressed only by random keys; the browser never sees a key or path."""
import io
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from django.conf import settings
from django.db import transaction

CHUNK = 1024 * 1024


def new_key(kind: str) -> str:
    """kind: originals | outputs. Random and never derived from user input."""
    now = datetime.now(timezone.utc)
    return f"{kind}/{now:%Y/%m}/{secrets.token_hex(16)}"


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):  # path-traversal guard
            raise ValueError("invalid storage key")
        return p

    def _create(self, key: str):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")

    def put(self, key: str, data: bytes) -> None:
        p, f = self._create(key)
        with f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())  # on disk before the upload is reported as saved

    def put_file(self, key: str, upload) -> int:
        """Streams an uploaded file to storage chunk by chunk (no whole-file copy in memory). Returns the bytes written;
        a partial file is removed if anything fails."""
        p, f = self._create(key)
        written = 0
        try:
            with f:
                for chunk in upload.chunks(CHUNK):
                    f.write(chunk)
                    written += len(chunk)
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            p.unlink(missing_ok=True)
            raise
        return written

    def stream(self, key: str) -> Iterator[bytes]:
        with open(self._path(key), "rb") as f:
            while chunk := f.read(CHUNK):
                yield chunk

    def open(self, key: str):
        """Seekable read-only file object (lets zipfile read only the entries it needs instead of the whole file)."""
        return open(self._path(key), "rb")

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def healthy(self) -> bool:
        return self.root.is_dir() and os.access(self.root, os.W_OK)


DB_CHUNK = 1024 * 1024  # rows of 1 MB: small enough for any PostgreSQL setting, big enough to keep row counts low


class _DbReader(io.RawIOBase):
    """Seekable read-only file object over the chunk rows. Only the chunks that are actually read are fetched, so
    zipfile can open a ZIP package without loading the whole archive."""

    def __init__(self, meta):
        self.meta, self.pos = meta, 0
        self._cache = (None, b"")

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.meta.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def _chunk(self, seq):
        if self._cache[0] != seq:
            from .models import StoredFileChunk
            row = StoredFileChunk.objects.filter(file_id=self.meta.key, seq=seq).values_list("data", flat=True).first()
            self._cache = (seq, bytes(row) if row is not None else b"")
        return self._cache[1]

    def readinto(self, b):
        want = min(len(b), self.meta.size - self.pos)
        if want <= 0:
            return 0
        n = 0
        while n < want:
            seq, off = divmod(self.pos, self.meta.chunk_size)
            part = self._chunk(seq)[off: off + (want - n)]
            if not part:
                break
            b[n:n + len(part)] = part
            n += len(part)
            self.pos += len(part)
        return n


class DatabaseStorage:
    """DEFAULT. Files live in the database next to the rest of the data, so they survive restarts, redeploys and
    new instances, and are covered by the same backups. If a key is not in the database (a file saved before this
    switch) it is still served from the old local directory when that file exists."""

    def __init__(self, legacy: "LocalStorage | None" = None):
        self.legacy = legacy

    @staticmethod
    def _models():
        from .models import StoredFile, StoredFileChunk
        return StoredFile, StoredFileChunk

    def _meta(self, key):
        StoredFile, _ = self._models()
        return StoredFile.objects.filter(key=key).first()

    def _write(self, key: str, chunks) -> int:
        StoredFile, Chunk = self._models()
        total = 0
        with transaction.atomic():  # all chunks or nothing: a half-written file can never be read
            meta = StoredFile.objects.create(key=key, size=0, chunk_size=DB_CHUNK)
            buf, seq = bytearray(), 0
            for piece in chunks:
                buf.extend(piece)
                total += len(piece)
                while len(buf) >= DB_CHUNK:
                    Chunk.objects.create(file=meta, seq=seq, data=bytes(buf[:DB_CHUNK]))
                    del buf[:DB_CHUNK]
                    seq += 1
            if buf or seq == 0:
                Chunk.objects.create(file=meta, seq=seq, data=bytes(buf))
            StoredFile.objects.filter(key=key).update(size=total)
        return total

    def put(self, key: str, data: bytes) -> None:
        self._write(key, [data])

    def put_file(self, key: str, upload) -> int:
        return self._write(key, upload.chunks(DB_CHUNK))

    def stream(self, key: str) -> Iterator[bytes]:
        meta = self._meta(key)
        if meta is None:
            if self.legacy:
                yield from self.legacy.stream(key)
                return
            raise FileNotFoundError(key)
        _, Chunk = self._models()
        for seq in range(((meta.size + meta.chunk_size - 1) // meta.chunk_size) or 1):
            data = Chunk.objects.filter(file_id=key, seq=seq).values_list("data", flat=True).first()
            if data:
                yield bytes(data)

    def open(self, key: str):
        meta = self._meta(key)
        if meta is None:
            if self.legacy:
                return self.legacy.open(key)
            raise FileNotFoundError(key)
        return io.BufferedReader(_DbReader(meta), buffer_size=64 * 1024)

    def delete(self, key: str) -> None:
        StoredFile, _ = self._models()
        StoredFile.objects.filter(key=key).delete()  # chunks cascade
        if self.legacy:
            self.legacy.delete(key)

    def exists(self, key: str) -> bool:
        StoredFile, _ = self._models()
        return StoredFile.objects.filter(key=key).exists() or bool(self.legacy and self.legacy.exists(key))

    def healthy(self) -> bool:
        try:
            StoredFile, _ = self._models()
            StoredFile.objects.exists()
            return True
        except Exception:
            return False


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        local = LocalStorage(settings.STORAGE_LOCAL_DIR)
        backend = getattr(settings, "STORAGE_BACKEND", "database")
        _storage = local if backend == "local" else DatabaseStorage(legacy=local)
    return _storage


def reset_storage():  # tests
    global _storage
    _storage = None
