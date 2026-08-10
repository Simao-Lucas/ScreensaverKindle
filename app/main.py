from __future__ import annotations

from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from app.book_converter import (
    BookConvertError,
    convert_book,
    load_book_meta,
    save_book_meta,
)
from app.image_pipeline import process_image, save_kindle_png, save_preview_png
from app.kindle_client import KindleClient, KindleError

bp = Blueprint("main", __name__)


def _ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def allowed_image(filename: str) -> bool:
    return _ext(filename) in current_app.config["ALLOWED_EXTENSIONS"]


def allowed_book(filename: str) -> bool:
    return _ext(filename) in current_app.config["BOOK_INPUT_EXTENSIONS"]


def kindle_client() -> KindleClient:
    cfg = current_app.config
    return KindleClient(
        host=cfg["KINDLE_HOST"],
        port=cfg["KINDLE_PORT"],
        username=cfg["KINDLE_USER"],
        password=cfg.get("KINDLE_PASSWORD", "") or "",
        key_path=cfg.get("KINDLE_SSH_KEY", "") or "",
        timeout=cfg["KINDLE_SSH_TIMEOUT"],
        remote_path=cfg["KINDLE_REMOTE_PATH"],
        refresh_cmd=cfg.get("KINDLE_REFRESH_CMD", "") or "",
        clear_screensaver_dir=cfg.get("KINDLE_CLEAR_SCREENSAVER_DIR", True),
        documents_dir=cfg.get("KINDLE_DOCUMENTS_DIR", "/mnt/us/documents"),
    )


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/")
def home():
    return render_template("home.html")


# --- Screensaver -------------------------------------------------------------


@bp.get("/screensaver")
def screensaver_page():
    has_current = Path(current_app.config["CURRENT_IMAGE"]).is_file()
    return render_template(
        "screensaver.html",
        has_current=has_current,
        width=current_app.config["KINDLE_WIDTH"],
        height=current_app.config["KINDLE_HEIGHT"],
        host=current_app.config["KINDLE_HOST"] or "(não configurado)",
        remote_path=current_app.config["KINDLE_REMOTE_PATH"],
    )


@bp.get("/screensaver/preview")
def screensaver_preview():
    preview_path = Path(current_app.config["PREVIEW_IMAGE"])
    current_path = Path(current_app.config["CURRENT_IMAGE"])
    target = preview_path if preview_path.is_file() else current_path
    if not target.is_file():
        return jsonify({"error": "Nenhuma imagem processada ainda."}), 404
    return send_from_directory(target.parent, target.name, mimetype="image/png")


@bp.post("/screensaver/upload")
def screensaver_upload():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "Nenhum arquivo enviado.", "status": {}}), 400

    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Arquivo vazio.", "status": {}}), 400
    if not allowed_image(file.filename):
        return jsonify(
            {
                "ok": False,
                "error": "Formato não suportado. Use PNG, JPG, WEBP, BMP ou GIF.",
                "status": {},
            }
        ), 400

    filename = secure_filename(file.filename)
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    raw_path = upload_dir / f"source_{filename}"
    file.save(raw_path)

    try:
        processed = process_image(
            raw_path,
            width=current_app.config["KINDLE_WIDTH"],
            height=current_app.config["KINDLE_HEIGHT"],
            contrast=current_app.config["KINDLE_CONTRAST"],
        )
        save_kindle_png(processed, Path(current_app.config["CURRENT_IMAGE"]))
        save_preview_png(processed, Path(current_app.config["PREVIEW_IMAGE"]))
    except Exception as exc:  # noqa: BLE001
        return jsonify(
            {
                "ok": False,
                "error": f"Falha na conversão: {exc}",
                "status": {"converted": False},
            }
        ), 500
    finally:
        if raw_path.exists():
            raw_path.unlink(missing_ok=True)

    return jsonify(
        {
            "ok": True,
            "message": "Imagem convertida para e-ink.",
            "status": {"converted": True, "transferred": False, "ready": False},
            "preview_url": "/screensaver/preview",
        }
    )


@bp.post("/screensaver/push")
def screensaver_push():
    current = Path(current_app.config["CURRENT_IMAGE"])
    if not current.is_file():
        return jsonify(
            {
                "ok": False,
                "error": "Nenhuma imagem convertida. Faça o upload primeiro.",
                "status": {"converted": False},
            }
        ), 400

    client = kindle_client()
    try:
        result = client.push(current)
    except KindleError as exc:
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
                "status": {
                    "converted": True,
                    "transferred": False,
                    "ready": False,
                },
            }
        ), 502

    return jsonify(
        {
            "ok": True,
            "message": (
                "Imagem na pasta do screensaver do KOReader. "
                "Ela aparece quando o Kindle entrar em sleep."
            ),
            "status": {
                "converted": True,
                "transferred": True,
                "ready": True,
            },
            "detail": result,
        }
    )


# Legacy aliases (old UI paths)
@bp.get("/preview")
def preview_legacy():
    return screensaver_preview()


@bp.post("/upload")
def upload_legacy():
    return screensaver_upload()


@bp.post("/push")
def push_legacy():
    return screensaver_push()


# --- Books -------------------------------------------------------------------


@bp.get("/books")
def books_page():
    meta = load_book_meta(Path(current_app.config["CURRENT_BOOK_META"]))
    has_book = bool(meta and Path(meta.get("local_path", "")).is_file())
    return render_template(
        "books.html",
        has_book=has_book,
        book_name=(meta or {}).get("remote_name", ""),
        output_formats=current_app.config["BOOK_OUTPUT_FORMATS"],
        host=current_app.config["KINDLE_HOST"] or "(não configurado)",
        documents_dir=current_app.config["KINDLE_DOCUMENTS_DIR"],
    )


@bp.post("/books/upload")
def books_upload():
    if "book" not in request.files:
        return jsonify({"ok": False, "error": "Nenhum arquivo enviado.", "status": {}}), 400

    file = request.files["book"]
    target_format = (request.form.get("format") or "epub").lower().strip()
    if target_format not in current_app.config["BOOK_OUTPUT_FORMATS"]:
        return jsonify(
            {
                "ok": False,
                "error": f"Formato de saída inválido: {target_format}",
                "status": {},
            }
        ), 400

    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Arquivo vazio.", "status": {}}), 400
    if not allowed_book(file.filename):
        allowed = ", ".join(sorted(current_app.config["BOOK_INPUT_EXTENSIONS"]))
        return jsonify(
            {
                "ok": False,
                "error": f"Formato de entrada não suportado. Use: {allowed}",
                "status": {},
            }
        ), 400

    books_dir = Path(current_app.config["BOOKS_DIR"])
    incoming = books_dir / "incoming"
    ready = books_dir / "ready"
    incoming.mkdir(parents=True, exist_ok=True)
    ready.mkdir(parents=True, exist_ok=True)

    original_name = secure_filename(file.filename) or "book"
    source_path = incoming / original_name
    file.save(source_path)

    # Clean previous ready files
    for old in ready.glob("*"):
        if old.is_file():
            old.unlink(missing_ok=True)

    try:
        out_path, did_convert = convert_book(
            source_path,
            target_format=target_format,
            output_dir=ready,
            convert_bin=current_app.config["EBOOK_CONVERT_BIN"],
            timeout=current_app.config["EBOOK_CONVERT_TIMEOUT"],
        )
    except BookConvertError as exc:
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
                "status": {"converted": False},
            }
        ), 500
    finally:
        if source_path.exists():
            source_path.unlink(missing_ok=True)

    remote_stem = Path(original_name).stem
    remote_name = secure_filename(f"{remote_stem}.{target_format}") or f"book.{target_format}"
    save_book_meta(
        Path(current_app.config["CURRENT_BOOK_META"]),
        local_path=out_path,
        remote_name=remote_name,
        format=target_format,
    )

    msg = (
        f"Convertido para .{target_format}."
        if did_convert
        else f"Já estava em .{target_format}; pronto para enviar."
    )
    return jsonify(
        {
            "ok": True,
            "message": msg,
            "status": {"converted": True, "transferred": False, "ready": False},
            "book_name": remote_name,
            "converted": did_convert,
        }
    )


@bp.post("/books/push")
def books_push():
    meta = load_book_meta(Path(current_app.config["CURRENT_BOOK_META"]))
    if not meta:
        return jsonify(
            {
                "ok": False,
                "error": "Nenhum livro preparado. Faça o upload primeiro.",
                "status": {"converted": False},
            }
        ), 400

    local_path = Path(meta.get("local_path", ""))
    remote_name = meta.get("remote_name") or local_path.name
    if not local_path.is_file():
        return jsonify(
            {
                "ok": False,
                "error": "Arquivo convertido não encontrado. Envie o livro de novo.",
                "status": {"converted": False},
            }
        ), 400

    client = kindle_client()
    try:
        result = client.push_document(local_path, remote_name)
    except KindleError as exc:
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
                "status": {
                    "converted": True,
                    "transferred": False,
                    "ready": False,
                },
            }
        ), 502

    return jsonify(
        {
            "ok": True,
            "message": f"Livro enviado para {result.get('documents_path')}.",
            "status": {
                "converted": True,
                "transferred": True,
                "ready": True,
            },
            "detail": result,
        }
    )


from app import create_app  # noqa: E402

app = create_app()
