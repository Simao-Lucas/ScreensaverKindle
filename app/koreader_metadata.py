from __future__ import annotations

import re
from pathlib import Path

from app.book_meta import empty_metadata


def _lua_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _lua_unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _parse_props_block(block: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for m in re.finditer(r'\["([^"]+)"\]\s*=\s*"((?:\\.|[^"\\])*)"', block):
        props[m.group(1)] = _lua_unescape(m.group(2))
    for m in re.finditer(r'\["([^"]+)"\]\s*=\s*(\d+(?:\.\d+)?)', block):
        props[m.group(1)] = m.group(2)
    return props


def parse_custom_metadata_lua(text: str) -> dict[str, str]:
    """Return flat metadata preferring custom_props over doc_props."""
    meta = empty_metadata()
    if not text:
        return meta

    custom: dict[str, str] = {}
    doc: dict[str, str] = {}
    cm = re.search(r'\["custom_props"\]\s*=\s*\{(.*?)\n\}', text, flags=re.DOTALL)
    if cm:
        custom = _parse_props_block(cm.group(1))
    dm = re.search(r'\["doc_props"\]\s*=\s*\{(.*?)\n\}', text, flags=re.DOTALL)
    if dm:
        doc = _parse_props_block(dm.group(1))

    mapping = {
        "title": "title",
        "authors": "authors",
        "publisher": "publisher",
        "series": "series",
        "keywords": "tags",
        "tags": "tags",
        "language": "language",
        "description": "comments",
        "comments": "comments",
    }
    for src, dest in mapping.items():
        if custom.get(src):
            meta[dest] = custom[src]
        elif doc.get(src):
            meta[dest] = doc[src]
    return meta


def dump_custom_metadata_lua(
    *,
    custom_props: dict[str, str],
    doc_props: dict[str, str] | None = None,
) -> str:
    doc_props = doc_props or {}
    lines = ["return {"]
    lines.append('    ["custom_props"] = {')
    for key, value in custom_props.items():
        if value is None or str(value) == "":
            continue
        lines.append(f'        ["{_lua_escape(key)}"] = "{_lua_escape(str(value))}",')
    lines.append("    },")
    lines.append('    ["doc_props"] = {')
    for key, value in doc_props.items():
        if value is None or str(value) == "":
            continue
        lines.append(f'        ["{_lua_escape(key)}"] = "{_lua_escape(str(value))}",')
    lines.append("    },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def flat_to_custom_props(fields: dict[str, str]) -> dict[str, str]:
    return {
        "title": fields.get("title", ""),
        "authors": fields.get("authors", ""),
        "publisher": fields.get("publisher", ""),
        "series": fields.get("series", ""),
        "keywords": fields.get("tags", ""),
        "language": fields.get("language", ""),
        "description": fields.get("comments", ""),
    }


def sidecar_meta_path(sdr_dir: str) -> str:
    return f"{sdr_dir.rstrip('/')}/custom_metadata.lua"


def sidecar_cover_path(sdr_dir: str) -> str:
    return f"{sdr_dir.rstrip('/')}/cover.jpg"
