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

    def list_books(self) -> list[dict]:
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
            # lightweight: try cached custom metadata if present locally later
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
        docs = self.client.documents_dir.rstrip("/")
        path = f"{docs}/{name}"
        if not self.client.remote_exists(path):
            raise KindleError(f"Livro não encontrado: {name}")

        stem = Path(name).stem
        sdr_dir = f"{docs}/{stem}.sdr"
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
            "name": name,
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
        local = self.covers_dir / f"{Path(name).stem}.jpg"
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

        # Optional: mirror into the ebook file with ebook-meta
        if ebook_meta_available(self.ebook_meta_bin):
            local_book = self.tmp_dir / name
            try:
                self.client.download_file(path, local_book)
                cover_local = None
                if book.get("cover_remote"):
                    cover_local = self.tmp_dir / f"{Path(name).stem}_cover.jpg"
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
                # custom_metadata.lua already saved; ebook-meta is best-effort
                pass
            finally:
                if local_book.exists():
                    local_book.unlink(missing_ok=True)

        return self.get_book(name)

    def save_cover(self, name: str, image_path: Path) -> dict:
        book = self.get_book(name)
        dest = self.tmp_dir / f"{Path(name).stem}_cover.jpg"
        normalize_cover(image_path, dest)
        remote = sidecar_cover_path(book["sdr_dir"])
        self.client.upload_to(dest, remote, clear_images=False)
        cached = self.covers_dir / f"{Path(name).stem}.jpg"
        cached.write_bytes(dest.read_bytes())
        return self.get_book(name)

    def delete_book(self, name: str) -> None:
        book = self.get_book(name)
        path = book["path"]
        # Remove from all collections first
        collections = self.load_collections()
        changed = False
        for coll_name in list(collections.keys()):
            before = len(collections[coll_name].items)
            collections = remove_book_from_collection(collections, coll_name, path)
            if len(collections[coll_name].items) != before:
                changed = True
        if changed:
            self.save_collections(collections)
        self.client.delete_document(name)
        cached = self.covers_dir / f"{Path(name).stem}.jpg"
        if cached.exists():
            cached.unlink(missing_ok=True)

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
