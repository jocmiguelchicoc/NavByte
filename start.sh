#!/usr/bin/env bash
# ==============================================================================
# NavByte - Lanzador Inteligente Multiplataforma (Linux / macOS)
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo " 🚀 NavByte - Servidor Multimedia y Gestor de Archivos"
echo "=========================================================="

# 1. Verificar si Python 3 está disponible
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 no está instalado en este sistema."
    echo "👉 Instálalo con: sudo apt install python3 python3-venv (Ubuntu/Debian)"
    exit 1
fi

# 2. Verificar o crear entorno virtual
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual Python (venv)..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip --quiet
    echo "📥 Instalando dependencias necesarias (Flask, Pillow, qrcode)..."
    ./venv/bin/pip install -r requirements.txt --quiet
else
    # Verificar si falta alguna dependencia
    if ! ./venv/bin/python -c "import flask, qrcode, PIL" 2>/dev/null; then
        echo "📦 Verificando dependencias..."
        ./venv/bin/pip install -r requirements.txt --quiet
    fi
fi

# 3. Asistente interactivo de primer uso: configurar usuario y contraseña
if [ ! -f ".auth_credentials.json" ] && [ ! -f ".password_hash" ]; then
    echo ""
    echo "=========================================================="
    echo " 🔐 ASISTENTE DE CONFIGURACIÓN INICIAL (PRIMER USO)"
    echo "=========================================================="
    echo " Para proteger tus archivos contra accesos no autorizados en tu red,"
    echo " necesitas crear un usuario y contraseña de acceso:"
    echo ""
    
    read -r -p "👤 Elige tu nombre de usuario [admin]: " CHOSEN_USER
    CHOSEN_USER=${CHOSEN_USER:-admin}

    while true; do
        read -r -s -p "🔑 Elige tu contraseña de acceso: " CHOSEN_PASS
        echo ""
        if [ -n "$CHOSEN_PASS" ]; then
            break
        else
            echo "⚠️ La contraseña no puede estar vacía. Inténtalo de nuevo."
        fi
    done

    echo "⚙️ Guardando credenciales seguras..."
    ./venv/bin/python app.py --set-user "$CHOSEN_USER" --set-password "$CHOSEN_PASS"
    echo "✅ ¡Configuración completada con éxito!"
    echo "=========================================================="
    echo ""
fi

# 4. Iniciar servidor Flask con los argumentos pasados
echo "🌐 Iniciando servidor NavByte..."
exec ./venv/bin/python app.py "$@"
