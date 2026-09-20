#!/usr/bin/env python3
"""
NavByte - Servidor de Archivos y Streaming para Móvil y PC
Permite explorar, descargar, subir archivos y reproducir audio desde el celular.
"""

import os
import sys
import io
import time
import socket
import shutil
import json
import secrets
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, jsonify, send_file, abort, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Configuración y argumentos de línea de comandos
parser = argparse.ArgumentParser(description="NavByte - Servidor Web Móvil")
parser.add_argument("-f", "--folder", default="/", help="Carpeta raíz a compartir (por defecto: / = todo el PC)")
parser.add_argument("-p", "--port", type=int, default=5000, help="Puerto de escucha (por defecto: 5000)")
parser.add_argument("-H", "--host", default="0.0.0.0", help="Host de escucha (por defecto: 0.0.0.0)")
parser.add_argument("--readonly", action="store_true", help="Modo sólo lectura (deshabilita subida y borrado)")
parser.add_argument("--set-password", dest="set_password", default=None,
                    help="Establecer la contraseña de acceso (ej: ./start.sh --set-password MiClave123)")
parser.add_argument("--set-user", dest="set_user", default=None,
                    help="Establecer el usuario de acceso (ej: ./start.sh --set-user admin)")

args, unknown = parser.parse_known_args()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SHARED_DIR = os.path.abspath(args.folder) if os.path.isabs(args.folder) else os.path.abspath(os.path.join(BASE_DIR, args.folder))

# Crear carpeta solo si no es la raíz del sistema
if SHARED_DIR != "/" and SHARED_DIR != "\\":
    os.makedirs(SHARED_DIR, exist_ok=True)

# Carpetas virtuales del SO que se deben omitir para evitar cuelgues o errores de permiso
SYSTEM_SKIP_DIRS = {
    "proc", "sys", "dev", "run", "snap", "lost+found",
    "cgroup", "cgroup2", "pstore", "bpf", "debugfs",
    "tracefs", "fusectl", "configfs", "securityfs",
    "efivarfs", "mqueue", "hugetlbfs", "ramfs",
}

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024
app.config["SHARED_DIR"] = SHARED_DIR
app.config["READONLY"] = args.readonly
app.config["PERMANENT_SESSION_LIFETIME"] = 7 * 24 * 3600  # Sesiones duran 7 días
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Deshabilitar caché estático para reflejar cambios en móviles inmediatamente

# ===========================================================================
# SISTEMA DE SEGURIDAD - Clave Secreta y Contraseña de Acceso
# ===========================================================================

SECRET_KEY_FILE = os.path.join(BASE_DIR, ".secret_key")
PASSWORD_HASH_FILE = os.path.join(BASE_DIR, ".password_hash")
AUTH_CONFIG_FILE = os.path.join(BASE_DIR, ".auth_credentials.json")

# Generar o cargar clave secreta persistente para sesiones Flask
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "rb") as f:
        app.secret_key = f.read()
else:
    app.secret_key = secrets.token_bytes(64)
    with open(SECRET_KEY_FILE, "wb") as f:
        f.write(app.secret_key)
    try:
        os.chmod(SECRET_KEY_FILE, 0o600)  # Solo el propietario puede leer
    except Exception:
        pass

def load_auth_config():
    """Carga usuario y hash de contraseña guardados."""
    username = "admin"
    password_hash = None
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                username = data.get("username", "admin")
                password_hash = data.get("password_hash", None)
        except Exception:
            pass
    elif os.path.exists(PASSWORD_HASH_FILE):
        try:
            with open(PASSWORD_HASH_FILE, "r", encoding="utf-8") as f:
                password_hash = f.read().strip()
        except Exception:
            pass
    return username, password_hash

def save_auth_config(username: str, password_raw: str = None, password_hash: str = None):
    """Guarda usuario y hash de contraseña con permisos restringidos 600."""
    data = {}
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if username:
        data["username"] = username.strip()
    if password_raw:
        data["password_hash"] = generate_password_hash(password_raw, method="pbkdf2:sha256", salt_length=16)
    elif password_hash:
        data["password_hash"] = password_hash
    with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    try:
        os.chmod(AUTH_CONFIG_FILE, 0o600)
    except Exception:
        pass
    if "password_hash" in data:
        with open(PASSWORD_HASH_FILE, "w", encoding="utf-8") as f:
            f.write(data["password_hash"])
        try:
            os.chmod(PASSWORD_HASH_FILE, 0o600)
        except Exception:
            pass
    return data

