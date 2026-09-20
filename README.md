# 🚀 NavByte - Tu Servidor Multimedia y Nube Personal Móvil 📱💻

¡Bienvenido a **NavByte**! Con esta herramienta puedes conectar tu celular a tu computadora a través de tu red Wi-Fi para:
- 🎵 **Escuchar tu música** (WAV, MP3, FLAC, pistas, samples) en streaming continuo con calidad total y sin gastar tus datos móviles.
- 📁 **Explorar todos tus archivos y discos duros** (tanto internos como memorias USB y discos externos) desde la comodidad de tu cama o estudio.
- ⚡ **Descargar y transferir archivos** de la PC al celular a máxima velocidad y sin cables.

> 💡 **No necesitas saber nada de programación ni informática.** Solo sigue los 5 sencillos pasos a continuación para tenerlo funcionando en 3 minutos.

---

## ⚡ Guía Paso a Paso para Principiantes

### 📦 Paso 1: Descomprimir la carpeta
1. Descarga o copia la carpeta del proyecto a tu computadora (por ejemplo, en tu carpeta de *Documentos* o *Música*).
2. Si lo descargaste como archivo `.zip`, dale clic derecho y elige **"Extraer todo..."** o **"Extraer aquí"**.

---

### 🐍 Paso 2: Instalar Python (Solo se hace una vez)
Python es el motor gratuito que hace funcionar el servidor en tu computadora.

