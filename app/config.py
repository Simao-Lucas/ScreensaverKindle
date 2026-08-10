import os
import re
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    value = value.replace("\ufeff", "").strip().strip('"').strip("'")
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "")
    if not raw:
        return default
    match = re.match(r"^-?\d+", raw)
    if not match:
        return default
    try:
        return int(match.group(0))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "")
    if not raw:
        return default
    raw = raw.replace(",", ".")
    match = re.match(r"^-?\d+(\.\d+)?", raw)
    if not match:
        return default
    try:
        return float(match.group(0))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = _env("SECRET_KEY", "dev-secret") or "dev-secret"
    BASE_DIR = Path(__file__).resolve().parent.parent
    _upload = _env("UPLOAD_DIR", "")
    UPLOAD_DIR = Path(_upload) if _upload else (BASE_DIR / "data" / "uploads")
    CURRENT_IMAGE = UPLOAD_DIR / "current.png"
    PREVIEW_IMAGE = UPLOAD_DIR / "preview.png"

    BOOKS_DIR = Path(_env("BOOKS_DIR", "") or (BASE_DIR / "data" / "books"))
    CURRENT_BOOK_META = BOOKS_DIR / "current.json"

    KINDLE_WIDTH = _env_int("KINDLE_WIDTH", 1072)
    KINDLE_HEIGHT = _env_int("KINDLE_HEIGHT", 1448)
    KINDLE_CONTRAST = _env_float("KINDLE_CONTRAST", 1.15)

    KINDLE_HOST = _env("KINDLE_HOST", "")
    KINDLE_PORT = _env_int("KINDLE_PORT", 2222)
    KINDLE_USER = _env("KINDLE_USER", "root") or "root"
    KINDLE_PASSWORD = _env("KINDLE_PASSWORD", "")
    KINDLE_SSH_KEY = _env("KINDLE_SSH_KEY", "/keys/id_rsa")
    KINDLE_SSH_TIMEOUT = _env_int("KINDLE_SSH_TIMEOUT", 20)
    KINDLE_REMOTE_PATH = _env(
        "KINDLE_REMOTE_PATH", "/mnt/us/screensaver/current.png"
    ) or "/mnt/us/screensaver/current.png"
    KINDLE_REFRESH_CMD = _env("KINDLE_REFRESH_CMD", "")
    KINDLE_CLEAR_SCREENSAVER_DIR = _env_bool("KINDLE_CLEAR_SCREENSAVER_DIR", True)
    KINDLE_DOCUMENTS_DIR = _env(
        "KINDLE_DOCUMENTS_DIR", "/mnt/us/documents"
    ) or "/mnt/us/documents"

    # Limite global alto o bastante para livros (imagens são bem menores)
    MAX_CONTENT_LENGTH = _env_int("BOOK_MAX_CONTENT_LENGTH", 200 * 1024 * 1024)
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
    BOOK_INPUT_EXTENSIONS = {
        "epub",
        "pdf",
        "mobi",
        "azw",
        "azw3",
        "docx",
        "html",
        "htm",
        "rtf",
        "txt",
        "fb2",
        "odt",
        "cbz",
    }
    BOOK_OUTPUT_FORMATS = ("epub", "pdf", "mobi", "fb2", "txt")
    EBOOK_CONVERT_BIN = _env("EBOOK_CONVERT_BIN", "ebook-convert") or "ebook-convert"
    EBOOK_META_BIN = _env("EBOOK_META_BIN", "ebook-meta") or "ebook-meta"
    EBOOK_CONVERT_TIMEOUT = _env_int("EBOOK_CONVERT_TIMEOUT", 600)