# Manejar --set-password y --set-user: guardar credenciales y salir
if args.set_password or args.set_user:
    u, p_hash = load_auth_config()
    new_user = args.set_user if args.set_user else u
    new_hash = generate_password_hash(args.set_password, method="pbkdf2:sha256", salt_length=16) if args.set_password else p_hash
    save_auth_config(new_user, password_hash=new_hash)
    print(f"\n✅ Credenciales de acceso actualizadas correctamente.")
    print(f"   Usuario:    {new_user}")
    if args.set_password:
        print(f"   Contraseña: [Actualizada con hash pbkdf2:sha256]")
    print(f"   Archivo:    {AUTH_CONFIG_FILE}")
    print(f"\nAhora puedes iniciar el servidor con: ./start.sh\n")
    sys.exit(0)

# Cargar credenciales activas
STORED_USERNAME, STORED_PASSWORD_HASH = load_auth_config()
if not STORED_PASSWORD_HASH:
    print("\n" + "="*60)
    print(" ⚠️  PRIMER USO: No hay contraseña configurada.")
    print("="*60)
    print(" Para proteger el servidor, ejecuta:")
    print("   ./start.sh --set-user admin --set-password TuContraseña")
    print(" (O simplemente ejecuta ./start.sh para el asistente automático)")
    print("\n Sin contraseña, CUALQUIER persona en tu red WiFi")
    print(" podrá acceder a tus archivos.")
    print("="*60 + "\n")
    REQUIRE_AUTH = False
else:
    REQUIRE_AUTH = True

# Rate limiting: registro de IPs con intentos fallidos de login
# { ip_address: {"count": int, "blocked_until": float} }
login_attempts: dict = {}
MAX_ATTEMPTS = 5       # Máximo intentos fallidos
BLOCK_SECONDS = 300   # Bloqueo de 5 minutos tras agotar intentos

# Extensiones reconocidas por categoría
EXT_CATEGORIES = {
    "audio": {".mp3", ".wav", ".wave", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".wma", ".opus", ".aif", ".aiff"},
    "midi": {".mid", ".midi"},
    "video": {".mp4", ".mkv", ".webm", ".avi", ".mov", ".wmv", ".flv"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"},
    "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".rtf", ".odt", ".csv"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "code": {".py", ".js", ".html", ".css", ".json", ".sh", ".c", ".cpp", ".java", ".xml", ".yaml", ".yml", ".sql"},
}

# Tipos MIME explícitos para streaming de audio compatible con móviles (Safari/Chrome)
AUDIO_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".wave": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".opus": "audio/opus",
    ".wma": "audio/x-ms-wma",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
}

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
}

VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}


def get_local_ip() -> str:
    """Detecta la IP local de la computadora en la red WiFi/Ethernet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def format_size(bytes_size: int) -> str:
    """Convierte bytes a formato legible (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}" if unit != "B" else f"{bytes_size} B"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def get_file_category(ext: str) -> str:
    """Retorna la categoría del archivo según su extensión."""
    ext = ext.lower()
    for category, extensions in EXT_CATEGORIES.items():
        if ext in extensions:
            return category
    return "other"


def safe_resolve_path(rel_path: str) -> tuple[str, bool]:
    """
    Resuelve de forma segura una ruta relativa dentro de SHARED_DIR.
    Previene vulnerabilidades de Path Traversal (ej: ../../../etc/passwd).
    Retorna (ruta_absoluta, es_valida).
    """
    if not rel_path or not rel_path.strip():
        return SHARED_DIR, True

    clean_rel = rel_path.strip().strip("/\\")
    if not clean_rel:
        return SHARED_DIR, True

    # Soporte para Windows (ej: C:\ o C:/carpeta)
    if sys.platform == "win32":
        if len(clean_rel) >= 2 and clean_rel[1] == ":":
            target = os.path.abspath(clean_rel)
            return target, True
        if SHARED_DIR in ("/", "\\"):
            system_drive = os.environ.get("SystemDrive", "C:")
            target = os.path.abspath(os.path.join(f"{system_drive}\\", clean_rel))
            return target, True

    target = os.path.abspath(os.path.join(SHARED_DIR, clean_rel))

    # Comprobar que target esté estrictamente dentro de SHARED_DIR si no es la raíz /
    if SHARED_DIR != "/" and SHARED_DIR != "\\":
        try:
            common = os.path.commonpath([SHARED_DIR, target])
            if common != SHARED_DIR:
                return SHARED_DIR, False
        except ValueError:
            return SHARED_DIR, False

    return target, True


