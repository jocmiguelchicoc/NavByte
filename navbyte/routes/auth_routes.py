# -*- coding: utf-8 -*-
"""
NavByte - Rutas de Autenticación
Endpoints para inicio/cierre de sesión y verificación de estado con protección anti fuerza bruta.
"""

from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.security import check_password_hash

from ..security import (
    get_client_ip,
    check_rate_limit,
    record_failed_login,
    clear_failed_login,
    load_auth_config,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth_status", methods=["GET"])
def auth_status():
    """Verifica si la sesión actual está autenticada."""
    return jsonify({
        "authenticated": session.get("authenticated", False),
        "auth_required": True,
        "username": session.get("username", None),
    })


@auth_bp.route("/api/login", methods=["POST"])
def login():
    """
    Autenticación con usuario y contraseña.
    Implementa rate limiting estricto anti fuerza bruta basado en IP real.
    """
    trusted_proxies = current_app.config.get("TRUSTED_PROXIES", False)
    client_ip = get_client_ip(trusted_proxies=trusted_proxies)

    # 1. Comprobar bloqueo de IP
    is_blocked, remaining = check_rate_limit(client_ip)
    if is_blocked:
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

    stored_user, stored_hash = load_auth_config()

    user_ok = (stored_user and username.lower() == stored_user.lower())
    password_ok = bool(stored_hash and check_password_hash(stored_hash, password))

    if user_ok and password_ok:
        # ✅ Login exitoso: limpiar intentos fallidos y crear sesión
        clear_failed_login(client_ip)
        session["authenticated"] = True
        session["username"] = stored_user
        session.permanent = True
        return jsonify({
            "success": True,
            "message": "Acceso concedido",
            "username": stored_user
        })

    # ❌ Credenciales incorrectas: registrar intento fallido
    is_now_blocked, attempts_or_secs = record_failed_login(client_ip)
    if is_now_blocked:
        return jsonify({
            "success": False,
            "error": f"Cuenta bloqueada temporalmente por {attempts_or_secs // 60} minutos tras demasiados intentos fallidos.",
            "blocked": True,
            "retry_after": attempts_or_secs,
        }), 429

    return jsonify({
        "success": False,
        "error": f"Usuario o contraseña incorrectos. Intentos restantes: {attempts_or_secs}.",
    }), 401


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    """Cierra la sesión actual y destruye las cookies."""
    session.clear()
    return jsonify({"success": True, "message": "Sesión cerrada correctamente"})

