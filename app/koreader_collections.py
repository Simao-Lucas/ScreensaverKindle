from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field


class CollectionError(Exception):
    """Raised when collection.lua cannot be parsed or written."""


@dataclass
class CollectionBook:
    file: str
    order: int = 1


@dataclass
class Collection:
    name: str
    settings: dict = field(default_factory=lambda: {"order": 1})
    items: list[CollectionBook] = field(default_factory=list)


def _lua_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _parse_settings_block(block: str) -> dict:
    settings: dict = {"order": 1}
    order_m = re.search(r'\["order"\]\s*=\s*(\d+)', block)
    if order_m:
        settings["order"] = int(order_m.group(1))
    if re.search(r'\["default"\]\s*=\s*true', block):
        settings["default"] = True
    return settings


def parse_collection_lua(text: str) -> dict[str, Collection]:
    """
    Parse KOReader settings/collection.lua into Collection objects.

    Supports the usual dump format with ["favorites"] = { [1]={file,order}, settings={...} }.
    """
    if not text or not text.strip():
        return {
            "favorites": Collection(name="favorites", settings={"order": 1}, items=[]),
        }

    collections: dict[str, Collection] = {}
    # Only top-level keys inside `return { ... }` (ignore nested ["settings"] etc.)
    return_m = re.search(r"return\s*\{", text)
    body_start = return_m.end() - 1 if return_m else 0
    depth = 0
    i = body_start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            i += 1
            if depth <= 0:
                break
            continue
        if depth == 1:
            km = re.match(r'\["([^"]+)"\]\s*=\s*\{', text[i:])
            if km:
                name = km.group(1)
                start = i + km.end() - 1  # at '{'
                nest = 0
                end = start
                for idx in range(start, len(text)):
                    c2 = text[idx]
                    if c2 == "{":
                        nest += 1
                    elif c2 == "}":
                        nest -= 1
                        if nest == 0:
                            end = idx + 1
                            break
                block = text[start:end]

                items: list[CollectionBook] = []
                for fm in re.finditer(
                    r'\{\s*\["file"\]\s*=\s*"([^"]+)"\s*,\s*\["order"\]\s*=\s*(\d+)\s*,?\s*\}',
                    block,
                ):
                    items.append(CollectionBook(file=fm.group(1), order=int(fm.group(2))))
                if not items:
                    for fm in re.finditer(
                        r'\{\s*\["order"\]\s*=\s*(\d+)\s*,\s*\["file"\]\s*=\s*"([^"]+)"\s*,?\s*\}',
                        block,
                    ):
                        items.append(
                            CollectionBook(file=fm.group(2), order=int(fm.group(1)))
                        )

                settings = {"order": 1}
                sm = re.search(r'\["settings"\]\s*=\s*\{', block)
                if sm:
                    s_start = sm.end() - 1
                    s_nest = 0
                    s_end = s_start
                    for idx in range(s_start, len(block)):
                        c2 = block[idx]
                        if c2 == "{":
                            s_nest += 1
                        elif c2 == "}":
                            s_nest -= 1
                            if s_nest == 0:
                                s_end = idx + 1
                                break
                    settings = _parse_settings_block(block[s_start:s_end])
                elif name == "favorites":
                    settings = {"order": 1}

                items.sort(key=lambda it: it.order)
                collections[name] = Collection(name=name, settings=settings, items=items)
                i = end
                continue
        i += 1

    if "favorites" not in collections:
        collections["favorites"] = Collection(
            name="favorites", settings={"order": 1}, items=[]
        )
    return collections