@app.after_request
def add_no_cache_headers(response):
    """Evita almacenamiento en caché agresivo en navegadores móviles durante actualizaciones."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    """Sirve la interfaz web móvil responsiva con cache-busting dinámico."""
    import time
    return render_template("index.html", version_ts=int(time.time()))


# ===========================================================================
# AUTENTICACIÓN Y CONTROL DE ACCESO
# ===========================================================================

def require_auth(f):
    """Decorador que protege endpoints: retorna 401 si no hay sesión activa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if REQUIRE_AUTH and not session.get("authenticated"):
            return jsonify({"error": "No autorizado. Inicia sesión primero.", "auth_required": True}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/auth_status", methods=["GET"])
def auth_status():
    """Verifica si la sesión actual está autenticada."""
    return jsonify({
        "authenticated": session.get("authenticated", False),
        "auth_required": REQUIRE_AUTH,
        "username": session.get("username", None),
    })


@app.route("/api/login", methods=["POST"])
def login():
    """Autenticación con usuario y contraseña. Implementa rate limiting anti fuerza bruta."""
    if not REQUIRE_AUTH:
        session["authenticated"] = True
        session["username"] = STORED_USERNAME
        session.permanent = True
        return jsonify({"success": True, "message": "Acceso sin contraseña", "username": STORED_USERNAME})

    # Obtener IP del cliente para rate limiting
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    now = time.time()

    # Verificar si la IP está bloqueada
    attempt_data = login_attempts.get(client_ip, {"count": 0, "blocked_until": 0})
    if attempt_data["blocked_until"] > now:
        remaining = int(attempt_data["blocked_until"] - now)
        return jsonify({
            "success": False,
            "error": f"Demasiados intentos fallidos. Espera {remaining} segundos.",
            "blocked": True,
            "retry_after": remaining,
        }), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username:
        return jsonify({"success": False, "error": "Ingresa el nombre de usuario"}), 400
    if not password:
        return jsonify({"success": False, "error": "Ingresa la contraseña"}), 400

    # Coincidencia de usuario (insensible a mayúsculas para comodidad móvil)
    # y verificación criptográfica estricta de la contraseña
    user_ok = (username.lower() == STORED_USERNAME.lower())
    password_ok = check_password_hash(STORED_PASSWORD_HASH, password)

    if user_ok and password_ok:
        # ✅ Login exitoso: limpiar intentos y crear sesión
        login_attempts.pop(client_ip, None)
        session["authenticated"] = True
        session["username"] = STORED_USERNAME
        session.permanent = True
        return jsonify({"success": True, "message": "Acceso concedido", "username": STORED_USERNAME})
    else:
        # ❌ Credenciales incorrectas: registrar intento fallido
        attempt_data["count"] = attempt_data.get("count", 0) + 1
        if attempt_data["count"] >= MAX_ATTEMPTS:
            attempt_data["blocked_until"] = now + BLOCK_SECONDS
            attempt_data["count"] = 0
            login_attempts[client_ip] = attempt_data
            return jsonify({
                "success": False,
                "error": f"Cuenta bloqueada por {BLOCK_SECONDS // 60} minutos tras demasiados intentos fallidos.",
                "blocked": True,
                "retry_after": BLOCK_SECONDS,
            }), 429
        login_attempts[client_ip] = attempt_data
        remaining_attempts = MAX_ATTEMPTS - attempt_data["count"]
        return jsonify({
            "success": False,
            "error": f"Usuario o contraseña incorrectos. Intentos restantes: {remaining_attempts}.",
        }), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    """Cierra la sesión actual."""
    session.clear()
    return jsonify({"success": True, "message": "Sesión cerrada correctamente"})

@app.route("/api/info", methods=["GET"])
@require_auth
def get_info():
    """Información del sistema y estado del servidor."""
    try:
        total, used, free = shutil.disk_usage(SHARED_DIR)
        disk_info = {
            "total": format_size(total),
            "used": format_size(used),
            "free": format_size(free),
            "percent": round((used / total) * 100, 1),
        }
    except Exception:
        disk_info = {"total": "N/A", "used": "N/A", "free": "N/A", "percent": 0}

    local_ip = get_local_ip()
    port = request.environ.get("SERVER_PORT", args.port)

    return jsonify({
        "hostname": socket.gethostname(),
        "ip": local_ip,
        "port": port,
        "access_url": f"http://{local_ip}:{port}",
        "shared_dir": SHARED_DIR,
        "readonly": app.config["READONLY"],
        "disk": disk_info,
    })


def detect_system_drives() -> list[dict]:
    r"""
    Detecta y retorna las particiones/unidades montadas reales del sistema.
    Soporta Linux (/proc/mounts) y Windows (letras de unidad C:\, D:\, etc.).
    Filtra montajes virtuales del SO y particiones reservadas.
    """
    drives = []

    # Soporte nativo para Windows (letras de unidad C:\, D:\, etc.)
    if sys.platform == "win32":
        import string
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                label = ""
                fs_type = "NTFS"
                try:
                    vol_buf = ctypes.create_unicode_buffer(1024)
                    fs_buf = ctypes.create_unicode_buffer(1024)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        drive_path, vol_buf, len(vol_buf), None, None, None, fs_buf, len(fs_buf)
                    )
                    label = vol_buf.value
                    fs_type = fs_buf.value
                except Exception:
                    pass

                try:
                    total, used, free = shutil.disk_usage(drive_path)
                    disk_info = {
                        "total": format_size(total),
                        "free": format_size(free),
                        "percent_used": round((used / total) * 100, 1),
                    }
                except Exception:
                    disk_info = {"total": "N/A", "free": "N/A", "percent_used": 0}

                name = f"Disco {letter}: ({label})" if label else f"Disco Local ({letter}:)"
                drives.append({
                    "name": name,
                    "mount_point": drive_path,
                    "path": f"{letter}:",
                    "device": f"{letter}:",
                    "fs_type": fs_type,
                    "disk": disk_info,
                })
            bitmask >>= 1
        return drives

    # Soporte para Linux
    VIRTUAL_FS_TYPES = {
        "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup",
        "cgroup2", "pstore", "bpf", "tracefs", "fusectl", "configfs",
        "securityfs", "efivarfs", "mqueue", "hugetlbfs", "ramfs",
        "autofs", "debugfs", "overlay",
    }
    SKIP_MOUNT_PREFIXES = ("/proc", "/sys", "/dev", "/run", "/snap", "/var/lib/docker", "/boot")

    seen_mounts = set()
    home_dir = os.path.expanduser("~")
    home_rel = home_dir.lstrip("/")

    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                device, mount_point, fs_type = parts[0], parts[1], parts[2]
                mount_point = mount_point.replace('\\040', ' ').replace('\\011', '\t')

                if fs_type in VIRTUAL_FS_TYPES:
                    continue

                if any(mount_point.startswith(p) for p in SKIP_MOUNT_PREFIXES):
                    continue

                if mount_point in seen_mounts:
                    continue
                seen_mounts.add(mount_point)

                try:
                    total, used, free = shutil.disk_usage(mount_point)
                    disk_info = {
                        "total": format_size(total),
                        "free": format_size(free),
                        "percent_used": round((used / total) * 100, 1),
                    }
                except Exception:
                    disk_info = {"total": "N/A", "free": "N/A", "percent_used": 0}

                if mount_point == "/":
                    if os.path.isdir(home_dir):
                        display_name = "Disco Local (Archivos Personales)"
                        rel = home_rel
                    else:
                        display_name = "Disco Principal"
                        rel = "home"
                else:
                    display_name = os.path.basename(mount_point) or "Unidad de Almacenamiento"
                    if SHARED_DIR == "/":
                        rel = mount_point.lstrip("/")
                    else:
                        try:
                            rel = os.path.relpath(mount_point, SHARED_DIR)
                        except ValueError:
                            continue

                drives.append({
                    "name": display_name,
                    "mount_point": mount_point,
                    "path": rel,
                    "device": device,
                    "fs_type": fs_type,
                    "disk": disk_info,
                })
    except Exception:
        pass

    def sort_key(d):
        mp = d["mount_point"]
        if mp == "/": return 0
        if mp.startswith("/home"): return 1
        if mp.startswith("/media"): return 2
        return 3

    drives.sort(key=sort_key)
    return drives


