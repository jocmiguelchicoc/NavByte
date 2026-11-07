# -*- coding: utf-8 -*-
"""
NavByte - Rutas Multimedia y Streaming
Transmisión eficiente de audio y video con soporte para peticiones HTTP 206 Range (seek / rebobinado).
"""

import os
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, current_app

from ..config import AUDIO_MIME_TYPES, VIDEO_MIME_TYPES
from ..security import require_auth
from ..services.filesystem import safe_resolve_path

media_bp = Blueprint("media", __name__)


@media_bp.route("/api/stream", methods=["GET"])
@require_auth
def stream():
    """
    Transmite archivos multimedia (audio/video) con soporte para Range requests
    (HTTP 206 Partial Content), permitiendo adelantar/retroceder en el reproductor.
    """
    shared_dir = current_app.config["SHARED_DIR"]
    rel_path = request.args.get("path", "").strip()
    abs_path, is_valid = safe_resolve_path(rel_path, shared_dir)

    if not is_valid or not os.path.isfile(abs_path):
        return jsonify({"error": "Archivo multimedia no encontrado o restringido"}), 404

    ext = Path(abs_path).suffix.lower()
    mime = AUDIO_MIME_TYPES.get(ext) or VIDEO_MIME_TYPES.get(ext)

    if mime:
        return send_file(abs_path, mimetype=mime, conditional=True)
    return send_file(abs_path, conditional=True)
