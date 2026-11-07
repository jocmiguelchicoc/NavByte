# -*- coding: utf-8 -*-
"""
NavByte - Rutas de Gestión de Archivos
Exploración, previsualización, descarga, subida, creación y eliminación segura de archivos.
"""

import os
import sys
import time
from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_file,
    current_app,
)
from werkzeug.utils import secure_filename

from ..config import (
    IMAGE_MIME_TYPES,
    VIDEO_MIME_TYPES,
    AUDIO_MIME_TYPES,
    DANGEROUS_UPLOAD_EXTS,
)
from ..security import require_auth, is_protected_system_path
from ..services.filesystem import (
    safe_resolve_path,
    detect_system_drives,
    list_directory_entries,
    get_file_category,
    format_size,
)
from ..services.search import search_files

file_bp = Blueprint("files", __name__)


@file_bp.route("/")
def index():
    """Sirve la interfaz web móvil responsiva con cache-busting dinámico."""
    return render_template("index.html", version_ts=int(time.time()))


@file_bp.route("/api/browse", methods=["GET"])
@require_auth
def browse():
    """
    Lista archivos y carpetas en una ruta relativa dada.
    Parámetros GET:
      path: ruta relativa dentro de SHARED_DIR (opcional, default "")
    """
    shared_dir = current_app.config["SHARED_DIR"]
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)

    if not is_valid or not os.path.exists(abs_path):
        return jsonify({"error": "Ruta no válida o no encontrada"}), 404

    if not os.path.isdir(abs_path):
        return jsonify({"error": "La ruta especificada no es una carpeta"}), 400

    # Calcular breadcrumbs y ruta padre coherente con las unidades del PC
    drives = detect_system_drives(shared_dir)
    drive_map = {d["path"]: d for d in drives if d["path"]}

    clean_rel = rel_path.strip().strip("/\\")
    norm_rel = os.path.normpath(clean_rel).replace("\\", "/") if clean_rel else "."

    matched_drive = None
    drive_subpath = None

    if norm_rel != ".":
        if norm_rel in drive_map:
            matched_drive = drive_map[norm_rel]
            drive_subpath = ""
        else:
            for d_path, d_info in drive_map.items():
                if norm_rel.startswith(d_path + "/"):
                    matched_drive = d_info
                    drive_subpath = norm_rel[len(d_path) + 1:]
                    break

    breadcrumbs = [{"name": "Inicio", "path": ""}]
    parent_path = None

    if norm_rel != ".":
        if matched_drive:
            breadcrumbs.append({"name": f"💽 {matched_drive['name']}", "path": matched_drive["path"]})
            if drive_subpath:
                parts = drive_subpath.split("/")
                accum = [matched_drive["path"]]
                for p in parts:
                    accum.append(p)
                    breadcrumbs.append({"name": p, "path": "/".join(accum)})
                parent_dir = os.path.dirname(norm_rel)
                parent_path = parent_dir.replace("\\", "/")
            else:
                parent_path = ""
        else:
            parts = norm_rel.split(os.sep)
            accum = []
            for p in parts:
                accum.append(p)
                breadcrumbs.append({"name": p, "path": "/".join(accum)})
            parent_dir = os.path.dirname(norm_rel)
            if parent_dir in (".", "", "media") or (parent_dir.startswith("media/") and len(parent_dir.split("/")) <= 2):
                parent_path = ""
            elif sys.platform == "win32" and len(parent_dir) <= 3 and parent_dir.endswith(":"):
                parent_path = ""
            else:
                parent_path = parent_dir.replace("\\", "/")

    # En la pantalla de Inicio (/), mostrar exclusivamente las unidades y discos duros, sin archivos sueltos del sistema
    if norm_rel == "." and shared_dir == "/":
        return jsonify({
            "current_path": "",
            "parent_path": None,
            "breadcrumbs": breadcrumbs,
            "items": [],
            "total_items": 0,
            "is_root": True,
        })

    try:
        items = list_directory_entries(abs_path, shared_dir)
    except PermissionError:
        return jsonify({"error": "Permiso denegado para leer este directorio"}), 403

    return jsonify({
        "current_path": "" if norm_rel == "." else norm_rel.replace("\\", "/"),
        "parent_path": parent_path,
        "breadcrumbs": breadcrumbs,
        "items": items,
        "total_items": len(items),
        "is_root": norm_rel == ".",
    })


