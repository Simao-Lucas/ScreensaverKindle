from __future__ import annotations

from pathlib import Path

from app.book_meta import (
    apply_metadata,
    ebook_meta_available,
    empty_metadata,
    normalize_cover,
)
from app.kindle_client import KindleClient, KindleError
from app.koreader_collections import (
    Collection,
    CollectionError,
    add_book_to_collection,
    collections_for_file,
    create_collection,
    delete_collection,
    dump_collection_lua,
    ensure_favorites,
    parse_collection_lua,
    remove_book_from_collection,
    rename_collection,
    rewrite_collection_paths,
)
from app.koreader_metadata import (
    dump_custom_metadata_lua,
    flat_to_custom_props,
    parse_custom_metadata_lua,
    sidecar_cover_path,
    sidecar_meta_path,
)


class LibraryService:
    def __init__(
        self,
        client: KindleClient,
        *,
        cache_dir: Path,
        collection_file: str,
        book_extensions: set[str],
        ebook_meta_bin: str = "ebook-meta",
    ):
        self.client = client
        self.cache_dir = cache_dir
        self.covers_dir = cache_dir / "covers"
        self.tmp_dir = cache_dir / "tmp"
        self.collection_file = collection_file
        self.book_extensions = {e.lower().lstrip(".") for e in book_extensions}
        self.ebook_meta_bin = ebook_meta_bin
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def _norm_rel(self, relative: str) -> str:
        return (relative or "").replace("\\", "/").strip("/")

    def _abs(self, relative: str) -> str:
        return self.client.resolve_under_documents(self._norm_rel(relative))

    def _sdr_for_book_rel(self, book_rel: str) -> str:
        abs_book = self._abs(book_rel)
        parent = self.client._parent_dir(abs_book)
        stem = Path(book_rel).stem
        return f"{parent}/{stem}.sdr"

    def _cover_cache_name(self, book_rel: str) -> str:
        safe = self._norm_rel(book_rel).replace("/", "__")
        return f"{Path(safe).stem}.jpg"

    def browse(self, relative_path: str = "") -> dict:
        rel = self._norm_rel(relative_path)
        # Ensure path exists and is a directory (root always ok)
        abs_path = self._abs(rel)
        if rel and not self.client.remote_is_dir(abs_path):
            raise KindleError(f"Pasta não encontrada: {rel}")
        entries = self.client.list_dir(rel, self.book_extensions)
        try:
            collections = self.load_collections()
        except (KindleError, CollectionError):
            collections = ensure_favorites({})

        enriched = []
        for entry in entries:
            if entry["type"] == "file":
                membership = collections_for_file(collections, entry["path"])
                enriched.append(
                    {
                        **entry,
                        "title": Path(entry["name"]).stem.replace("_", " "),
                        "collections": membership,
                        "favorite": "favorites" in membership,
                    }
                )
            else:
                enriched.append(entry)

        crumbs = []
        if rel:
            parts = rel.split("/")
            acc = []
            for part in parts:
                acc.append(part)
                crumbs.append({"name": part, "rel": "/".join(acc)})

        return {
            "path": rel,
            "absolute": abs_path,
            "crumbs": crumbs,
            "entries": enriched,
        }

    def folder_tree(self) -> dict:
        return self.client.list_folder_tree()

    def create_folder(self, parent_rel: str, name: str) -> dict:
        name = (name or "").strip().replace("\\", "/").strip("/")
        if not name or "/" in name or name in (".", "..") or name.endswith(".sdr"):
            raise KindleError("Nome de pasta inválido.")
        parent = self._norm_rel(parent_rel)
        target = f"{parent}/{name}".strip("/")
        if self.client.remote_exists(self._abs(target)):
            raise KindleError(f"Já existe: {name}")
        self.client.mkdir(target)
        return self.browse(parent)

    def rename_entry(self, relative_path: str, new_name: str) -> dict:
        rel = self._norm_rel(relative_path)
        if not rel:
            raise KindleError("Não é possível renomear a raiz.")
        new_name = (new_name or "").strip().replace("\\", "/").strip("/")
        if not new_name or "/" in new_name or new_name in (".", ".."):
            raise KindleError("Novo nome inválido.")

        abs_src = self._abs(rel)
        parent_rel = str(Path(rel).parent).replace("\\", "/")
        if parent_rel == ".":
            parent_rel = ""
        is_dir = self.client.remote_is_dir(abs_src)
        old_abs = abs_src

        if is_dir:
            new_rel = self.client.rename_path(rel, new_name)
            new_abs = self._abs(new_rel)
            self._rewrite_collections(old_abs, new_abs, is_prefix=True)
            return {"ok": True, "rel": new_rel, "type": "dir"}

        # Book file: rename file + sibling .sdr
        stem_old = Path(rel).stem
        stem_new = Path(new_name).stem
        if not Path(new_name).suffix:
            raise KindleError("Arquivo de livro precisa de extensão.")
        dest_rel = f"{parent_rel}/{new_name}".strip("/")
        dest_abs = self._abs(dest_rel)
        if self.client.remote_exists(dest_abs):
            raise KindleError(f"Já existe: {new_name}")
        sdr_old = self._sdr_for_book_rel(rel)
        sdr_new = f"{self.client._parent_dir(dest_abs)}/{stem_new}.sdr"
        self.client._remote_mv(abs_src, dest_abs)
        if self.client.remote_exists(sdr_old):
            if stem_old != stem_new and self.client.remote_exists(sdr_new):
                raise KindleError(f"Pasta .sdr já existe: {stem_new}.sdr")
            if sdr_old != sdr_new:
                self.client._remote_mv(sdr_old, sdr_new)
        self._rewrite_collections(old_abs, dest_abs, is_prefix=False)
        return {"ok": True, "rel": dest_rel, "type": "file"}

    def move_entries(self, sources: list[str], dest_rel: str) -> dict:
        dest = self._norm_rel(dest_rel)
        dest_abs = self._abs(dest)
        if dest and not self.client.remote_is_dir(dest_abs):
            raise KindleError(f"Destino não é pasta: {dest}")

        moved = []
        for src in sources:
            rel = self._norm_rel(src)
            if not rel:
                raise KindleError("Não é possível mover a raiz.")
            abs_src = self._abs(rel)
            # Skip no-op (already in dest)
            parent = str(Path(rel).parent).replace("\\", "/")
            if parent == ".":
                parent = ""
            if parent == dest:
                moved.append(rel)
                continue

            is_dir = self.client.remote_is_dir(abs_src)
            old_abs = abs_src
            if is_dir:
                new_rel = self.client.move_path(rel, dest)
                new_abs = self._abs(new_rel)
                self._rewrite_collections(old_abs, new_abs, is_prefix=True)
            else:
                new_rel = self.client.move_document(rel, dest)
                new_abs = self._abs(new_rel)
                self._rewrite_collections(old_abs, new_abs, is_prefix=False)
            moved.append(new_rel)
        return {"ok": True, "moved": moved, "dest": dest}

    def delete_entry(self, relative_path: str) -> None:
        rel = self._norm_rel(relative_path)
        if not rel:
            raise KindleError("Não é possível apagar a raiz documents.")
        abs_path = self._abs(rel)
        if not self.client.remote_exists(abs_path):
            raise KindleError(f"Não encontrado: {rel}")

        is_dir = self.client.remote_is_dir(abs_path)
        if is_dir:
            # Remove any book paths under this folder from collections
            self._remove_collection_prefix(abs_path)
            self.client.remove_remote(abs_path)
            return

        # Book: remove from collections, delete file + .sdr
        collections = self.load_collections()
        changed = False
        for coll_name in list(collections.keys()):
            before = len(collections[coll_name].items)
            collections = remove_book_from_collection(collections, coll_name, abs_path)
            if len(collections[coll_name].items) != before:
                changed = True
        if changed:
            self.save_collections(collections)
        self.client.delete_document(rel)
        cached = self.covers_dir / self._cover_cache_name(rel)
        if cached.exists():
            cached.unlink(missing_ok=True)

    def _rewrite_collections(self, old_abs: str, new_abs: str, *, is_prefix: bool) -> None:
        try:
            collections = self.load_collections()
        except (KindleError, CollectionError):
            return
        collections, changed = rewrite_collection_paths(
            collections, old_abs, new_abs, is_prefix=is_prefix
        )
        if changed:
            self.save_collections(collections)

    def _remove_collection_prefix(self, folder_abs: str) -> None:
        try:
            collections = self.load_collections()
        except (KindleError, CollectionError):
            return
        prefix = folder_abs.rstrip("/")
        changed = False
        for coll in collections.values():
            before = len(coll.items)
            coll.items = [
                it
                for it in coll.items
                if not (it.file == prefix or it.file.startswith(prefix + "/"))
            ]
            if len(coll.items) != before:
                changed = True
        if changed:
            self.save_collections(collections)

    def list_books(self) -> list[dict]:
        """Flat list (legacy); prefers browse for UI."""
        books = self.client.list_documents(self.book_extensions)
        try:
            collections = self.load_collections()
        except (KindleError, CollectionError):
            collections = ensure_favorites({})

        enriched = []
        for book in books:
            path = book["path"]
            membership = collections_for_file(collections, path)
            title = Path(book["name"]).stem.replace("_", " ")
            enriched.append(
                {
                    **book,
                    "title": title,
                    "collections": membership,
                    "favorite": "favorites" in membership,
                }
            )
        return enriched

    def get_book(self, name: str) -> dict:
        rel = self._norm_rel(name)
        path = self._abs(rel)
        if not self.client.remote_exists(path):
            raise KindleError(f"Livro não encontrado: {rel}")
        if self.client.remote_is_dir(path):
            raise KindleError(f"Não é um arquivo de livro: {rel}")

        stem = Path(rel).stem
        sdr_dir = self._sdr_for_book_rel(rel)
        meta_remote = sidecar_meta_path(sdr_dir)
        cover_jpg = sidecar_cover_path(sdr_dir)
        cover_png = f"{sdr_dir}/cover.png"

        metadata = empty_metadata()
        metadata["title"] = stem.replace("_", " ")
        if self.client.remote_exists(meta_remote):
            try:
                text = self.client.read_text(meta_remote)
                metadata = parse_custom_metadata_lua(text)
                if not metadata.get("title"):
                    metadata["title"] = stem.replace("_", " ")
            except KindleError:
                pass

        has_cover = False
        cover_remote = ""
        if self.client.remote_exists(cover_jpg):
            has_cover = True
            cover_remote = cover_jpg
        elif self.client.remote_exists(cover_png):
            has_cover = True
            cover_remote = cover_png

        collections = self.load_collections()
        membership = collections_for_file(collections, path)

        return {
            "name": rel,
            "path": path,
            "sdr_dir": sdr_dir,
            "metadata": metadata,
            "has_cover": has_cover,
            "cover_remote": cover_remote,
            "collections": membership,
            "favorite": "favorites" in membership,
            "all_collections": [
                {"name": c.name, "count": len(c.items)} for c in collections.values()
            ],
        }

    def cache_cover(self, name: str, cover_remote: str) -> Path | None:
        if not cover_remote:
            return None
        local = self.covers_dir / self._cover_cache_name(name)
        try:
            self.client.download_file(cover_remote, local)
            return local
        except KindleError:
            return None

    def save_metadata(self, name: str, fields: dict[str, str]) -> dict:
        book = self.get_book(name)
        sdr_dir = book["sdr_dir"]
        path = book["path"]
        custom_props = flat_to_custom_props(fields)
        doc_props = {
            "title": fields.get("title", ""),
            "authors": fields.get("authors", ""),
            "language": fields.get("language", ""),
            "keywords": fields.get("tags", ""),
            "description": fields.get("comments", ""),
            "series": fields.get("series", ""),
        }
        lua = dump_custom_metadata_lua(custom_props=custom_props, doc_props=doc_props)
        self.client.write_text(sidecar_meta_path(sdr_dir), lua, backup=True)

        if ebook_meta_available(self.ebook_meta_bin):
            local_name = Path(self._norm_rel(name)).name
            local_book = self.tmp_dir / local_name
            try:
                self.client.download_file(path, local_book)
                cover_local = None
                if book.get("cover_remote"):
                    cover_local = self.tmp_dir / f"{Path(local_name).stem}_cover.jpg"
                    try:
                        self.client.download_file(book["cover_remote"], cover_local)
                    except KindleError:
                        cover_local = None
                apply_metadata(
                    local_book,
                    title=fields.get("title", ""),
                    authors=fields.get("authors", ""),
                    publisher=fields.get("publisher", ""),
                    series=fields.get("series", ""),
                    tags=fields.get("tags", ""),
                    language=fields.get("language", ""),
                    comments=fields.get("comments", ""),
                    cover_path=cover_local if cover_local and cover_local.is_file() else None,
                    meta_bin=self.ebook_meta_bin,
                )
                self.client.upload_to(local_book, path, clear_images=False)
            except Exception:
                pass
            finally:
                if local_book.exists():
                    local_book.unlink(missing_ok=True)

        return self.get_book(name)

    def save_cover(self, name: str, image_path: Path) -> dict:
        book = self.get_book(name)
        dest = self.tmp_dir / f"{Path(self._norm_rel(name)).stem}_cover.jpg"
        normalize_cover(image_path, dest)
        remote = sidecar_cover_path(book["sdr_dir"])
        self.client.upload_to(dest, remote, clear_images=False)
        cached = self.covers_dir / self._cover_cache_name(name)
        cached.write_bytes(dest.read_bytes())
        return self.get_book(name)

    def delete_book(self, name: str) -> None:
        self.delete_entry(name)

    def load_collections(self) -> dict[str, Collection]:
        if not self.client.remote_exists(self.collection_file):
            return ensure_favorites({})
        text = self.client.read_text(self.collection_file)
        return ensure_favorites(parse_collection_lua(text))

    def save_collections(self, collections: dict[str, Collection]) -> None:
        lua = dump_collection_lua(collections, path_comment=self.collection_file)
        self.client.write_text(self.collection_file, lua, backup=True)

    def list_collections(self) -> list[dict]:
        collections = self.load_collections()
        rows = []
        for coll in collections.values():
            rows.append(
                {
                    "name": coll.name,
                    "order": coll.settings.get("order", 1),
                    "count": len(coll.items),
                    "files": [it.file for it in coll.items],
                }
            )
        rows.sort(key=lambda r: (0 if r["name"] == "favorites" else 1, r["order"], r["name"]))
        return rows

    def create_collection(self, name: str) -> list[dict]:
        collections = create_collection(self.load_collections(), name)
        self.save_collections(collections)
        return self.list_collections()

    def rename_collection(self, old: str, new: str) -> list[dict]:
        collections = rename_collection(self.load_collections(), old, new)
        self.save_collections(collections)
        return self.list_collections()

    def delete_collection(self, name: str) -> list[dict]:
        collections = delete_collection(self.load_collections(), name)
        self.save_collections(collections)
        return self.list_collections()

    def set_book_in_collection(
        self,
        coll_name: str,
        book_path: str,
        *,
        add: bool,
    ) -> list[dict]:
        collections = self.load_collections()
        if add:
            collections = add_book_to_collection(collections, coll_name, book_path)
        else:
            collections = remove_book_from_collection(collections, coll_name, book_path)
        self.save_collections(collections)
        return self.list_collections()
