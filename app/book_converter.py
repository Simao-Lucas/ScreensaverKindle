from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class BookConvertError(Exception):
    """Raised when ebook conversion fails."""


def convert_book(
    source: Path,
    *,
    target_format: str,
    output_dir: Path,
    convert_bin: str = "ebook-convert",
    timeout: int = 600,
) -> tuple[Path, bool]:
    """
    Convert (or copy) a book to target_format.

    Returns (output_path, converted) where converted is False if only copied.
    """
    target_format = target_format.lower().lstrip(".")
    if not source.is_file():
        raise BookConvertError(f"Arquivo de origem não encontrado: {source}")

    source_ext = source.suffix.lower().lstrip(".")
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = source.stem
    # Avoid colliding with source if same dir
    out_path = output_dir / f"{stem}.{target_format}"
    if out_path.resolve() == source.resolve():
        out_path = output_dir / f"{stem}_ready.{target_format}"

    if source_ext == target_format:
        shutil.copy2(source, out_path)
        return out_path, False

    cmd = [convert_bin, str(source), str(out_path)]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BookConvertError(
            f"Conversor não encontrado ({convert_bin}). "
            "Instale o Calibre no container."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BookConvertError(
            f"Conversão excedeu o tempo limite ({timeout}s)."
        ) from exc

    if completed.returncode != 0 or not out_path.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise BookConvertError(
            detail or f"ebook-convert falhou (exit {completed.returncode})."
        )

    return out_path, True


def save_book_meta(meta_path: Path, **fields) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if meta_path.is_file():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update({k: v for k, v in fields.items() if v is not None})
    # Normalize path-like values to strings
    for key in ("local_path", "cover_path"):
        if key in existing and existing[key] is not None:
            existing[key] = str(existing[key])
    meta_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_book_meta(meta_path: Path) -> dict | None:
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data
