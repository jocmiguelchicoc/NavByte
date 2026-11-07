# -*- coding: utf-8 -*-
"""
NavByte - Módulo de Seguridad y Autenticación
Gestiona el control de acceso, hashes de contraseñas, rate limiting anti fuerza bruta,
prevención de CSRF y verificación de rutas restringidas.
"""

import os
import sys
import json
import time
import hmac
import secrets
import logging
from typing import Tuple, Dict, Any, Optional
from functools import wraps

from flask import request, jsonify, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

from .config import BASE_DIR, PROTECTED_PATTERNS

logger = logging.getLogger("navbyte.security")

SECRET_KEY_FILE = os.path.join(BASE_DIR, ".secret_key")
PASSWORD_HASH_FILE = os.path.join(BASE_DIR, ".password_hash")
AUTH_CONFIG_FILE = os.path.join(BASE_DIR, ".auth_credentials.json")

# Configuración de Rate Limiting
MAX_LOGIN_ATTEMPTS = 5
BLOCK_SECONDS = 300  # 5 minutos de bloqueo

# Estado de intentos de login en memoria: { ip: {"count": int, "blocked_until": float, "last_attempt": float} }
_login_attempts: Dict[str, Dict[str, Any]] = {}


def get_client_ip(trusted_proxies: bool = False) -> str:
    """
    Obtiene la IP real del cliente.
    Por seguridad, solo confía en cabeceras X-Forwarded-For si trusted_proxies está activado.
    Esto previene el bypass de rate limiting mediante falsificación de cabeceras.
    """
    if trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Tomar la primera IP de la lista proporcionada por el proxy
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def get_or_create_secret_key() -> bytes:
    """Carga o genera una clave secreta criptográfica persistente con permisos 0600."""
    if os.path.exists(SECRET_KEY_FILE):
        try:
            with open(SECRET_KEY_FILE, "rb") as f:
                key = f.read()
                if len(key) >= 32:
                    return key
        except Exception as e:
            logger.warning(f"No se pudo leer la clave secreta existente: {e}")

    # Generar nueva clave de 64 bytes
    key = secrets.token_bytes(64)
    try:
        with open(SECRET_KEY_FILE, "wb") as f:
            f.write(key)
        os.chmod(SECRET_KEY_FILE, 0o600)
    except Exception as e:
        logger.warning(f"No se pudo restringir permisos a {SECRET_KEY_FILE}: {e}")
    return key


def load_auth_config() -> Tuple[str, Optional[str]]:
    """Carga el usuario y hash de contraseña almacenados."""
    username = "admin"
    password_hash = None

    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                username = data.get("username", "admin")
                password_hash = data.get("password_hash")
        except Exception as e:
            logger.error(f"Error cargando {AUTH_CONFIG_FILE}: {e}")

    elif os.path.exists(PASSWORD_HASH_FILE):
        try:
            with open(PASSWORD_HASH_FILE, "r", encoding="utf-8") as f:
                password_hash = f.read().strip()
        except Exception as e:
            logger.error(f"Error cargando {PASSWORD_HASH_FILE}: {e}")

    return username, password_hash


def save_auth_config(username: str, password_raw: Optional[str] = None, password_hash: Optional[str] = None) -> Dict[str, str]:
    """Guarda credenciales con permisos restringidos 0o600."""
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

    try:
        with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(AUTH_CONFIG_FILE, 0o600)
    except Exception as e:
        logger.error(f"Error escribiendo {AUTH_CONFIG_FILE}: {e}")

    if "password_hash" in data:
        try:
            with open(PASSWORD_HASH_FILE, "w", encoding="utf-8") as f:
                f.write(data["password_hash"])
            os.chmod(PASSWORD_HASH_FILE, 0o600)
        except Exception as e:
            logger.error(f"Error escribiendo {PASSWORD_HASH_FILE}: {e}")

    return data


def ensure_mandatory_credentials() -> Tuple[str, str]:
    """
    Garantiza que SIEMPRE exista autenticación obligatoria.
    Si no existen credenciales:
    - Si la terminal es interactiva (TTY), solicita al usuario definirlas.
    - Si no es interactiva (ej: systemd), genera una contraseña aleatoria de 16 caracteres,
      la guarda de forma segura y la muestra en la consola.
    """
    username, password_hash = load_auth_config()
    if password_hash:
        return username, password_hash

    # No hay contraseña configurada: generar o pedir obligatoriamente
    print("\n" + "=" * 64)
    print(" 🔐 CONFIGURACIÓN DE SEGURIDAD INICIAL OBLIGATORIA")
    print("=" * 64)

    if sys.stdin.isatty():
        import getpass
        try:
            chosen_user = input("👤 Elige tu nombre de usuario [admin]: ").strip() or "admin"
            while True:
                chosen_pass = getpass.getpass("🔑 Elige una contraseña segura de acceso: ").strip()
                if len(chosen_pass) >= 4:
                    break
                print("⚠️ La contraseña debe tener al menos 4 caracteres. Inténtalo de nuevo.")
            save_auth_config(chosen_user, password_raw=chosen_pass)
            print("✅ Credenciales configuradas correctamente.")
            print("=" * 64 + "\n")
            return load_auth_config()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada por el usuario.")
            sys.exit(1)

    # Modo no interactivo (ej. servicio systemd o background)
    auto_pass = secrets.token_urlsafe(14)
    username = "admin"
    save_auth_config(username, password_raw=auto_pass)
    print(" 🛡️ Se ha autogenerado una contraseña segura para este servidor:")
    print(f"    Usuario:    {username}")
    print(f"    Contraseña: {auto_pass}")
    print(f"    Guardada en: {AUTH_CONFIG_FILE} (permisos 0600)")
    print(" Para cambiarla más adelante ejecuta:")
    print("    ./start.sh --set-user admin --set-password TuNuevaClave")
    print("=" * 64 + "\n")

    return load_auth_config()