@file_bp.route("/api/search", methods=["GET"])
@require_auth
def search():
    """Busca recursivamente archivos y carpetas."""
    shared_dir = current_app.config["SHARED_DIR"]
    rel_path = request.args.get("path", "").strip()
    query = request.args.get("q", "").strip()

    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)
    if not is_valid or not os.path.exists(abs_path) or not os.path.isdir(abs_path):
        return jsonify({"error": "Ruta de búsqueda no válida"}), 400

    max_results = min(int(request.args.get("max_results", 80)), 200)
    data = search_files(
        abs_path=abs_path,
        rel_path=rel_path,
        query=query,
        shared_dir=shared_dir,
        max_results=max_results,
    )
    return jsonify(data)


@file_bp.route("/api/preview", methods=["GET"])
@require_auth
def preview():
    """Sirve un archivo para visualización inline en el navegador."""
    shared_dir = current_app.config["SHARED_DIR"]
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)

    if not is_valid or not os.path.isfile(abs_path):
        return jsonify({"error": "Archivo no encontrado o acceso restringido"}), 404

    ext = Path(abs_path).suffix.lower()
    category = get_file_category(ext)
    file_size = os.path.getsize(abs_path)

    # 1. Imágenes
    if category == "image":
        mime = IMAGE_MIME_TYPES.get(ext, "image/jpeg")
        return send_file(abs_path, mimetype=mime, conditional=True)

    # 2. Videos
    if category == "video":
        mime = VIDEO_MIME_TYPES.get(ext, "video/mp4")
        return send_file(abs_path, mimetype=mime, conditional=True)

    # 3. PDFs
    if ext == ".pdf":
        return send_file(abs_path, mimetype="application/pdf", conditional=True)

    # 4. Audio
    if category == "audio":
        mime = AUDIO_MIME_TYPES.get(ext, "audio/mpeg")
        return send_file(abs_path, mimetype=mime, conditional=True)

    # 5. MIDI
    if category == "midi":
        return jsonify({
            "type": "midi",
            "name": os.path.basename(abs_path),
            "extension": ext[1:] if ext else "mid",
            "size": file_size,
            "message": "Archivo MIDI (Secuencia musical para DAW como FL Studio o Ableton)."
        })

    # 6. Documentos Ofimáticos
    if ext in (".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf"):
        return jsonify({
            "type": "office",
            "name": os.path.basename(abs_path),
            "extension": ext[1:] if ext else "",
            "size": file_size,
            "message": "Documento ofimático. Descárgalo para abrirlo en tu app preferida."
        })

    # 7. Código y Texto plano
    TEXT_EXTENSIONS = {
        ".txt", ".md", ".csv", ".log", ".json", ".xml", ".yaml", ".yml",
        ".ini", ".cfg", ".conf", ".env", ".py", ".js", ".html", ".css",
        ".sh", ".sql", ".c", ".cpp", ".java", ".ts", ".tsx", ".jsx",
        ".bat", ".cmd", ".properties", ".toml", ".gitignore",
        ".nfo", ".reg", ".inf", ".h", ".hpp", ".vue", ".svelte"
    }
    if category == "code" or ext in TEXT_EXTENSIONS:
        MAX_TEXT_SIZE = 2 * 1024 * 1024  # 2 MB máximo para vista previa
        if file_size > MAX_TEXT_SIZE:
            return jsonify({
                "type": "text",
                "name": os.path.basename(abs_path),
                "size": file_size,
                "error": f"El archivo es muy grande para vista previa ({format_size(file_size)}). Descárgalo para verlo."
            })
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return jsonify({
                "type": "text",
                "name": os.path.basename(abs_path),
                "extension": ext[1:] if ext else "",
                "size": file_size,
                "content": content,
            })
        except Exception as e:
            return jsonify({"error": f"Error leyendo archivo: {str(e)}"}), 500

    # 8. Archivos binarios
    return jsonify({
        "type": "binary",
        "name": os.path.basename(abs_path),
        "extension": ext[1:] if ext else "",
        "size": file_size,
        "message": "Este tipo de archivo no tiene vista previa web directa. Puedes descargarlo a tu dispositivo."
    })


@file_bp.route("/api/download", methods=["GET"])
@require_auth
def download():
    """Descarga un archivo específico como adjunto."""
    shared_dir = current_app.config["SHARED_DIR"]
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)

    if not is_valid or not os.path.isfile(abs_path):
        return jsonify({"error": "Archivo no encontrado o acceso restringido"}), 404

    filename = os.path.basename(abs_path)
    return send_file(abs_path, as_attachment=True, download_name=filename)


