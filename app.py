#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NavByte - Servidor Multimedia y Gestor Seguro de Archivos para Móvil y PC
Punto de entrada principal (Entry Point).
"""

import sys
import os

from navbyte.config import parse_cli_args, BASE_DIR
from navbyte.security import (
    load_auth_config,
    save_auth_config,
    ensure_mandatory_credentials,
)
from navbyte.services.qr import get_local_ip, print_ascii_qr
from navbyte.services.filesystem import automount_unmounted_drives
from navbyte import create_app


def print_banner(host: str, port: int, shared_dir: str):
    """Imprime el banner de inicio con IP y código QR para emparejamiento móvil."""
    local_ip = get_local_ip()
    url = f"http://{local_ip}:{port}"

    print("\n" + "=" * 64)
    print(" 🚀 SERVIDOR NAVBYTE SEGURO INICIADO CON ÉXITO")
    print("=" * 64)
    print(f" 📂 Carpeta compartida: {shared_dir}")
    print(f" 🌐 En tu computadora:  http://localhost:{port}")
    print(f" 📱 En tu celular (WiFi): \033[1;32m{url}\033[0m")
    print("=" * 64)
    print(" Escanea este código QR con la cámara de tu celular:\n")

    print_ascii_qr(url)

    print("\n Presiona CTRL+C para detener el servidor.\n" + "=" * 64 + "\n")


def main():
    args, unknown = parse_cli_args()

    # 1. Resolver ruta compartida
    shared_dir = os.path.abspath(args.folder) if os.path.isabs(args.folder) else os.path.abspath(os.path.join(BASE_DIR, args.folder))

    # 2. Manejo de --set-password y --set-user (actualizar y salir)
    if args.set_password or args.set_user:
        curr_user, curr_hash = load_auth_config()
        new_user = args.set_user if args.set_user else curr_user
        save_auth_config(new_user, password_raw=args.set_password)
        print(f"\n✅ Credenciales de acceso actualizadas con éxito.")
        print(f"   Usuario: {new_user}")
        if args.set_password:
            print(f"   Contraseña: [Actualizada con hash pbkdf2:sha256]")
        print("\nAhora puedes iniciar el servidor normalmente con: ./start.sh\n")
        sys.exit(0)

    # 3. Blindaje: Garantizar credenciales obligatorias siempre
    ensure_mandatory_credentials()

    # 4. Automontaje: Detectar y montar automáticamente discos externos y USBs conectadas
    automount_unmounted_drives()

    # 5. Crear instancia de Flask
    app = create_app(
        shared_dir=shared_dir,
        readonly=args.readonly,
        trusted_proxies=args.trusted_proxies,
        port=args.port
    )

    # 5. Imprimir información de red y QR
    print_banner(args.host, args.port, app.config["SHARED_DIR"])

    # 6. Lanzar con Waitress (WSGI de producción) o fallback a Werkzeug
    try:
        from waitress import serve
        print("⚡ Motor de alto rendimiento: Waitress WSGI activo")
        serve(app, host=args.host, port=args.port, threads=args.threads)
    except ImportError:
        print("⚠️ Waitress no encontrado. Ejecutando con servidor estándar de Flask.")
        print("👉 Recomendado: pip install waitress para máxima velocidad y estabilidad.")
        app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
