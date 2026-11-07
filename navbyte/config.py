# -*- coding: utf-8 -*-
"""
NavByte - Módulo de Configuración y Constantes
Centraliza la configuración de la aplicación, constantes MIME y listas de exclusión de seguridad.
"""

import os
import sys
import argparse
from typing import Set, Dict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Extensiones reconocidas por categoría
EXT_CATEGORIES: Dict[str, Set[str]] = {
    "audio": {".mp3", ".wav", ".wave", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".wma", ".opus", ".aif", ".aiff"},
    "midi": {".mid", ".midi"},
    "video": {".mp4", ".mkv", ".webm", ".avi", ".mov", ".wmv", ".flv"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"},
    "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".rtf", ".odt", ".csv"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "code": {
        ".py", ".js", ".html", ".css", ".json", ".sh", ".c", ".cpp", ".java",
        ".xml", ".yaml", ".yml", ".sql", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
        ".php", ".rs", ".go", ".rb", ".toml", ".ini", ".env", ".properties"
    },
}

# Tipos MIME explícitos para streaming de audio compatible con móviles (Safari/Chrome/Firefox)
AUDIO_MIME_TYPES: Dict[str, str] = {
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

IMAGE_MIME_TYPES: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
}

VIDEO_MIME_TYPES: Dict[str, str] = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}

# Carpetas virtuales o del sistema que se deben omitir para evitar cuelgues o accesos no deseados
SYSTEM_SKIP_DIRS: Set[str] = {
    "proc", "sys", "dev", "run", "snap", "lost+found",
    "cgroup", "cgroup2", "pstore", "bpf", "debugfs",
    "tracefs", "fusectl", "configfs", "securityfs",
    "efivarfs", "mqueue", "hugetlbfs", "ramfs",
}

# Archivos y carpetas críticas protegidas contra visualización, descarga, borrado o sobreescritura
PROTECTED_PATTERNS: Set[str] = {
    "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa", "authorized_keys", "known_hosts",
    ".bash_history", ".zsh_history", ".node_repl_history", ".python_history",
    "shadow", "gshadow", "sudoers", "master.passwd",
    ".secret_key", ".password_hash", ".auth_credentials.json",
    "sam", "system", "security", "ntuser.dat"
}

# Extensiones prohibidas para subida directa en carpetas críticas
DANGEROUS_UPLOAD_EXTS: Set[str] = {
    ".exe", ".msi", ".bat", ".cmd", ".sh", ".bash", ".ps1", ".vbs",
    ".scr", ".pif", ".application", ".gadget", ".jar"
}


def parse_cli_args():
    """Analiza argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="NavByte - Servidor Multimedia y Gestor Seguro de Archivos")
    parser.add_argument("-f", "--folder", default="/", help="Carpeta raíz a compartir (por defecto: / = todo el PC)")
    parser.add_argument("-p", "--port", type=int, default=5000, help="Puerto de escucha (por defecto: 5000)")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="Host de escucha (por defecto: 0.0.0.0)")
    parser.add_argument("--readonly", action="store_true", help="Modo sólo lectura (deshabilita subida y borrado)")
    parser.add_argument("--set-password", dest="set_password", default=None,
                        help="Establecer la contraseña de acceso (ej: ./start.sh --set-password MiClave123)")
    parser.add_argument("--set-user", dest="set_user", default=None,
                        help="Establecer el usuario de acceso (ej: ./start.sh --set-user admin)")
    parser.add_argument("--trusted-proxies", dest="trusted_proxies", action="store_true", default=False,
                        help="Habilitar confianza en cabeceras X-Forwarded-For si está tras un proxy inverso (Nginx/Cloudflare)")
    parser.add_argument("--threads", type=int, default=8, help="Número de hilos de trabajo para Waitress (por defecto: 8)")
    return parser.parse_known_args()