@file_bp.route("/api/upload", methods=["POST"])
@require_auth
def upload():
    """Sube uno o múltiples archivos al directorio indicado de forma segura."""
    if current_app.config.get("READONLY", False):
        return jsonify({"error": "El servidor está en modo sólo lectura"}), 403

    shared_dir = current_app.config["SHARED_DIR"]
    rel_path = request.form.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)

    if not is_valid or not os.path.isdir(abs_path):
        return jsonify({"error": "Directorio de destino no válido o acceso denegado"}), 400

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or uploaded_files[0].filename == "":
        return jsonify({"error": "No se recibieron archivos para subir"}), 400

    saved_list = []
    for file in uploaded_files:
        if not file or not file.filename:
            continue

        raw_filename = os.path.basename(file.filename)
        safe_name = secure_filename(raw_filename)
        if not safe_name:
            safe_name = f"upload_{int(time.time())}"

        # Prevención contra subida de scripts maliciosos en directorios raíz
        file_ext = Path(safe_name).suffix.lower()
        if file_ext in DANGEROUS_UPLOAD_EXTS and abs_path in ("/", "\\", "/etc", "/usr", "/bin"):
            return jsonify({"error": f"Por seguridad no se permite subir ejecutables ({file_ext}) a carpetas del sistema"}), 403

        # Evitar sobreescrituras accidentales
        dest_path = os.path.join(abs_path, safe_name)
        base, ext = os.path.splitext(safe_name)
        counter = 1
        while os.path.exists(dest_path):
            safe_name = f"{base}_{counter}{ext}"
            dest_path = os.path.join(abs_path, safe_name)
            counter += 1

        try:
            file.save(dest_path)
            saved_list.append(safe_name)
        except Exception as e:
            return jsonify({"error": f"Error guardando {safe_name}: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "message": f"{len(saved_list)} archivo(s) subido(s) con éxito",
        "uploaded": saved_list,
    })


@file_bp.route("/api/mkdir", methods=["POST"])
@require_auth
def mkdir():
    """Crea una nueva carpeta dentro del directorio especificado."""
    if current_app.config.get("READONLY", False):
        return jsonify({"error": "El servidor está en modo sólo lectura"}), 403

    shared_dir = current_app.config["SHARED_DIR"]
    data = request.get_json(silent=True) or {}
    rel_path = data.get("path", "").strip()
    folder_name = data.get("name", "").strip()

    if not folder_name:
        return jsonify({"error": "El nombre de la carpeta no puede estar vacío"}), 400

    safe_folder_name = secure_filename(folder_name) or folder_name.replace("/", "_").replace("\\", "_")
    target_rel = os.path.join(rel_path, safe_folder_name) if rel_path else safe_folder_name
    abs_path, is_valid = safe_resolve_path(target_rel, shared_dir)

    if not is_valid:
        return jsonify({"error": "Ruta inválida o protegida"}), 400

    if os.path.exists(abs_path):
        return jsonify({"error": "Ya existe una carpeta o archivo con ese nombre"}), 400

    try:
        os.makedirs(abs_path, exist_ok=True)
        return jsonify({"success": True, "message": f"Carpeta '{safe_folder_name}' creada"})
    except Exception as e:
        return jsonify({"error": f"No se pudo crear la carpeta: {str(e)}"}), 500


@file_bp.route("/api/delete", methods=["POST"])
@require_auth
def delete():
    """Elimina un archivo de forma segura."""
    if current_app.config.get("READONLY", False):
        return jsonify({"error": "El servidor está en modo sólo lectura"}), 403

    shared_dir = current_app.config["SHARED_DIR"]
    data = request.get_json(silent=True) or {}
    rel_path = data.get("path", "").strip()

    if not rel_path:
        return jsonify({"error": "No se puede eliminar el directorio raíz"}), 400

    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)
    if not is_valid or not os.path.exists(abs_path):
        return jsonify({"error": "Archivo no encontrado o acceso restringido"}), 404

    # Protección reforzada: nunca permitir borrar carpetas ni archivos del sistema
    if os.path.isdir(abs_path):
        return jsonify({"error": "La eliminación de carpetas está desactivada por seguridad para proteger tus datos"}), 403

    if is_protected_system_path(abs_path):
        return jsonify({"error": "Operación bloqueada: archivo protegido del sistema"}), 403

    try:
        os.remove(abs_path)
        return jsonify({"success": True, "message": "Archivo eliminado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500

