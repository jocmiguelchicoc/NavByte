#!/usr/bin/env bash
# ==============================================================================
# NavByte - Instalador de Inicio Automático (Linux systemd)
# ==============================================================================

set -e

# 1. Comprobar privilegios de superusuario (sudo)
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Este instalador requiere permisos de administrador."
  echo "👉 Por favor ejecútalo con: sudo bash $0"
  exit 1
fi

CURRENT_USER="${SUDO_USER:-$USER}"
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
SERVICE_FILE="/etc/systemd/system/navbyte.service"

echo "=============================================================="
echo " 🚀 CONFIGURADOR DE INICIO AUTOMÁTICO - NAVBYTE"
echo "=============================================================="
echo " Usuario del servicio: $CURRENT_USER"
echo " Directorio base:      $PROJECT_DIR"
echo " Archivo de servicio:  $SERVICE_FILE"
echo "=============================================================="

# 2. Verificar que exista el entorno virtual venv
if [ ! -f "$PROJECT_DIR/venv/bin/python" ]; then
  echo "📦 Creando entorno virtual e instalando dependencias..."
  sudo -u "$CURRENT_USER" python3 -m venv "$PROJECT_DIR/venv"
  sudo -u "$CURRENT_USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade pip --quiet
  sudo -u "$CURRENT_USER" "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet
fi

# 3. Crear archivo de servicio systemd
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=NavByte Remote Audio & File Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory="$PROJECT_DIR"
ExecStart="$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/app.py" -p 5000
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

# 4. Habilitar e iniciar servicio
systemctl daemon-reload
systemctl enable navbyte.service
systemctl restart navbyte.service

echo ""
echo "=============================================================="
echo "✅ ¡Servicio NavByte instalado y activo con éxito!"
echo "=============================================================="
echo "📌 Comandos útiles para administrar el servicio:"
echo "   - Ver estado:     sudo systemctl status navbyte.service"
echo "   - Detener:        sudo systemctl stop navbyte.service"
echo "   - Reiniciar:      sudo systemctl restart navbyte.service"
echo "   - Ver registros:  sudo journalctl -u navbyte -f"
echo "=============================================================="