@app.route("/api/browse", methods=["GET"])
@require_auth
def browse():
    """
    Lista archivos y carpetas en una ruta relativa dada.
    Parámetros GET:
      path: ruta relativa dentro de SHARED_DIR (opcional, default "")
    """
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path)

    if not is_valid or not os.path.exists(abs_path):
        return jsonify({"error": "Ruta no válida o no encontrada"}), 404

    if not os.path.isdir(abs_path):
        return jsonify({"error": "La ruta especificada no es una carpeta"}), 400

    # Calcular breadcrumbs y ruta padre coherente con las unidades del PC
    drives = detect_system_drives()
    drive_map = {d["path"]: d for d in drives if d["path"]}

    # Normalizar ruta relativa para breadcrumbs y jerarquía
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
    if norm_rel == "." and SHARED_DIR == "/":
        return jsonify({
            "current_path": "",
            "parent_path": None,
            "breadcrumbs": breadcrumbs,
            "items": [],
            "total_items": 0,
            "is_root": True,
        })

    items = []
    try:
        with os.scandir(abs_path) as entries:
            for entry in entries:
                name = entry.name
                # Omitir archivos ocultos del sistema
                if name.startswith("."):
                    continue

                # Omitir carpetas virtuales del SO (proc, sys, dev, etc.) para evitar cuelgues
                if entry.is_dir(follow_symlinks=False) and name.lower() in SYSTEM_SKIP_DIRS:
                    continue

                try:
                    stat = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)
                    size = stat.st_size if not is_dir else 0
                    mtime = stat.st_mtime
                    mtime_dt = datetime.fromtimestamp(mtime)
                    mtime_str = mtime_dt.strftime("%d/%m/%Y %H:%M")

                    ext = Path(name).suffix.lower() if not is_dir else ""
                    category = "folder" if is_dir else get_file_category(ext)

                    # Subruta relativa para el item
                    item_rel = os.path.relpath(entry.path, SHARED_DIR).replace("\\", "/")

                    items.append({
                        "name": name,
                        "path": item_rel,
                        "is_dir": is_dir,
                        "size": size,
                        "size_human": format_size(size) if not is_dir else "--",
                        "mtime": mtime,
                        "mtime_human": mtime_str,
                        "extension": ext[1:] if ext else "",
                        "category": category,
                        "can_stream": category in ("audio", "video"),
                    })
                except (OSError, PermissionError):
                    continue
    except PermissionError:
        return jsonify({"error": "Permiso denegado para leer este directorio"}), 403

    # Ordenar: primero directorios alfabéticamente, luego archivos alfabéticamente
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    return jsonify({
        "current_path": "" if norm_rel == "." else norm_rel.replace("\\", "/"),
        "parent_path": parent_path,
        "breadcrumbs": breadcrumbs,
        "items": items,
        "total_items": len(items),
        "is_root": norm_rel == ".",
    })


