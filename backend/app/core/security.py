"""Upload boundaries. Uploaded files are data and are never executed or dereferenced."""
import hashlib
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile
from lxml import etree

SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_.-]")


def sanitize_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = SAFE_FILENAME_RE.sub("_", name)[:180]
    return name if name and not name.startswith(".") else "document" + Path(name).suffix


def calculate_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


async def save_upload(file: UploadFile, path: Path, allowed_extensions: set[str], max_size_bytes: int = None) -> str:
    from .config import settings
    if Path(file.filename or "").suffix.lower() not in allowed_extensions:
        raise HTTPException(400, "Unsupported file format. Allowed: " + ", ".join(sorted(allowed_extensions)))
    size = 0
    limit = max_size_bytes or (settings.MAX_FILE_SIZE_MB * 1024 * 1024)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("wb") as target:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File exceeds {limit // (1024 * 1024)} MB limit.")
                target.write(chunk)
        if not size:
            raise HTTPException(400, "The uploaded file is empty.")
        return calculate_file_hash(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def validate_zip_safety(file_path: Path, max_ratio: float = 100.0, max_size_bytes: int = 200 * 1024 * 1024):
    if not zipfile.is_zipfile(file_path):
        raise HTTPException(400, "Uploaded file is not a valid DOCX archive.")
    try:
        with zipfile.ZipFile(file_path) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            if len(entries) > 10000 or len(set(names)) != len(names):
                raise HTTPException(400, "Archive has duplicate or excessive members.")
            if not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}.issubset(names):
                raise HTTPException(400, "Required Word document package parts are missing.")
            total = 0
            for info in entries:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in PurePosixPath(name).parts or ":" in name:
                    raise HTTPException(400, "Archive contains unsafe file paths.")
                if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                    raise HTTPException(400, "Encrypted or symbolic archive members are unsupported.")
                if "vbaproject" in name.lower() or name.lower().startswith("word/embeddings/"):
                    raise HTTPException(400, "Macro and embedded executable/object packages are not supported.")
                total += info.file_size
                if total > max_size_bytes:
                    raise HTTPException(400, "Decompressed document exceeds maximum allowed size.")
            if total / max(file_path.stat().st_size, 1) > max_ratio:
                raise HTTPException(400, "Compression ratio is suspiciously high (potential zip bomb).")
            for info in entries:
                if not info.filename.endswith((".xml", ".rels")):
                    continue
                data = archive.read(info)
                if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    raise HTTPException(400, "DTD/entity definitions are not permitted in document XML.")
                root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
                if info.filename.endswith(".rels"):
                    for rel in root:
                        if rel.get("TargetMode") == "External":
                            if not rel.get("Type", "").endswith("/hyperlink") or urlparse(rel.get("Target", "")).scheme.lower() not in {"https", "http", "mailto"}:
                                raise HTTPException(400, "Unsafe external relationship: only inert web/email hyperlinks are supported.")
            if archive.testzip():
                raise HTTPException(400, "The document archive has corrupt members.")
    except (zipfile.BadZipFile, etree.XMLSyntaxError, RuntimeError, ValueError) as exc:
        raise HTTPException(400, "Malformed or unreadable DOCX package.") from exc
    return True


def validate_pdf(path: Path):
    import pymupdf
    from .config import settings
    try:
        with pymupdf.open(path) as pdf:
            if not pdf.is_pdf or pdf.needs_pass or not 0 < len(pdf) <= settings.MAX_PDF_PAGES:
                raise ValueError("PDF is encrypted, empty, or exceeds the page limit.")
    except Exception as exc:
        raise HTTPException(400, "PDF is invalid, encrypted, empty, or exceeds the page limit.") from exc


def managed_path(path: str | Path) -> Path:
    from .config import settings
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(settings.STORAGE_DIR.resolve()):
        raise HTTPException(400, "Stored artifact is outside managed storage.")
    return resolved
