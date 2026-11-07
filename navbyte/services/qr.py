# -*- coding: utf-8 -*-
"""
NavByte - Servicio de Red y Códigos QR
Detección de IP local en WiFi/Ethernet y generación de códigos QR para emparejamiento móvil.
"""

import io
import socket
from typing import Tuple


def get_local_ip() -> str:
    """Detecta la IP local de la computadora en la red WiFi o Ethernet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Conexión UDP simulada (no envía paquetes reales) para averiguar la interfaz de salida
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_qr_buffer(url: str) -> Tuple[io.BytesIO, str]:
    """
    Genera una imagen QR en memoria (PNG con Pillow o SVG como fallback).
    Retorna (buffer_en_memoria, mimetype).
    """
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    try:
        # Intento con Pillow para PNG de alta definición
        img = qr.make_image(fill_color="#10b981", back_color="#0f172a")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf, "image/png"
    except Exception:
        # Fallback a SVG vectorial sin Pillow
        import qrcode.image.svg
        svg_qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
            image_factory=qrcode.image.svg.SvgImage,
        )
        svg_qr.add_data(url)
        svg_qr.make(fit=True)
        img = svg_qr.make_image()
        buf = io.BytesIO()
        img.save(buf)
        buf.seek(0)
        return buf, "image/svg+xml"


def print_ascii_qr(url: str):
    """Imprime el código QR directamente en la consola para escanearlo con el celular."""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass

