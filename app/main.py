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

from app.image_pipeline import process_image, save_kindle_png, save_preview_png
from app.kindle_client import KindleClient, KindleError

bp = Blueprint("main", __name__)


def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def kindle_client() -> KindleClient:
    cfg = current_app.config
    return KindleClient(
        host=cfg["KINDLE_HOST"],
        port=cfg["KINDLE_PORT"],
        username=cfg["KINDLE_USER"],
        password=cfg["KINDLE_PASSWORD"],
        timeout=cfg["KINDLE_SSH_TIMEOUT"],
        remote_path=cfg["KINDLE_REMOTE_PATH"],
        refresh_cmd=cfg["KINDLE_REFRESH_CMD"],
    )


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/")
def index():
    has_current = Path(current_app.config["CURRENT_IMAGE"]).is_file()
    return render_template(
        "index.html",
        has_current=has_current,
        width=current_app.config["KINDLE_WIDTH"],
        height=current_app.config["KINDLE_HEIGHT"],
        host=current_app.config["KINDLE_HOST"] or "(não configurado)",
    )


@bp.get("/preview")
def preview():
    preview_path = Path(current_app.config["PREVIEW_IMAGE"])
    current_path = Path(current_app.config["CURRENT_IMAGE"])
    target = preview_path if preview_path.is_file() else current_path
    if not target.is_file():
        return jsonify({"error": "Nenhuma imagem processada ainda."}), 404
    return send_from_directory(target.parent, target.name, mimetype="image/png")


@bp.post("/upload")
def upload():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "Nenhum arquivo enviado.", "status": {}}), 400

    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Arquivo vazio.", "status": {}}), 400
    if not allowed_file(file.filename):
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
    except Exception as exc:  # noqa: BLE001 — surface conversion errors to UI
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
            "status": {"converted": True, "transferred": False, "displayed": False},
            "preview_url": "/preview",
        }
    )


@bp.post("/push")
def push():
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
                    "displayed": False,
                },
            }
        ), 502

    return jsonify(
        {
            "ok": True,
            "message": "Imagem enviada e refresh disparado.",
            "status": {
                "converted": True,
                "transferred": True,
                "displayed": True,
            },
            "detail": result,
        }
    )


from app import create_app  # noqa: E402

app = create_app()