def check_rate_limit(ip: str) -> Tuple[bool, int]:
    """
    Verifica si una IP está bloqueada por intentos fallidos.
    Retorna (esta_bloqueada, segundos_restantes).
    """
    now = time.time()
    # Limpiar IPs antiguas si la tabla crece mucho
    if len(_login_attempts) > 1000:
        expired = [k for k, v in _login_attempts.items() if now > v.get("blocked_until", 0) and now - v.get("last_attempt", 0) > 3600]
        for k in expired:
            _login_attempts.pop(k, None)

    attempt_data = _login_attempts.get(ip, {"count": 0, "blocked_until": 0, "last_attempt": now})
    if attempt_data["blocked_until"] > now:
        remaining = int(attempt_data["blocked_until"] - now)
        return True, remaining
    return False, 0


def record_failed_login(ip: str) -> Tuple[bool, int]:
    """
    Registra un intento fallido para la IP dada.
    Retorna (esta_bloqueada, intentos_o_segundos_restantes).
    """
    now = time.time()
    attempt_data = _login_attempts.get(ip, {"count": 0, "blocked_until": 0, "last_attempt": now})
    attempt_data["count"] = attempt_data.get("count", 0) + 1
    attempt_data["last_attempt"] = now

    if attempt_data["count"] >= MAX_LOGIN_ATTEMPTS:
        attempt_data["blocked_until"] = now + BLOCK_SECONDS
        attempt_data["count"] = 0
        _login_attempts[ip] = attempt_data
        return True, BLOCK_SECONDS

    _login_attempts[ip] = attempt_data
    remaining_attempts = MAX_LOGIN_ATTEMPTS - attempt_data["count"]
    return False, remaining_attempts


def clear_failed_login(ip: str):
    """Limpia los intentos fallidos tras un login exitoso."""
    _login_attempts.pop(ip, None)


def require_auth(f):
    """Decorador que protege endpoints: retorna 401 si no hay sesión activa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "No autorizado. Inicia sesión primero.", "auth_required": True}), 401
        return f(*args, **kwargs)
    return decorated


def is_protected_system_path(abs_path: str) -> bool:
    """
    Determina si una ruta absoluta apunta a un archivo crítico o confidencial del sistema
    que nunca debe ser leído, descargado, sobreescrito o eliminado.
    """
    norm_path = os.path.normpath(abs_path).replace("\\", "/").lower()
    base_name = os.path.basename(norm_path).lower()

    # Comprobar nombres de archivo confidenciales exactos
    if base_name in PROTECTED_PATTERNS:
        return True

    # Comprobar patrones de claves y credenciales
    for pattern in PROTECTED_PATTERNS:
        if pattern in base_name:
            return True

    # Rutas sensibles del sistema operativo
    CRITICAL_SYSTEM_PREFIXES = (
        "/etc/shadow", "/etc/gshadow", "/etc/sudoers", "/etc/security",
        "/root", "/var/lib/docker", "/var/run/docker.sock"
    )
    for prefix in CRITICAL_SYSTEM_PREFIXES:
        if norm_path.startswith(prefix.lower()):
            return True

    # Carpetas .ssh y .gnupg en cualquier directorio home
    if "/.ssh/" in norm_path or norm_path.endswith("/.ssh") or "/.gnupg/" in norm_path:
        return True

    return False


def validate_csrf_protection() -> Optional[Response]:
    """
    Verifica que las peticiones POST de modificación de estado provengan del mismo origen.
    Protección contra ataques CSRF desde sitios web maliciosos.
    """
    if request.method in ("POST", "PUT", "DELETE"):
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin:
            host = request.host
            # Comprobar que el Host coincida con el Origin/Referer
            if f"://{host}" not in origin and not origin.startswith(f"http://{host}") and not origin.startswith(f"https://{host}"):
                return jsonify({"error": "Petición bloqueada por validación de origen (CSRF)"}), 403
    return None

