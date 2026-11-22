# -*- coding: utf-8 -*-
"""
NavByte - Fábrica de Aplicación (Application Factory)
Configura y ensambla el servidor Flask con cabeceras de seguridad y blueprints modulares.
"""

import os
from flask import Flask, jsonify, request, Response

from .config import BASE_DIR
from .security import (
    get_or_create_secret_key,
    validate_csrf_protection,
)
from .routes import auth_bp, file_bp, media_bp, system_bp


def create_app(
    shared_dir: str = "/",
    readonly: bool = False,
    trusted_proxies: bool = False,
    port: int = 5000
) -> Flask:
    """Crea y configura la instancia de la aplicación Flask."""
    template_dir = os.path.join(BASE_DIR, "templates")
    static_dir = os.path.join(BASE_DIR, "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )

    # 1. Configuración de Sesiones y Claves Criptográficas
    app.secret_key = get_or_create_secret_key()
    app.config["PERMANENT_SESSION_LIFETIME"] = 7 * 24 * 3600  # 7 días
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_NAME"] = "navbyte_session"

    # 2. Configuración Operativa
    app.config["SHARED_DIR"] = os.path.realpath(shared_dir)
    app.config["READONLY"] = readonly
    app.config["TRUSTED_PROXIES"] = trusted_proxies
    app.config["PORT"] = port
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10 GB
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Crear carpeta compartida si no existe y no es la raíz
    if app.config["SHARED_DIR"] not in ("/", "\\"):
        os.makedirs(app.config["SHARED_DIR"], exist_ok=True)

    # 3. Middlewares de Seguridad (Pre y Post Request)
    @app.before_request
    def check_csrf():
        csrf_error = validate_csrf_protection()
        if csrf_error:
            return csrf_error

    @app.after_request
    def apply_security_headers(response: Response) -> Response:
        """Aplica cabeceras de protección HTTP a todas las respuestas."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # Evitar almacenamiento en caché no deseado para respuestas dinámicas y APIs
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    # 4. Manejadores de Error Globales
    @app.errorhandler(400)
    def bad_request_handler(e):
        if request.path.startswith("/api/"):
            msg = getattr(e, "description", "Petición no válida")
            return jsonify({"error": str(msg)}), 400
        return "Petición incorrecta", 400

    @app.errorhandler(404)
    def not_found_handler(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Recurso no encontrado"}), 404
        return "Página no encontrada", 404

    @app.errorhandler(403)
    def forbidden_handler(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Acceso denegado o protegido por seguridad"}), 403
        return "Acceso denegado", 403

    @app.errorhandler(413)
    def request_entity_too_large(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "El archivo excede el tamaño máximo permitido (10 GB)"}), 413
        return "Archivo demasiado grande", 413

    @app.errorhandler(500)
    def internal_error_handler(e):
        app.logger.error(f"Error interno: {e}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno del servidor"}), 500
        return "Error interno del servidor", 500

    @app.errorhandler(Exception)
    def unhandled_exception_handler(e):
        app.logger.error(f"Error no controlado en la aplicación: {e}", exc_info=True)
        if request.path.startswith("/api/"):
            return jsonify({"error": f"Error del servidor: {str(e)}"}), 500
        return "Error interno del servidor", 500

    # 5. Registrar Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(system_bp)

    return app