@app.route("/api/search", methods=["GET"])
@require_auth
def search_files():
    """
    Busca recursivamente archivos y carpetas dentro de la ruta especificada.
    Parámetros GET:
      path: carpeta base donde buscar (ej. 'Musica' o 'Discos')
      q: término de búsqueda (ej. 'salsa', 'rock', 'sample')
      max_results: límite de resultados (default 80)
    """
    import time
    start_time = time.time()
    MAX_SEARCH_SECONDS = 5.0

    rel_path = request.args.get("path", "").strip()
    query = request.args.get("q", "").strip().lower()

    if not query:
        return jsonify({"results": [], "query": "", "total": 0})

    abs_path, is_valid = safe_resolve_path(rel_path)
    if not is_valid or not os.path.exists(abs_path) or not os.path.isdir(abs_path):
        return jsonify({"error": "Ruta de búsqueda no válida"}), 400

    max_results = min(int(request.args.get("max_results", 80)), 200)
    results = []

    SKIP_FOLDERS = {
        "$recycle.bin", "system volume information", "found.000", "found.001",
        ".git", ".cache", "node_modules", "__pycache__", ".vscode", ".idea",
        "proc", "sys", "dev", "run", "snap", "boot", "lost+found",
    }

    try:
        search_roots = []
        if not rel_path or rel_path in (".", "/"):
            drives = detect_system_drives()
            search_roots = [d["mount_point"] for d in drives if d["mount_point"] != "/"]
            if not search_roots:
                search_roots = [SHARED_DIR]
        else:
            search_roots = [abs_path]

        for s_root in search_roots:
            if len(results) >= max_results or (time.time() - start_time) > MAX_SEARCH_SECONDS:
                break
            for root, dirs, files in os.walk(s_root, topdown=True):
                # Evitar carpetas del sistema y papelera de reciclaje
                root_lower = root.lower()
                if any(sf in root_lower for sf in SKIP_FOLDERS) or any(f"/{sd}" in root_lower for sd in SYSTEM_SKIP_DIRS):
                    dirs[:] = []
                    continue

                # Filtrar subdirectorios in-place
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d.lower() not in SKIP_FOLDERS and d.lower() not in SYSTEM_SKIP_DIRS
                ]

                # 1. Comprobar si directorios coinciden
                for d in dirs:
                    if query in d.lower():
                        full_dir_path = os.path.join(root, d)
                        try:
                            stat = os.stat(full_dir_path)
                            item_rel = os.path.relpath(full_dir_path, SHARED_DIR).replace("\\", "/")
                            parent_rel = os.path.relpath(root, SHARED_DIR).replace("\\", "/")
                            if parent_rel == ".":
                                parent_rel = ""
                            results.append({
                                "name": d,
                                "path": item_rel,
                                "parent_path": parent_rel,
                                "is_dir": True,
                                "size": 0,
                                "size_human": "Carpeta",
                                "mtime": stat.st_mtime,
                                "mtime_human": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                                "extension": "",
                                "category": "folder",
                                "can_stream": False,
                            })
                            if len(results) >= max_results:
                                break
                        except (OSError, PermissionError):
                            continue

                if len(results) >= max_results or (time.time() - start_time) > MAX_SEARCH_SECONDS:
                    break

                # 2. Comprobar archivos que coincidan
                for f in files:
                    if f.startswith("."):
                        continue
                    if query in f.lower():
                        full_file_path = os.path.join(root, f)
                        try:
                            stat = os.stat(full_file_path)
                            size = stat.st_size
                            ext = Path(f).suffix.lower()
                            category = get_file_category(ext)
                            item_rel = os.path.relpath(full_file_path, SHARED_DIR).replace("\\", "/")
                            parent_rel = os.path.relpath(root, SHARED_DIR).replace("\\", "/")
                            if parent_rel == ".":
                                parent_rel = ""

                            results.append({
                                "name": f,
                                "path": item_rel,
                                "parent_path": parent_rel,
                                "is_dir": False,
                                "size": size,
                                "size_human": format_size(size),
                                "mtime": stat.st_mtime,
                                "mtime_human": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                                "extension": ext[1:] if ext else "",
                                "category": category,
                                "can_stream": category in ("audio", "video"),
                            })
                            if len(results) >= max_results:
                                break
                        except (OSError, PermissionError):
                            continue

                if len(results) >= max_results or (time.time() - start_time) > MAX_SEARCH_SECONDS:
                    break
    except Exception as e:
        app.logger.error(f"Error en búsqueda: {e}")

    results.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    return jsonify({
        "query": query,
        "base_path": rel_path,
        "results": results,
        "total": len(results),
        "limit_reached": len(results) >= max_results,
        "elapsed_seconds": round(time.time() - start_time, 2),
    })


