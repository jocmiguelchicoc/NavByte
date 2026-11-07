# -*- coding: utf-8 -*-
"""
NavByte - Rutas de Información del Sistema y Dispositivos
Endpoints para obtener métricas de disco, lista de unidades y emparejamiento QR.
"""

import socket
import shutil
from flask import Blueprint, request, jsonify, send_file, current_app

from ..security import require_auth
from ..services.filesystem import format_size, detect_system_drives
from ..services.qr import get_local_ip, generate_qr_buffer

system_bp = Blueprint("system", __name__)


@system_bp.route("/api/info", methods=["GET"])
@require_auth
def get_info():
    """Información del sistema y estado del servidor."""
    shared_dir = current_app.config["SHARED_DIR"]
    try:
        total, used, free = shutil.disk_usage(shared_dir)
        disk_info = {
            "total": format_size(total),
            "used": format_size(used),
            "free": format_size(free),
            "percent": round((used / total) * 100, 1) if total else 0,
        }
    except Exception:
        disk_info = {"total": "N/A", "used": "N/A", "free": "N/A", "percent": 0}

    local_ip = get_local_ip()
    port = request.environ.get("SERVER_PORT", current_app.config.get("PORT", 5000))

    return jsonify({
        "hostname": socket.gethostname(),
        "ip": local_ip,
        "port": port,
        "access_url": f"http://{local_ip}:{port}",
        "shared_dir": shared_dir,
        "readonly": current_app.config.get("READONLY", False),
        "disk": disk_info,
    })


@system_bp.route("/api/drives", methods=["GET"])
@require_auth
def get_drives():
    """Detecta y retorna las particiones y discos duros reales del sistema."""
    shared_dir = current_app.config["SHARED_DIR"]
    drives = detect_system_drives(shared_dir)
    return jsonify({"drives": drives, "total": len(drives)})


@system_bp.route("/api/qr", methods=["GET"])
@require_auth
def get_qr():
    """Genera y retorna la imagen QR en memoria (PNG/SVG) para emparejar el celular."""
    local_ip = get_local_ip()
    port = request.environ.get("SERVER_PORT", current_app.config.get("PORT", 5000))
    url = f"http://{local_ip}:{port}"

    try:
        buf, mimetype = generate_qr_buffer(url)
        return send_file(buf, mimetype=mimetype)
    except Exception as e:
        return jsonify({"error": f"No se pudo generar el código QR: {str(e)}"}), 500