#### 🪟 Si estás en Windows:
1. Entra a la página oficial: **[python.org/downloads](https://www.python.org/downloads/)** y pulsa el botón amarillo grande que dice **Download Python**.
2. Abre el archivo descargado para comenzar la instalación.
3. ⚠️ **MUY IMPORTANTE (NO TE SALTES ESTE DETALLE):**
   - En la primera ventana que se abre, **marca la casilla** que está abajo del todo que dice:
     **☑️ Add Python to PATH** (o *"Agregar Python al PATH"*).
   - Luego haz clic en **Install Now**.
   - Al finalizar, pulsa **Close**. ¡Listo!

#### 🐧 Si estás en Linux (Ubuntu / Mint / Debian):
Abre una terminal y escribe este único comando:
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

---

### 🚀 Paso 3: Encender NavByte con 1 Clic

#### 🪟 En Windows:
1. Abre la carpeta donde tienes los archivos de NavByte.
2. Simplemente haz **doble clic** sobre el archivo llamado:
   ```text
   start_windows.bat
   ```
*(Se abrirá una ventana de fondo negro. ¡No te asustes, es normal! El programa está preparando todo automáticamente).*

#### 🐧 En Linux / macOS:
1. Abre la terminal dentro de la carpeta.
2. Escribe:
   ```bash
   ./start.sh
   ```
*(Si no te deja ejecutarlo, dale permisos con `chmod +x start.sh` y vuelve a ejecutar `./start.sh`)*.

---

### 🔐 Paso 4: Crear tu Usuario y Contraseña (Solo la primera vez)

Como es la primera vez que lo abres, el sistema te pedirá en la ventana negra que elijas tu nombre de usuario y tu contraseña para que nadie más en tu casa pueda entrar a tus archivos:

1. **👤 Elige tu nombre de usuario:**
   - Escribe tu nombre o apodo (ejemplo: `carlos`) y presiona la tecla **Enter**. (Si dejas vacío y pulsas Enter, se usará `admin`).
2. **🔑 Elige tu contraseña:**
   - Escribe una contraseña que recuerdes (ejemplo: `musica2026`) y presiona la tecla **Enter**.
   - ℹ️ *Por tu seguridad, mientras escribes la contraseña es normal que la pantalla no muestre letras ni asteriscos. Tú solo escríbela con calma y pulsa Enter.*

¡Y listo! El sistema guardará tus datos de forma segura y nunca más te volverá a pedir crearlos.

---

### 📱 Paso 5: Conectar tu Celular en 5 Segundos

Una vez creado tu usuario, en la pantalla de tu computadora aparecerá un **código QR grande** y una dirección como esta:
```text
👉 URL Local: http://192.168.1.15:5000
```

1. **Asegúrate de que tu celular esté conectado al mismo Wi-Fi de tu casa que la computadora.**
2. Abre la cámara de tu celular y apunta hacia el código QR en la pantalla de la computadora.
3. Toca el enlace amarillo o ventana emergente que aparece en la pantalla del celular.
   *(O si prefieres, abre Google Chrome o Safari en tu teléfono y escribe la dirección que te dio la PC, por ejemplo `http://192.168.1.15:5000`)*.
4. Escribe el usuario y la contraseña que creaste en el Paso 4 y toca en **"Iniciar Sesión"**.

---

### 📲 Cómo poner el icono de NavByte en tu Celular (Como una App)

Para no tener que escribir la dirección cada vez que quieras escuchar música:

- **En Android (Google Chrome):**
  1. Con la página de NavByte abierta, toca los **3 puntos** arriba a la derecha.
  2. Selecciona la opción **"Agregar a la pantalla principal"** o **"Instalar aplicación"**.
  3. ¡Listo! Te quedará un icono con el logo de NavByte junto a tus demás aplicaciones.

- **En iPhone / iPad (Safari):**
  1. Con la página abierta, toca el botón de **Compartir** (el cuadrito con la flecha hacia arriba en la barra inferior).
  2. Desliza hacia abajo y toca **"Agregar a inicio"**.

---

## 💡 Consejos de Uso Diario

- **¿Cómo apago el servidor cuando termine?**
  - Simplemente cierra la ventana negra en tu computadora o presiona las teclas `Ctrl + C`.
- **¿Cómo lo vuelvo a encender mañana?**
  - Solo vuelve a hacer doble clic en `start_windows.bat` (o `./start.sh` en Linux). ¡Ya no te pedirá crear usuario, arrancará directamente!
- **Discos externos y memorias USB:**
  - Si conectas una memoria USB o un disco duro externo a tu PC, NavByte lo detectará automáticamente y te mostrará una tarjeta para entrar a él directamente.
- **Menú en el celular:**
  - Si mantienes presionado tu dedo sobre cualquier canción o archivo (o haces clic derecho en la PC), se abrirá un menú con opciones para **Reproducir**, **Descargar** o ver **Detalles**.
- **Reproducción en segundo plano:**
  - Puedes bloquear la pantalla de tu celular o cambiar de aplicación y tu música seguirá sonando sin interrupciones.

---

## 🌍 ¿Quieres usarlo fuera de tu casa con datos móviles? (Opcional)

Si vas por la calle, estás en el transporte o en otro lugar y quieres escuchar la música de tu PC desde tu celular con datos móviles:

1. Entra en tu computadora a **[tailscale.com](https://tailscale.com)** y crea una cuenta gratis con tu correo de Google o Apple.
2. Descarga e instala Tailscale en tu PC.
3. Descarga la App **Tailscale** en tu celular (desde Google Play Store o App Store) e inicia sesión con el mismo correo.
4. ¡Listo! Tu computadora tendrá una dirección fija (por ejemplo `http://100.86.20.10:5000`) y podrás entrar desde cualquier lugar del mundo a la velocidad de tu conexión.

---

## ❓ Preguntas Frecuentes y Solución de Problemas

### 1. "En el celular me sale 'No se puede acceder a este sitio'"
- **Causa más común:** Tu celular está conectado a los datos móviles en vez de la red Wi-Fi de tu casa. Enciende el Wi-Fi en el celular.
- **Cortafuegos de Windows (Firewall):** La primera vez que abres NavByte en Windows, puede aparecer una pequeña ventana azul que dice *"El Firewall de Windows bloqueó algunas características"*. Asegúrate de marcar ambas casillas y hacer clic en **"Permitir acceso"**.

### 2. "Olvidé mi contraseña o quiero cambiarla"
- Puedes cambiar tu usuario y contraseña en cualquier momento abriendo una terminal o consola en la carpeta y ejecutando:
  ```bash
  # En Linux:
  ./start.sh --set-user MiNombre --set-password MiNuevaClave

  # En Windows:
  venv\Scripts\python.exe app.py --set-user MiNombre --set-password MiNuevaClave
  ```

---

¡Disfruta de tu música y tus archivos dondequiera que estés, con total privacidad y sin cables! 🎧🔥
