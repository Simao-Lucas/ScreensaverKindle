from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageOps


class BookMetaError(Exception):
    """Raised when ebook-meta read/apply fails."""


_FIELD_MAP = {
    "title": "title",
    "author(s)": "authors",
    "authors": "authors",
    "publisher": "publisher",
    "series": "series",
    "tags": "tags",
    "languages": "language",
    "language": "language",
    "comments": "comments",
    "identifiers": "identifiers",
}


def empty_metadata() -> dict[str, str]:
    return {
        "title": "",
        "authors": "",
        "publisher": "",
        "series": "",
        "tags": "",
        "language": "",
        "comments": "",
    }


def normalize_cover(
    source: Path | Image.Image,
    destination: Path,
    *,
    max_edge: int = 1600,
) -> Path:
    """Save an RGB JPEG cover suitable for KOReader sidecar / ebook-meta."""
    if isinstance(source, Image.Image):
        image = source
    else:
        image = Image.open(source)

    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="JPEG", quality=88, optimize=True)
    return destination


def read_metadata(
    book_path: Path,
    *,
    meta_bin: str = "ebook-meta",
    timeout: int = 60,
) -> dict[str, str]:
    """Parse `ebook-meta` stdout into a flat metadata dict."""
    meta = empty_metadata()
    if not book_path.is_file():
        return meta

    try:
        completed = subprocess.run(
            [meta_bin, str(book_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return meta
    except subprocess.TimeoutExpired as exc:
        raise BookMetaError("Timeout ao ler metadados (ebook-meta).") from exc

    if completed.returncode != 0:
        # Still try to parse partial stdout; otherwise return empty.
        text = completed.stdout or ""
    else:
        text = completed.stdout or ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_norm = key.strip().lower()
        mapped = _FIELD_MAP.get(key_norm)
        if not mapped:
            continue
        meta[mapped] = value.strip()

    # ebook-meta sometimes prints Title on first line without label for some formats
    if not meta["title"]:
        first = (text.splitlines()[0].strip() if text.splitlines() else "")
        if first and ":" not in first and first.lower() != str(book_path):
            meta["title"] = first

    return meta


def apply_metadata(
    book_path: Path,
    *,
    title: str = "",
    authors: str = "",
    publisher: str = "",
    series: str = "",
    tags: str = "",
    language: str = "",
    comments: str = "",
    cover_path: Path | None = None,
    meta_bin: str = "ebook-meta",
    timeout: int = 120,
) -> None:
    if not book_path.is_file():
        raise BookMetaError(f"Livro não encontrado: {book_path}")

    cmd = [meta_bin, str(book_path)]
    if title.strip():
        cmd.extend(["--title", title.strip()])
    if authors.strip():
        cmd.extend(["--authors", authors.strip()])
    if publisher.strip():
        cmd.extend(["--publisher", publisher.strip()])
    if series.strip():
        cmd.extend(["--series", series.strip()])
    if tags.strip():
        cmd.extend(["--tags", tags.strip()])
    if language.strip():
        cmd.extend(["--language", language.strip()])
    if comments.strip():
        cmd.extend(["--comments", comments.strip()])
    if cover_path is not None:
        if not cover_path.is_file():
            raise BookMetaError(f"Capa não encontrada: {cover_path}")
        cmd.extend(["--cover", str(cover_path)])

    # Nothing to apply
    if len(cmd) == 2:
        return

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BookMetaError(
            f"ebook-meta não encontrado ({meta_bin}). "
            "Instale o Calibre ou envie só o sidecar de capa."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BookMetaError("Timeout ao aplicar metadados (ebook-meta).") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise BookMetaError(detail or f"ebook-meta falhou (exit {completed.returncode}).")


def remote_name_from_title(title: str, fmt: str, fallback_stem: str = "book") -> str:
    stem = re.sub(r"[^\w\s\-]+", "", title, flags=re.UNICODE).strip()
    stem = re.sub(r"\s+", "_", stem)
    if not stem:
        stem = fallback_stem
    # Keep it filesystem-safe and reasonably short
    stem = stem[:80]
    fmt = fmt.lstrip(".")
    return f"{stem}.{fmt}"


def ebook_meta_available(meta_bin: str = "ebook-meta") -> bool:
    return shutil.which(meta_bin) is not None