@app.route("/api/preview", methods=["GET"])
@require_auth
def preview():
    """
    Sirve un archivo para visualización inline en el navegador.
    - Imágenes y videos: devuelve con Content-Disposition inline (streaming con rangos).
    - Texto/código: devuelve el contenido en JSON con metadatos.
    - PDFs: devuelve inline para que el navegador los abra.
    """
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path)

    if not is_valid or not os.path.isfile(abs_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    ext = Path(abs_path).suffix.lower()
    category = get_file_category(ext)
    file_size = os.path.getsize(abs_path)

    # Para imágenes: servir con MIME explícito
    if category == "image":
        mime = IMAGE_MIME_TYPES.get(ext, "image/jpeg")
        return send_file(abs_path, mimetype=mime, conditional=True)

    # Para videos: servir con soporte de Range y MIME explícito
    if category == "video":
        mime = VIDEO_MIME_TYPES.get(ext, "video/mp4")
        return send_file(abs_path, mimetype=mime, conditional=True)

    # Para PDFs: servir con MIME application/pdf
    if ext == ".pdf":
        return send_file(abs_path, mimetype="application/pdf", conditional=True)

    # Para audio: streaming inline con MIME type explícito
    if category == "audio":
        mime = AUDIO_MIME_TYPES.get(ext, "audio/mpeg")
        return send_file(abs_path, mimetype=mime, conditional=True)

    # Para archivos MIDI: secuencia musical digital para DAW
    if category == "midi":
        return jsonify({
            "type": "midi",
            "name": os.path.basename(abs_path),
            "extension": ext[1:] if ext else "mid",
            "size": file_size,
            "message": "Archivo MIDI (Secuencia musical para DAW como FL Studio o Ableton)."
        })

    # Para documentos ofimáticos binarios (Word, Excel, PowerPoint, etc.)
    if ext in (".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf"):
        return jsonify({
            "type": "office",
            "name": os.path.basename(abs_path),
            "extension": ext[1:] if ext else "",
            "size": file_size,
            "message": "Documento ofimático. Descárgalo para abrirlo en Word, Excel, PowerPoint o tu app preferida."
        })

    # Para archivos de texto plano y código: devolver contenido como JSON
    TEXT_EXTENSIONS = {
        ".txt", ".md", ".csv", ".log", ".json", ".xml", ".yaml", ".yml",
        ".ini", ".cfg", ".conf", ".env", ".py", ".js", ".html", ".css",
        ".sh", ".sql", ".c", ".cpp", ".java", ".ts", ".tsx", ".jsx",
        ".bat", ".cmd", ".properties", ".toml", ".gitignore", ".env",
        ".nfo", ".reg", ".inf", ".h", ".hpp", ".vue", ".svelte"
    }
    if category == "code" or ext in TEXT_EXTENSIONS:
        MAX_TEXT_SIZE = 2 * 1024 * 1024  # 2 MB máximo para texto
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

    # Para otros archivos no previsualizables: tarjeta informativa con descarga directa
    return jsonify({
        "type": "binary",
        "name": os.path.basename(abs_path),
        "extension": ext[1:] if ext else "",
        "size": file_size,
        "message": "Este tipo de archivo no tiene vista previa web directa. Puedes descargarlo a tu dispositivo."
    })


@app.route("/api/drives", methods=["GET"])
@require_auth
def get_drives():
    """Detecta y retorna las particiones/unidades montadas reales del sistema."""
    drives = detect_system_drives()
    return jsonify({"drives": drives, "total": len(drives)})


@app.route("/api/download", methods=["GET"])
@require_auth
def download():
    """Descarga un archivo específico como adjunto."""
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path)

    if not is_valid or not os.path.isfile(abs_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    filename = os.path.basename(abs_path)
    return send_file(abs_path, as_attachment=True, download_name=filename)


@app.route("/api/stream", methods=["GET"])
@require_auth
def stream():
    """
    Transmite archivos multimedia (audio/video) con soporte para Range requests
    (HTTP 206 Partial Content), permitiendo adelantar/retroceder en el reproductor.
    """
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path)

    if not is_valid or not os.path.isfile(abs_path):
        return jsonify({"error": "Archivo multimedia no encontrado"}), 404

    ext = Path(abs_path).suffix.lower()
    mime = AUDIO_MIME_TYPES.get(ext)
    if mime:
        return send_file(abs_path, mimetype=mime, conditional=True)
    return send_file(abs_path, conditional=True)


