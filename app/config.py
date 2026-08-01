import os
from pathlib import Path


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    BASE_DIR = Path(__file__).resolve().parent.parent
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
    CURRENT_IMAGE = UPLOAD_DIR / "current.png"
    PREVIEW_IMAGE = UPLOAD_DIR / "preview.png"

    KINDLE_WIDTH = int(os.getenv("KINDLE_WIDTH", "1072"))
    KINDLE_HEIGHT = int(os.getenv("KINDLE_HEIGHT", "1448"))
    KINDLE_CONTRAST = float(os.getenv("KINDLE_CONTRAST", "1.15"))

    KINDLE_HOST = os.getenv("KINDLE_HOST", "")
    KINDLE_PORT = int(os.getenv("KINDLE_PORT", "2222"))
    KINDLE_USER = os.getenv("KINDLE_USER", "root")
    KINDLE_PASSWORD = os.getenv("KINDLE_PASSWORD", "")
    KINDLE_SSH_TIMEOUT = int(os.getenv("KINDLE_SSH_TIMEOUT", "20"))
    KINDLE_REMOTE_PATH = os.getenv(
        "KINDLE_REMOTE_PATH", "/mnt/us/display/current.png"
    )
    KINDLE_REFRESH_CMD = os.getenv(
        "KINDLE_REFRESH_CMD",
        "/mnt/us/koreader/koreader.sh /mnt/us/display/current.png",
    )

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