def dump_collection_lua(
    collections: dict[str, Collection],
    *,
    path_comment: str = "/mnt/us/koreader/settings/collection.lua",
) -> str:
    lines = [f"-- {path_comment}", "return {"]
    # Stable order: favorites first, then by settings.order then name
    ordered = sorted(
        collections.values(),
        key=lambda c: (0 if c.name == "favorites" else 1, c.settings.get("order", 1), c.name),
    )
    for coll in ordered:
        lines.append(f'    ["{_lua_escape(coll.name)}"] = {{')
        for idx, item in enumerate(sorted(coll.items, key=lambda it: it.order), start=1):
            lines.append(f"        [{idx}] = {{")
            lines.append(f'            ["file"] = "{_lua_escape(item.file)}",')
            lines.append(f'            ["order"] = {item.order},')
            lines.append("        },")
        # settings
        lines.append('        ["settings"] = {')
        order = int(coll.settings.get("order", 1))
        lines.append(f'            ["order"] = {order},')
        if coll.settings.get("default"):
            lines.append('            ["default"] = true,')
        lines.append("        },")
        lines.append("    },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def ensure_favorites(collections: dict[str, Collection]) -> dict[str, Collection]:
    data = deepcopy(collections)
    if "favorites" not in data:
        data["favorites"] = Collection(name="favorites", settings={"order": 1}, items=[])
    return data


def add_book_to_collection(
    collections: dict[str, Collection],
    coll_name: str,
    file_path: str,
) -> dict[str, Collection]:
    data = ensure_favorites(collections)
    if coll_name not in data:
        raise CollectionError(f"Coleção inexistente: {coll_name}")
    coll = data[coll_name]
    if any(it.file == file_path for it in coll.items):
        return data
    next_order = max((it.order for it in coll.items), default=0) + 1
    coll.items.append(CollectionBook(file=file_path, order=next_order))
    return data


def remove_book_from_collection(
    collections: dict[str, Collection],
    coll_name: str,
    file_path: str,
) -> dict[str, Collection]:
    data = ensure_favorites(collections)
    if coll_name not in data:
        raise CollectionError(f"Coleção inexistente: {coll_name}")
    coll = data[coll_name]
    coll.items = [it for it in coll.items if it.file != file_path]
    for idx, it in enumerate(sorted(coll.items, key=lambda x: x.order), start=1):
        it.order = idx
    return data


def create_collection(
    collections: dict[str, Collection],
    name: str,
) -> dict[str, Collection]:
    data = ensure_favorites(collections)
    if name in data:
        raise CollectionError(f"Coleção já existe: {name}")
    max_order = max((c.settings.get("order", 1) for c in data.values()), default=0)
    data[name] = Collection(name=name, settings={"order": max_order + 1}, items=[])
    return data


def rename_collection(
    collections: dict[str, Collection],
    old_name: str,
    new_name: str,
) -> dict[str, Collection]:
    data = ensure_favorites(collections)
    if old_name == "favorites":
        raise CollectionError("Não é possível renomear a coleção favorites.")
    if old_name not in data:
        raise CollectionError(f"Coleção inexistente: {old_name}")
    if new_name in data:
        raise CollectionError(f"Já existe coleção: {new_name}")
    coll = data.pop(old_name)
    coll.name = new_name
    data[new_name] = coll
    return data


def delete_collection(
    collections: dict[str, Collection],
    name: str,
) -> dict[str, Collection]:
    data = ensure_favorites(collections)
    if name == "favorites":
        raise CollectionError("Não é possível apagar a coleção favorites.")
    if name not in data:
        raise CollectionError(f"Coleção inexistente: {name}")
    del data[name]
    return data


def collections_for_file(
    collections: dict[str, Collection],
    file_path: str,
) -> list[str]:
    return sorted(
        name
        for name, coll in collections.items()
        if any(it.file == file_path for it in coll.items)
    )


def rewrite_collection_paths(
    collections: dict[str, Collection],
    old_path: str,
    new_path: str,
    *,
    is_prefix: bool = False,
) -> tuple[dict[str, Collection], bool]:
    """
    Rewrite absolute file paths in collections after move/rename.
    If is_prefix, update every path that equals old_path or starts with old_path/.
    """
    data = ensure_favorites(collections)
    old = old_path.rstrip("/")
    new = new_path.rstrip("/")
    changed = False
    for coll in data.values():
        for item in coll.items:
            file = item.file
            if is_prefix:
                if file == old or file.startswith(old + "/"):
                    item.file = new + file[len(old) :]
                    changed = True
            elif file == old:
                item.file = new
                changed = True
    return data, changed