@app.route("/api/upload", methods=["POST"])
@require_auth
def upload():
    """Sube uno o múltiples archivos al directorio indicado."""
    if app.config["READONLY"]:
        return jsonify({"error": "El servidor está en modo sólo lectura"}), 403

    rel_path = request.form.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path)

    if not is_valid or not os.path.isdir(abs_path):
        return jsonify({"error": "Directorio de destino no válido"}), 400

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

        # Evitar sobreescrituras accidentales agregando número si ya existe
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


@app.route("/api/mkdir", methods=["POST"])
@require_auth
def mkdir():
    """Crea una nueva carpeta dentro del directorio especificado."""
    if app.config["READONLY"]:
        return jsonify({"error": "El servidor está en modo sólo lectura"}), 403

    data = request.get_json(silent=True) or {}
    rel_path = data.get("path", "").strip()
    folder_name = data.get("name", "").strip()

    if not folder_name:
        return jsonify({"error": "El nombre de la carpeta no puede estar vacío"}), 400

    # Limpiar nombre de carpeta
    safe_folder_name = secure_filename(folder_name) or folder_name.replace("/", "_").replace("\\", "_")
    target_rel = os.path.join(rel_path, safe_folder_name) if rel_path else safe_folder_name
    abs_path, is_valid = safe_resolve_path(target_rel)

    if not is_valid:
        return jsonify({"error": "Ruta inválida"}), 400

    if os.path.exists(abs_path):
        return jsonify({"error": "Ya existe una carpeta o archivo con ese nombre"}), 400

    try:
        os.makedirs(abs_path, exist_ok=True)
        return jsonify({"success": True, "message": f"Carpeta '{safe_folder_name}' creada"})
    except Exception as e:
        return jsonify({"error": f"No se pudo crear la carpeta: {str(e)}"}), 500


