import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    return value.strip().strip('"').strip("'")


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "")
    if not raw:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "")
    if not raw:
        return default
    return float(raw)


class Config:
    SECRET_KEY = _env("SECRET_KEY", "dev-secret") or "dev-secret"
    BASE_DIR = Path(__file__).resolve().parent.parent
    _upload = _env("UPLOAD_DIR", "")
    UPLOAD_DIR = Path(_upload) if _upload else (BASE_DIR / "data" / "uploads")
    CURRENT_IMAGE = UPLOAD_DIR / "current.png"
    PREVIEW_IMAGE = UPLOAD_DIR / "preview.png"

    KINDLE_WIDTH = _env_int("KINDLE_WIDTH", 1072)
    KINDLE_HEIGHT = _env_int("KINDLE_HEIGHT", 1448)
    KINDLE_CONTRAST = _env_float("KINDLE_CONTRAST", 1.15)

    KINDLE_HOST = _env("KINDLE_HOST", "")
    KINDLE_PORT = _env_int("KINDLE_PORT", 2222)
    KINDLE_USER = _env("KINDLE_USER", "root") or "root"
    KINDLE_PASSWORD = _env("KINDLE_PASSWORD", "")
    KINDLE_SSH_TIMEOUT = _env_int("KINDLE_SSH_TIMEOUT", 20)
    KINDLE_REMOTE_PATH = _env(
        "KINDLE_REMOTE_PATH", "/mnt/us/display/current.png"
    ) or "/mnt/us/display/current.png"
    KINDLE_REFRESH_CMD = _env(
        "KINDLE_REFRESH_CMD",
        "/mnt/us/koreader/koreader.sh /mnt/us/display/current.png",
    ) or "/mnt/us/koreader/koreader.sh /mnt/us/display/current.png"

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
