@echo off
REM ==============================================================================
REM NavByte - Lanzador para Windows (Doble Clic)
REM ==============================================================================
title NavByte - Servidor Multimedia y Gestor de Archivos
cd /d "%~dp0"

echo ==========================================================
echo  🚀 NavByte - Servidor Multimedia y Gestor de Archivos
echo ==========================================================

REM 1. Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH de Windows.
    echo Descargalo e instalalo desde https://www.python.org/
    echo IMPORTANTE: Marca la casilla "Add Python to PATH" al instalar.
    pause
    exit /b 1
)

REM 2. Verificar o crear entorno virtual
if not exist "venv" (
    echo [INFO] Creando entorno virtual Python (venv)...
    python -m venv venv
    venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    echo [INFO] Instalando dependencias necesarias (Flask, Pillow, qrcode)...
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
) else (
    venv\Scripts\python.exe -c "import flask, qrcode, PIL" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [INFO] Instalando dependencias faltantes...
        venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    )
)

REM 3. Asistente interactivo de primer uso (crear credenciales)
if not exist ".auth_credentials.json" (
    if not exist ".password_hash" (
        echo.
        echo ==========================================================
        echo  🔐 ASISTENTE DE CONFIGURACION INICIAL (PRIMER USO)
        echo ==========================================================
        echo  Para proteger tus archivos contra accesos no autorizados en tu red,
        echo  necesitas crear un usuario y contrasena de acceso:
        echo.
        set /p CHOSEN_USER="👤 Elige tu nombre de usuario [admin]: "
        if "%CHOSEN_USER%"=="" set CHOSEN_USER=admin

        set /p CHOSEN_PASS="🔑 Elige tu contrasena de acceso: "
        if "%CHOSEN_PASS%"=="" set CHOSEN_PASS=navbyte123

        echo [INFO] Guardando credenciales seguras...
        venv\Scripts\python.exe app.py --set-user "%CHOSEN_USER%" --set-password "%CHOSEN_PASS%"
        echo [OK] Configuracion completada con exito.
        echo ==========================================================
        echo.
    )
)

REM 4. Iniciar el servidor NavByte
echo [INFO] Iniciando servidor NavByte...
venv\Scripts\python.exe app.py %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] El servidor se detuvo con errores.
    pause
)