@app.route("/api/delete", methods=["POST"])
@require_auth
def delete():
    """Elimina un archivo o carpeta vacía."""
    if app.config["READONLY"]:
        return jsonify({"error": "El servidor está en modo sólo lectura"}), 403

    data = request.get_json(silent=True) or {}
    rel_path = data.get("path", "").strip()

    if not rel_path:
        return jsonify({"error": "No se puede eliminar el directorio raíz"}), 400

    abs_path, is_valid = safe_resolve_path(rel_path)
    if not is_valid or not os.path.exists(abs_path):
        return jsonify({"error": "Archivo o carpeta no encontrada"}), 404

    try:
        if os.path.isdir(abs_path):
            return jsonify({"error": "La eliminación de carpetas está desactivada por seguridad para proteger tus datos"}), 403
        else:
            os.remove(abs_path)
        return jsonify({"success": True, "message": "Archivo eliminado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500


@app.route("/api/qr", methods=["GET"])
@require_auth
def get_qr_image():
    """Genera y retorna la imagen (PNG o SVG) del código QR para escanear con el celular."""
    try:
        import qrcode

        local_ip = get_local_ip()
        port = request.environ.get("SERVER_PORT", args.port)
        url = f"http://{local_ip}:{port}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        try:
            # Intento generar PNG con Pillow
            img = qr.make_image(fill_color="#10b981", back_color="#0f172a")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return send_file(buf, mimetype="image/png")
        except Exception:
            # Fallback a SVG si Pillow falla
            import qrcode.image.svg
            svg_factory = qrcode.image.svg.SvgImage
            svg_qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
                image_factory=svg_factory,
            )
            svg_qr.add_data(url)
            svg_qr.make(fit=True)
            img = svg_qr.make_image()
            buf = io.BytesIO()
            img.save(buf)
            buf.seek(0)
            return send_file(buf, mimetype="image/svg+xml")
    except Exception as e:
        return jsonify({"error": f"No se pudo generar el QR: {str(e)}"}), 500


def print_banner(host: str, port: int, shared_dir: str):
    """Imprime el banner de inicio con la IP y código QR en la consola."""
    local_ip = get_local_ip()
    url = f"http://{local_ip}:{port}"

    print("\n" + "=" * 62)
    print(" 🚀 SERVIDOR NAVBYTE INICIADO CON ÉXITO")
    print("=" * 62)
    print(f" 📂 Carpeta compartida: {shared_dir}")
    print(f" 🌐 En tu computadora:  http://localhost:{port}")
    print(f" 📱 En tu celular (WiFi): \033[1;32m{url}\033[0m")
    print("=" * 62)
    print(" Escanea este código QR con la cámara de tu celular:\n")

    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass

    print("\n Presiona CTRL+C para detener el servidor.\n" + "=" * 62 + "\n")


if __name__ == "__main__":
    print_banner(args.host, args.port, SHARED_DIR)
    app.run(host=args.host, port=args.port, debug=False)
