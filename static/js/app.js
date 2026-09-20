/**
 * NavByte - Lógica Frontend Móvil-Primero
 * Conexión reactiva con API Flask para navegación, subida, descarga, reproducción y autenticación.
 */

// Estado global de la aplicación
const AppState = {
  currentPath: '',
  parentPath: null,
  items: [],
  filteredItems: [],
  drives: [],
  serverInfo: null,
  currentAudio: null,
  currentTrack: null,
  searchQuery: '',
  authenticated: false,
  username: '',
};

// ==========================================================================
// Inicialización y Autenticación
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  checkAuthAndInit();
});

/** Conmuta visibilidad de la contraseña en el formulario de login */
function togglePasswordVisibility() {
  const pw = document.getElementById('loginPasswordInput');
  const btn = document.getElementById('btnTogglePassword');
  if (!pw) return;
  if (pw.type === 'password') {
    pw.type = 'text';
    if (btn) btn.textContent = '🙈';
  } else {
    pw.type = 'password';
    if (btn) btn.textContent = '👁️';
  }
}

/** Verifica el estado de autenticación antes de mostrar la UI */
async function checkAuthAndInit() {
  try {
    const res = await fetch('/api/auth_status');
    const data = await res.json();
    AppState.authenticated = data.authenticated;
    if (data.username) AppState.username = data.username;

    if (!data.auth_required || data.authenticated) {
      // Ya autenticado o no se requiere auth: mostrar la app
      showMainApp();
    } else {
      // Requiere autenticación: mostrar pantalla de login
      showLoginScreen();
    }
  } catch (err) {
    showLoginScreen();
  }
}

/** Muestra la pantalla de login */
function showLoginScreen() {
  const loginScreen = document.getElementById('loginScreen');
  const mainApp = document.getElementById('mainApp');
  const audioBar = document.getElementById('audioDock');
  if (loginScreen) loginScreen.style.display = 'flex';
  if (mainApp) mainApp.style.display = 'none';
  if (audioBar) audioBar.style.display = 'none';

  // Enfocar usuario si está vacío, o contraseña si ya hay usuario
  setTimeout(() => {
    const userInput = document.getElementById('loginUserInput');
    const pwInput = document.getElementById('loginPasswordInput');
    if (userInput && !userInput.value) {
      userInput.focus();
    } else if (pwInput) {
      pwInput.focus();
    }
  }, 300);
}

/** Muestra la app principal tras login exitoso */
function showMainApp() {
  const loginScreen = document.getElementById('loginScreen');
  const mainApp = document.getElementById('mainApp');
  const audioBar = document.getElementById('audioDock');
  if (loginScreen) loginScreen.style.display = 'none';
  if (mainApp) mainApp.style.display = 'block';
  if (audioBar) audioBar.style.display = '';

  // Actualizar badge de usuario autenticado
  const userBadge = document.getElementById('userBadge');
  const userBadgeName = document.getElementById('userBadgeName');
  if (userBadge) {
    if (AppState.username) {
      if (userBadgeName) userBadgeName.textContent = AppState.username;
      userBadge.style.display = 'inline-flex';
    } else {
      userBadge.style.display = 'none';
    }
  }

  initAudioPlayer();
  setupEventListeners();
  loadServerInfo();

  // Restaurar ruta desde hash si existe (ej. al recargar en una subcarpeta)
  const initialPath = decodePathFromHash();
  loadDirectory(initialPath, false);
  const initialHash = initialPath ? '#/' + encodeURIComponent(initialPath) : '#/';
  if (window.history && window.history.replaceState) {
    window.history.replaceState({ path: initialPath }, '', initialHash);
  }
}

/** Envía las credenciales de login al servidor */
async function submitLogin() {
  const userInput = document.getElementById('loginUserInput');
  const pwInput = document.getElementById('loginPasswordInput');
  const errorEl = document.getElementById('loginError');
  const btn = document.getElementById('loginSubmitBtn');

  if (!userInput || !pwInput) return;
  const username = userInput.value.trim();
  const password = pwInput.value;

  if (!username) {
    if (errorEl) { errorEl.textContent = 'Por favor ingresa el nombre de usuario.'; errorEl.style.display = 'block'; }
    userInput.focus();
    return;
  }

  if (!password) {
    if (errorEl) { errorEl.textContent = 'Por favor ingresa la contraseña.'; errorEl.style.display = 'block'; }
    pwInput.focus();
    return;
  }

  // Mostrar estado de verificación
  if (btn) { btn.disabled = true; btn.textContent = 'Verificando...'; }
  if (errorEl) errorEl.style.display = 'none';

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json();

    if (data.success) {
      AppState.authenticated = true;
      AppState.username = data.username || username;
      pwInput.value = '';
      showMainApp();
    } else {
      if (errorEl) {
        errorEl.textContent = data.error || 'Usuario o contraseña incorrectos.';
        errorEl.style.display = 'block';
      }
      pwInput.value = '';
      pwInput.focus();

      // Efecto sacudida en la tarjeta de login
      const card = document.getElementById('loginCard');
      if (card) {
        card.style.animation = 'shake 0.4s ease';
        setTimeout(() => card.style.animation = '', 400);
      }
    }
  } catch (err) {
    if (errorEl) { errorEl.textContent = 'Error de conexión con el servidor.'; errorEl.style.display = 'block'; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🔓 Iniciar Sesión'; }
  }
}

/** Cierra la sesión actual */
async function logout() {
  if (!confirm('¿Cerrar sesión?')) return;
  try {
    await fetch('/api/logout', { method: 'POST' });
    AppState.authenticated = false;
    AppState.username = '';
    showLoginScreen();
  } catch (err) {
    showToast('Error al cerrar sesión', 'error');
  }
}


/** Carga información del sistema y almacenamiento */
async function loadServerInfo() {
  try {
    const res = await fetch('/api/info');
    if (!res.ok) return;
    AppState.serverInfo = await res.json();

    const ipBadge = document.getElementById('serverIpBadge');
    if (ipBadge) ipBadge.textContent = `${AppState.serverInfo.ip}:${AppState.serverInfo.port}`;

    const diskPill = document.getElementById('diskUsagePill');
    if (diskPill && AppState.serverInfo.disk) {
      diskPill.innerHTML = `💾 Libre: <strong>${AppState.serverInfo.disk.free}</strong>`;
    }

    const qrUrlText = document.getElementById('qrUrlText');
    if (qrUrlText) qrUrlText.textContent = AppState.serverInfo.access_url;

    // Si está en modo de sólo lectura, ocultar botones de subida y creación
    if (AppState.serverInfo.readonly) {
      const uploadBtn = document.getElementById('btnOpenUpload');
      const mkdirBtn = document.getElementById('btnOpenMkdir');
      if (uploadBtn) uploadBtn.style.display = 'none';
      if (mkdirBtn) mkdirBtn.style.display = 'none';
    }
  } catch (err) {
    console.error('Error cargando información del servidor:', err);
  }
}

/** Carga el contenido de un directorio */
async function loadDirectory(path, pushHistory = true) {
  showLoading(true);
  try {
    const url = `/api/browse?path=${encodeURIComponent(path)}`;
    const res = await fetch(url);
    if (res.status === 401) {
      showLoginScreen();
      return;
    }
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || 'Error al cargar directorio');
    }

    const data = await res.json();
    AppState.currentPath = data.current_path;
    AppState.parentPath = data.parent_path;
    AppState.items = data.items;

    // Actualizar botón de retroceso (Flecha Atrás)
    updateNavControls(data.parent_path);

    // Actualizar historial del navegador para soporte de botón Atrás nativo
    if (pushHistory && window.history && window.history.pushState) {
      const targetHash = path ? '#/' + encodeURIComponent(path) : '#/';
      if (window.location.hash !== targetHash) {
        window.history.pushState({ path: path }, '', targetHash);
      }
    }

    renderBreadcrumbs(data.breadcrumbs);

    // Si no estamos en la raíz, registrar la carpeta visitada en Recientes
    if (path && path !== '' && path !== '.') {
      const parts = path.split('/').filter(Boolean);
      const folderName = parts.length > 0 ? parts[parts.length - 1] : path;
      recordRecentFolder(path, folderName);
    }

    // Si estamos en la raíz del PC, mostrar también el panel de unidades y recientes
    if (data.is_root) {
      await loadAndRenderDrives();
      renderRecentsPanel();
    } else {
      hideDrivesPanel();
      hideRecentsPanel();
    }

    applyFilter();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    showLoading(false);
  }
}

/** Actualiza el estado visual de los botones de navegación */
function updateNavControls(parentPath) {
  const navBar = document.getElementById('navControlBar');
  const btnBack = document.getElementById('btnNavBack');

  // Si estamos en Inicio, ocultar toda la barra para no saturar la pantalla
  if (!AppState.currentPath || AppState.currentPath === '') {
    if (navBar) navBar.style.display = 'none';
    if (btnBack) btnBack.style.display = 'none';
    return;
  }

  if (navBar) navBar.style.display = 'flex';
  if (!btnBack) return;

  if (parentPath !== null && parentPath !== undefined) {
    btnBack.style.display = 'inline-flex';
    btnBack.disabled = false;
    btnBack.classList.add('btn-active-back');
    btnBack.title = 'Retroceder a la carpeta anterior (Subir un nivel)';
  } else {
    btnBack.style.display = 'none';
    btnBack.disabled = true;
    btnBack.classList.remove('btn-active-back');
    btnBack.title = 'Estás en el inicio';
  }
}

/** Retrocede a la carpeta padre o a la raíz */
function navigateBack() {
  if (AppState.parentPath !== null && AppState.parentPath !== undefined) {
    loadDirectory(AppState.parentPath);
  } else {
    loadDirectory('');
  }
}

/** Navega directo al inicio / unidades del PC */
function navigateHome() {
  loadDirectory('');
}

/** Obtiene la ruta limpia desde el hash de la URL */
function decodePathFromHash() {
  const hash = window.location.hash;
  if (!hash || hash === '#' || hash === '#/') return '';
  if (hash.startsWith('#/')) {
    try {
      return decodeURIComponent(hash.substring(2));
    } catch (e) {
      return hash.substring(2);
    }
  }
  return '';
}

// ==========================================================================
// Renderizado de UI
// ==========================================================================

/** Renderiza la barra de migas de pan (Breadcrumbs) */
function renderBreadcrumbs(crumbs) {
  const navBar = document.getElementById('navControlBar');
  const container = document.getElementById('breadcrumbContainer');
  if (!container) return;
  container.innerHTML = '';

  // En la raíz (Inicio), ocultar completamente la barra para que no aparezca el botón de inicio
  if (!AppState.currentPath || !crumbs || crumbs.length <= 1) {
    if (navBar) navBar.style.display = 'none';
    return;
  }

  if (navBar) navBar.style.display = 'flex';

  crumbs.forEach((crumb, idx) => {
    const isLast = idx === crumbs.length - 1;
    const btn = document.createElement('button');
    btn.className = `crumb-btn ${isLast ? 'active' : ''}`;
    btn.innerHTML = idx === 0 ? '🏠 Inicio' : escapeHtml(crumb.name);
    btn.onclick = () => loadDirectory(crumb.path);
    container.appendChild(btn);

    if (!isLast) {
      const sep = document.createElement('span');
      sep.className = 'crumb-separator';
      sep.textContent = '›';
      container.appendChild(sep);
    }
  });

  // Auto-scroll al final en móviles
  container.scrollLeft = container.scrollWidth;
}

/** Aplica el filtro de búsqueda a los archivos y unidades */
function applyFilter() {
  const query = AppState.searchQuery.trim().toLowerCase();

  // Si estamos en Inicio y se muestra el panel de unidades, filtrar las tarjetas de unidades
  const drivesGrid = document.getElementById('drivesGrid');
  if (drivesGrid && (!AppState.currentPath || AppState.currentPath === '')) {
    const driveCards = drivesGrid.children;
    for (let card of driveCards) {
      if (!query) {
        card.style.display = '';
      } else {
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? '' : 'none';
      }
    }
  }

  if (!query) {
    AppState.filteredItems = [...AppState.items];
  } else {
    AppState.filteredItems = AppState.items.filter(item =>
      item.name.toLowerCase().includes(query)
    );
  }
  renderExplorer();
}

/** Renderiza la lista/cuadrícula de elementos */
function renderExplorer() {
  const container = document.getElementById('explorerContainer');
  const emptyState = document.getElementById('emptyState');
  if (!container) return;

  container.innerHTML = '';

  // En la pantalla de Inicio (sin carpeta abierta y sin búsqueda), solo mostrar los discos
  if ((!AppState.currentPath || AppState.currentPath === '') && !AppState.searchQuery) {
    container.style.display = 'none';
    if (emptyState) emptyState.style.display = 'none';
    return;
  }

  if (AppState.filteredItems.length === 0) {
    container.style.display = 'none';
    if (emptyState) {
      if (!AppState.currentPath || AppState.currentPath === '') {
        emptyState.style.display = 'none';
        return;
      }
      emptyState.style.display = 'block';
      const emptyText = emptyState.querySelector('p');
      if (emptyText) {
        emptyText.textContent = AppState.searchQuery
          ? 'No se encontraron archivos que coincidan con la búsqueda.'
          : 'Esta carpeta está vacía. ¡Puedes subir archivos desde tu celular!';
      }
    }
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  container.style.display = 'grid';

  AppState.filteredItems.forEach(item => {
    const card = document.createElement('div');
    card.className = `file-card ${item.is_dir ? 'is-folder' : ''} ${item.category === 'audio' ? 'is-audio' : ''}`;
    card.dataset.path = item.path;

    // Icono correspondiente
    let iconClass = 'icon-document';
    let iconEmoji = '📄';

    if (item.is_dir) {
      iconClass = 'icon-folder';
      iconEmoji = '📁';
    } else if (item.category === 'audio') {
      iconClass = 'icon-audio';
      iconEmoji = '🎵';
    } else if (item.category === 'midi' || (item.extension && ['mid', 'midi'].includes(item.extension.toLowerCase()))) {
      iconClass = 'icon-audio';
      iconEmoji = '🎹';
    } else if (item.category === 'video') {
      iconClass = 'icon-video';
      iconEmoji = '🎬';
    } else if (item.category === 'image') {
      iconClass = 'icon-image';
      iconEmoji = '🖼️';
    } else if (item.category === 'archive') {
      iconClass = 'icon-archive';
      iconEmoji = '📦';
    }

    const isCurrentPlaying = AppState.currentTrack && AppState.currentTrack.path === item.path && AppState.currentAudio && !AppState.currentAudio.paused;
    if (isCurrentPlaying) card.classList.add('is-playing');

    card.innerHTML = `
      <div class="card-left">
        ${item.category === 'image' ? `
          <div class="item-icon icon-image has-thumb" style="padding:0; overflow:hidden; border-radius:10px; background:rgba(0,0,0,0.3); width:40px; height:40px; flex-shrink:0;">
            <img
              src="/api/preview?path=${encodeURIComponent(item.path)}"
              alt=""
              loading="lazy"
              style="width:100%; height:100%; object-fit:cover; display:block;"
              onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';"
            />
            <div style="display:none; width:100%; height:100%; align-items:center; justify-content:center; font-size:1.3rem;">🖼️</div>
          </div>
        ` : `
          <div class="item-icon ${iconClass}">
            ${iconEmoji}
          </div>
        `}
        <div class="item-details">
          <div class="item-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
          <div class="item-meta">
            <span>${item.size_human}</span>
            <span>•</span>
            <span>${item.mtime_human}</span>
          </div>
        </div>
      </div>
      <div class="card-actions">
        ${item.category === 'audio' ? `
          <button class="btn-card-action btn-play-audio" title="Escuchar antes de descargar" data-action="play">
            ${isCurrentPlaying ? '❚❚ Sonando' : '▶ Escuchar'}
          </button>
        ` : ''}
        ${item.category === 'midi' || (item.extension && ['mid', 'midi'].includes(item.extension.toLowerCase())) ? `
          <button class="btn-card-action" title="Ver información del MIDI" data-action="view" style="background:rgba(16,185,129,0.18);color:var(--accent-emerald);border-color:rgba(16,185,129,0.3); font-weight:600; padding:6px 10px;">🎹 MIDI</button>
        ` : ''}
        ${item.category === 'image' ? `
          <button class="btn-card-action" title="Ver imagen en grande" data-action="view" style="background:rgba(245,158,11,0.18);color:var(--accent-amber);border-color:rgba(245,158,11,0.3); font-weight:600; padding:6px 10px;">🔍 Ver</button>
        ` : ''}
        ${item.category === 'video' ? `
          <button class="btn-card-action" title="Reproducir video" data-action="view" style="background:rgba(168,85,247,0.18);color:var(--accent-purple);border-color:rgba(168,85,247,0.3); font-weight:600; padding:6px 10px;">▶ Ver</button>
        ` : ''}
        ${item.category === 'code' || (item.extension && ['txt','md','log','csv','json','xml','yaml','yml','py','js','html','css','sh','sql'].includes(item.extension)) ? `
          <button class="btn-card-action" title="Ver texto" data-action="view" style="background:rgba(59,130,246,0.18);color:var(--accent-blue);border-color:rgba(59,130,246,0.3); font-weight:600; padding:6px 10px;">📄 Ver</button>
        ` : ''}
        ${item.extension === 'pdf' ? `
          <button class="btn-card-action" title="Ver PDF" data-action="view" style="background:rgba(244,63,94,0.18);color:var(--accent-rose);border-color:rgba(244,63,94,0.3); font-weight:600; padding:6px 10px;">📄 Ver</button>
        ` : ''}
        ${!item.is_dir ? `
          <button class="btn-card-action" title="Descargar directo" data-action="download">⬇</button>
        ` : ''}
      </div>
    `;

    // Click en la tarjeta
    card.onclick = (e) => {
      const actionBtn = e.target.closest('[data-action]');
      if (actionBtn) {
        e.stopPropagation();
        const action = actionBtn.getAttribute('data-action');
        if (action === 'play') {
          renderAudioPreviewModal(item);
        } else if (action === 'view') {
          openFileViewer(item);
        } else if (action === 'download') {
          downloadFile(item.path, item.name);
        } else if (action === 'delete') {
          confirmDeleteItem(item);
        }
        return;
      }

      // Click en cualquier parte de la tarjeta
      if (item.is_dir) {
        loadDirectory(item.path);
      } else if (item.category === 'audio') {
        renderAudioPreviewModal(item);
      } else {
        // Para todos los demás, intentar vista previa
        openFileViewer(item);
      }
    };

    // Menú contextual con clic derecho (PC)
    card.oncontextmenu = (e) => {
      e.preventDefault();
      showContextMenu(e, item);
    };

    // Soporte para pulsación prolongada en pantallas táctiles (Móvil)
    let touchTimer = null;
    let touchMoved = false;
    card.addEventListener('touchstart', (e) => {
      touchMoved = false;
      if (e.touches.length === 1) {
        const touch = e.touches[0];
        touchTimer = setTimeout(() => {
          if (!touchMoved) {
            showContextMenu({
              clientX: touch.clientX,
              clientY: touch.clientY,
              preventDefault: () => {}
            }, item);
          }
        }, 550);
      }
    }, { passive: true });

    card.addEventListener('touchmove', () => {
      touchMoved = true;
      if (touchTimer) clearTimeout(touchTimer);
    }, { passive: true });

    card.addEventListener('touchend', () => {
      if (touchTimer) clearTimeout(touchTimer);
    }, { passive: true });

    container.appendChild(card);
  });
}

// ==========================================================================
// Acciones de Archivos: Descargar, Reproducir, Eliminar
// ==========================================================================

/** Descarga un archivo a través de la API */
function downloadFile(relPath, filename) {
  if (relPath && filename) {
    recordRecentFile({
      name: filename,
      path: relPath,
      category: getCategoryFromFilename(filename),
      extension: (filename.split('.').pop() || '').toLowerCase(),
      size_formatted: ''
    });
  }
  showToast(`Descargando ${filename}...`, 'success');
  const url = `/api/download?path=${encodeURIComponent(relPath)}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ==========================================================================
// Visor de Archivos (Imágenes, Video, Texto, PDF)
// ==========================================================================

/** Detecta el tipo de archivo y abre el visor apropiado */
async function openFileViewer(item) {
  if (!item) return;
  recordRecentFile(item);

  if (item.category === 'audio') {
    renderAudioPreviewModal(item);
    return;
  }

  if (item.category === 'midi' || (item.extension && ['mid', 'midi'].includes(item.extension.toLowerCase()))) {
    renderMidiPreviewModal(item);
    return;
  }

  if (item.category === 'image') {
    renderImagePreviewModal(item);
    return;
  }

  if (item.category === 'video') {
    renderVideoPreviewModal(item);
    return;
  }

  if (item.extension === 'pdf') {
    renderPdfPreviewModal(item);
    return;
  }

  const TEXT_EXTS = new Set(['txt','md','log','csv','json','xml','yaml','yml','py','js','ts','html','css','sh','sql','c','cpp','java','php','rb','ini','conf','cfg','env','toml','properties','nfo']);
  if (item.category === 'code' || TEXT_EXTS.has((item.extension || '').toLowerCase())) {
    renderTextPreviewModal(item);
    return;
  }

  renderGenericFileModal(item);
}

function getImagePlaylist() {
  return AppState.items.filter(item => !item.is_dir && item.category === 'image');
}

/** Renderiza el visor informativo de archivos MIDI */
function renderMidiPreviewModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  body.innerHTML = `
    <div style="padding:28px 16px; text-align:center; display:flex; flex-direction:column; align-items:center; gap:16px;">
      <div style="font-size:3.8rem;">🎹</div>
      <div>
        <h3 style="font-size:1.15rem; font-weight:700; margin-bottom:6px; color:var(--text-primary); word-break:break-word;">
          ${escapeHtml(item.name)}
        </h3>
        <p style="color:var(--text-muted); font-size:0.85rem;">
          Secuencia MIDI Digital • ${item.size_human} • ${item.mtime_human}
        </p>
      </div>

      <div style="
        background: rgba(16,185,129,0.08);
        border: 1px solid rgba(16,185,129,0.25);
        border-radius: 14px;
        padding: 16px;
        max-width: 380px;
        text-align: left;
        font-size: 0.82rem;
        line-height: 1.5;
        color: var(--text-secondary);
      ">
        <strong style="color: var(--accent-emerald); display:block; margin-bottom:6px;">ℹ️ Información MIDI</strong>
        Este archivo contiene notas y secuencias musicales para tu DAW (<strong>FL Studio, Ableton Live, Logic Pro, Cubase</strong>). Los navegadores no reproducen archivos MIDI directamente porque no son audio grabado. Descárgalo para cargarlo en tu proyecto musical.
      </div>

      <div style="width:100%; max-width:380px; margin-top:8px;">
        <button class="btn-download-hero" id="btnMidiHeroDownload">
          <span class="download-icon">⬇️</span>
          <span class="download-text">
            <strong>Descargar Archivo MIDI</strong>
            <small>${escapeHtml(item.name)} (${item.size_human})</small>
          </span>
        </button>
      </div>
    </div>
  `;

  modal.classList.add('open');

  const heroBtn = document.getElementById('btnMidiHeroDownload');
  if (heroBtn) heroBtn.onclick = () => downloadFile(item.path, item.name);
}

/** Renderiza el visor de imágenes con navegación, spinner y botón de descarga */
function renderImagePreviewModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  const previewUrl = `/api/preview?path=${encodeURIComponent(item.path)}`;

  body.innerHTML = `
    <div class="image-preview-container">
      <!-- Indicador de carga mientras descarga la imagen en alta calidad -->
      <div id="imageViewerLoader" style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:220px; color:var(--text-muted); gap:12px;">
        <div class="spinner"></div>
        <span style="font-size:0.85rem;">Cargando imagen en alta calidad...</span>
      </div>

      <!-- Contenedor de la imagen -->
      <div class="image-viewer-stage" style="display:none;" id="imageStage">
        <img
          id="mainPreviewImg"
          src="${previewUrl}"
          alt="${escapeHtml(item.name)}"
          class="preview-main-img"
        />
      </div>

      <!-- Barra de detalles -->
      <div class="image-meta-bar">
        <span class="badge-tag">🖼️ ${escapeHtml(item.extension ? item.extension.toUpperCase() : 'IMAGEN')}</span>
        <span class="badge-tag" id="imageDimensions">Calculando...</span>
        <span class="badge-tag">💾 ${item.size_human}</span>
      </div>

      <!-- Controles de navegación entre imágenes de la carpeta -->
      <div class="preview-nav-row">
        <button class="btn-circle-secondary" id="btnPrevImage" title="Imagen anterior">
          ⏮ Anterior
        </button>
        <button class="btn-circle-secondary" id="btnNextImage" title="Imagen siguiente">
          Siguiente ⏭
        </button>
      </div>

      <!-- Botón de descarga principal -->
      <div style="width:100%; max-width:380px; margin-top:6px;">
        <button class="btn-download-hero" id="btnImageHeroDownload">
          <span class="download-icon">⬇️</span>
          <span class="download-text">
            <strong>Descargar esta Imagen</strong>
            <small>${escapeHtml(item.name)} (${item.size_human})</small>
          </span>
        </button>
      </div>
    </div>
  `;

  modal.classList.add('open');

  const imgEl = document.getElementById('mainPreviewImg');
  if (imgEl) {
    const handleLoaded = () => {
      const loader = document.getElementById('imageViewerLoader');
      if (loader) loader.style.display = 'none';
      const stage = document.getElementById('imageStage');
      if (stage) stage.style.display = 'flex';
      const dimEl = document.getElementById('imageDimensions');
      if (dimEl && imgEl.naturalWidth) dimEl.textContent = `${imgEl.naturalWidth} × ${imgEl.naturalHeight} px`;
    };
    imgEl.onload = handleLoaded;
    imgEl.onerror = () => {
      const loader = document.getElementById('imageViewerLoader');
      if (loader) loader.style.display = 'none';
      const stage = document.getElementById('imageStage');
      if (stage) {
        stage.style.display = 'flex';
        stage.innerHTML = '<p style="color:var(--accent-rose); padding:30px; text-align:center;">⚠️ No se pudo cargar la vista previa de la imagen.</p>';
      }
    };
    if (imgEl.complete && imgEl.naturalWidth > 0) {
      handleLoaded();
    }
  }

  const heroBtn = document.getElementById('btnImageHeroDownload');
  if (heroBtn) heroBtn.onclick = () => downloadFile(item.path, item.name);

  const prevBtn = document.getElementById('btnPrevImage');
  if (prevBtn) {
    prevBtn.onclick = () => {
      const playlist = getImagePlaylist();
      if (!playlist.length) return;
      const idx = playlist.findIndex(it => it.path === item.path);
      const nextIdx = (idx - 1 + playlist.length) % playlist.length;
      renderImagePreviewModal(playlist[nextIdx]);
    };
  }

  const nextBtn = document.getElementById('btnNextImage');
  if (nextBtn) {
    nextBtn.onclick = () => {
      const playlist = getImagePlaylist();
      if (!playlist.length) return;
      const idx = playlist.findIndex(it => it.path === item.path);
      const nextIdx = (idx + 1) % playlist.length;
      renderImagePreviewModal(playlist[nextIdx]);
    };
  }
}

/** Renderiza el visor de video */
function renderVideoPreviewModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  const previewUrl = `/api/preview?path=${encodeURIComponent(item.path)}`;

  body.innerHTML = `
    <div style="padding:16px 12px; display:flex; flex-direction:column; align-items:center; gap:16px;">
      <video
        controls
        playsinline
        autoplay
        style="width:100%; max-height:65vh; border-radius:12px; background:#000; box-shadow:0 8px 30px rgba(0,0,0,0.5);"
        src="${previewUrl}"
      >
        Tu navegador no soporta reproducción de video.
      </video>

      <div class="image-meta-bar">
        <span class="badge-tag">🎬 ${escapeHtml(item.extension ? item.extension.toUpperCase() : 'VIDEO')}</span>
        <span class="badge-tag">💾 ${item.size_human}</span>
      </div>

      <div style="width:100%; max-width:380px;">
        <button class="btn-download-hero" id="btnVideoHeroDownload">
          <span class="download-icon">⬇️</span>
          <span class="download-text">
            <strong>Descargar este Video</strong>
            <small>${escapeHtml(item.name)} (${item.size_human})</small>
          </span>
        </button>
      </div>
    </div>
  `;

  modal.classList.add('open');

  const heroBtn = document.getElementById('btnVideoHeroDownload');
  if (heroBtn) heroBtn.onclick = () => downloadFile(item.path, item.name);
}

/** Renderiza el visor de documentos PDF */
function renderPdfPreviewModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  const previewUrl = `/api/preview?path=${encodeURIComponent(item.path)}`;

  body.innerHTML = `
    <div style="padding:28px 16px; text-align:center; display:flex; flex-direction:column; align-items:center; gap:16px;">
      <div style="font-size:3.5rem;">📄</div>
      <div>
        <h3 style="font-size:1.15rem; font-weight:700; margin-bottom:6px;">${escapeHtml(item.name)}</h3>
        <p style="color:var(--text-muted); font-size:0.85rem;">Documento PDF • ${item.size_human}</p>
      </div>

      <div style="display:flex; flex-direction:column; gap:12px; width:100%; max-width:340px; margin-top:8px;">
        <a href="${previewUrl}" target="_blank" class="btn-action btn-primary" style="padding:14px; text-decoration:none; justify-content:center; font-weight:600; border-radius:12px;">
          📖 Ver PDF en Pantalla Completa
        </a>
        <button class="btn-download-hero" id="btnPdfHeroDownload">
          <span class="download-icon">⬇️</span>
          <span class="download-text">
            <strong>Descargar PDF</strong>
            <small>${escapeHtml(item.name)} (${item.size_human})</small>
          </span>
        </button>
      </div>
    </div>
  `;

  modal.classList.add('open');

  const heroBtn = document.getElementById('btnPdfHeroDownload');
  if (heroBtn) heroBtn.onclick = () => downloadFile(item.path, item.name);
}

/** Renderiza el visor de texto y código con líneas y descarga */
async function renderTextPreviewModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  body.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted);">Cargando texto...</div>`;
  modal.classList.add('open');

  const previewUrl = `/api/preview?path=${encodeURIComponent(item.path)}`;

  try {
    const res = await fetch(previewUrl);
    const data = await res.json();

    if (data.error) {
      body.innerHTML = `
        <div style="padding:30px 20px; text-align:center;">
          <p style="color:var(--accent-amber); margin-bottom:16px;">${escapeHtml(data.error)}</p>
          <button class="btn-download-hero" id="btnTextErrDownload" style="max-width:320px; margin:0 auto;">
            ⬇️ Descargar archivo (${item.size_human})
          </button>
        </div>`;
      const btn = document.getElementById('btnTextErrDownload');
      if (btn) btn.onclick = () => downloadFile(item.path, item.name);
      return;
    }

    if (data.type === 'text') {
      const escaped = escapeHtml(data.content);
      body.innerHTML = `
        <div style="padding:4px 0; display:flex; flex-direction:column;">
          <div style="font-size:0.75rem; color:var(--text-muted); padding:8px 16px; border-bottom:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
            <span>${escapeHtml(data.extension ? data.extension.toUpperCase() : 'TEXTO')} • ${data.content.split('\n').length} líneas</span>
            <button class="btn-card-action" id="btnCopyText" style="padding:4px 8px; font-size:0.75rem;">📋 Copiar</button>
          </div>
          <pre style="
            margin:0;
            padding:14px 16px;
            overflow:auto;
            max-height:60vh;
            font-family:'Courier New',Courier,monospace;
            font-size:0.82rem;
            line-height:1.6;
            color:var(--text-primary);
            white-space:pre-wrap;
            word-break:break-all;
          ">${escaped}</pre>
          <div style="padding:12px 16px; border-top:1px solid var(--border-subtle); text-align:center;">
            <button class="btn-download-hero" id="btnTextHeroDownload" style="max-width:340px; margin:0 auto;">
              ⬇️ Descargar archivo (${item.size_human})
            </button>
          </div>
        </div>`;

      const copyBtn = document.getElementById('btnCopyText');
      if (copyBtn) {
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(data.content);
          showToast('Texto copiado al portapapeles', 'success');
        };
      }
      const dlHero = document.getElementById('btnTextHeroDownload');
      if (dlHero) dlHero.onclick = () => downloadFile(item.path, item.name);
      return;
    }
  } catch (err) {
    body.innerHTML = `<p style="color:var(--accent-rose);padding:30px;text-align:center;">Error cargando vista previa.</p>`;
  }
}

/** Renderiza la tarjeta informativa para cualquier otro archivo */
function renderGenericFileModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  let icon = '📦';
  let typeDesc = 'Archivo';
  const ext = (item.extension || '').toLowerCase();
  if (['doc', 'docx'].includes(ext)) {
    icon = '📝'; typeDesc = 'Documento Microsoft Word';
  } else if (['xls', 'xlsx'].includes(ext)) {
    icon = '📊'; typeDesc = 'Hoja de Cálculo Excel';
  } else if (['ppt', 'pptx'].includes(ext)) {
    icon = '📽️'; typeDesc = 'Presentación PowerPoint';
  } else if (['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'].includes(ext)) {
    icon = '🗜️'; typeDesc = 'Archivo Comprimido';
  } else if (['fxp', 'flp', 'als', 'sf2', 'nki'].includes(ext)) {
    icon = '🎹'; typeDesc = 'Preset o Proyecto Musical';
  } else if (['exe', 'deb', 'appimage', 'apk', 'dmg', 'iso'].includes(ext)) {
    icon = '⚙️'; typeDesc = 'Instalador o Programa';
  }

  body.innerHTML = `
    <div style="padding:32px 20px; text-align:center; display:flex; flex-direction:column; align-items:center; gap:16px;">
      <div style="font-size:3.5rem;">${icon}</div>
      <div>
        <h3 style="font-size:1.15rem; font-weight:700; margin-bottom:6px; word-break:break-word;">${escapeHtml(item.name)}</h3>
        <p style="color:var(--text-muted); font-size:0.85rem;">${typeDesc} • ${item.size_human} • ${item.mtime_human}</p>
      </div>

      <div style="width:100%; max-width:340px; margin-top:8px;">
        <button class="btn-download-hero" id="btnGenericHeroDownload">
          <span class="download-icon">⬇️</span>
          <span class="download-text">
            <strong>Descargar al Celular</strong>
            <small>${escapeHtml(item.name)} (${item.size_human})</small>
          </span>
        </button>
      </div>
    </div>
  `;

  modal.classList.add('open');

  const heroBtn = document.getElementById('btnGenericHeroDownload');
  if (heroBtn) heroBtn.onclick = () => downloadFile(item.path, item.name);
}

/** Cierra el visor de archivos */
function closeFileViewer() {
  const modal = document.getElementById('fileViewerModal');
  if (!modal) return;
  modal.classList.remove('open');
  // Detener cualquier video o audio en reproducción dentro del modal
  const videos = modal.querySelectorAll('video');
  videos.forEach(v => { v.pause(); v.src = ''; });
  const body = document.getElementById('viewerBody');
  if (body) body.innerHTML = '';
}

/** Confirma y elimina un archivo */
async function confirmDeleteItem(item) {
  if (!item) return;
  if (item.is_dir) {
    showToast('La eliminación de carpetas está desactivada por seguridad.', 'error');
    return;
  }
  const msg = `¿Estás seguro de eliminar el archivo "${item.name}"?`;

  if (!confirm(msg)) return;

  try {
    const res = await fetch('/api/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: item.path }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error al eliminar');

    showToast(data.message, 'success');
    loadDirectory(AppState.currentPath);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ==========================================================================
// ==========================================================================
// Reproductor de Audio Flotante y Visor de Audio (Preview & Download)
// ==========================================================================

function getAudioPlaylist() {
  return AppState.items.filter(item => !item.is_dir && item.category === 'audio');
}

function initAudioPlayer() {
  AppState.currentAudio = new Audio();

  const audio = AppState.currentAudio;
  const playPauseBtn = document.getElementById('btnPlayPause');
  const progressBar = document.getElementById('audioProgressBar');
  const currentTimeEl = document.getElementById('audioCurrentTime');
  const totalDurationEl = document.getElementById('audioTotalDuration');

  audio.addEventListener('timeupdate', () => {
    if (!audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    if (progressBar) progressBar.style.width = `${pct}%`;
    const formatted = formatAudioTime(audio.currentTime);
    if (currentTimeEl) currentTimeEl.textContent = formatted;

    // Sincronizar modal de preview si está abierto
    const modalSlider = document.getElementById('modalSeekSlider');
    const modalCurrent = document.getElementById('modalCurrentTime');
    if (modalSlider && !modalSlider.dataset.dragging) modalSlider.value = pct;
    if (modalCurrent) modalCurrent.textContent = formatted;
  });

  audio.addEventListener('loadedmetadata', () => {
    const formatted = formatAudioTime(audio.duration);
    if (totalDurationEl) totalDurationEl.textContent = formatted;
    const modalDuration = document.getElementById('modalTotalDuration');
    if (modalDuration) modalDuration.textContent = formatted;
  });

  audio.addEventListener('play', () => {
    if (playPauseBtn) playPauseBtn.innerHTML = '❚❚';
    const status = document.getElementById('playerTrackStatus');
    if (status) status.textContent = 'Reproduciendo • Toca para expandir';

    const modalBtn = document.getElementById('btnModalPlayPause');
    if (modalBtn) modalBtn.innerHTML = '❚❚';

    const disc = document.getElementById('modalVinylDisc');
    if (disc) disc.classList.add('spinning');

    const waves = document.getElementById('modalSoundWaves');
    if (waves) waves.classList.add('active');

    if (AppState.currentTrack) highlightActiveCard(AppState.currentTrack.path, true);
  });

  audio.addEventListener('pause', () => {
    if (playPauseBtn) playPauseBtn.innerHTML = '▶';
    const status = document.getElementById('playerTrackStatus');
    if (status) status.textContent = 'Pausado • Toca para expandir';

    const modalBtn = document.getElementById('btnModalPlayPause');
    if (modalBtn) modalBtn.innerHTML = '▶';

    const disc = document.getElementById('modalVinylDisc');
    if (disc) disc.classList.remove('spinning');

    const waves = document.getElementById('modalSoundWaves');
    if (waves) waves.classList.remove('active');

    if (AppState.currentTrack) highlightActiveCard(AppState.currentTrack.path, false);
  });

  audio.addEventListener('ended', () => {
    if (playPauseBtn) playPauseBtn.innerHTML = '▶';
    if (progressBar) progressBar.style.width = '0%';
    const modalBtn = document.getElementById('btnModalPlayPause');
    if (modalBtn) modalBtn.innerHTML = '▶';
    const disc = document.getElementById('modalVinylDisc');
    if (disc) disc.classList.remove('spinning');
    const waves = document.getElementById('modalSoundWaves');
    if (waves) waves.classList.remove('active');

    // Reproducir automáticamente la siguiente pista de la carpeta
    playNextTrack();
  });

  audio.addEventListener('error', (e) => {
    console.warn('Error en reproducción de audio:', e);
    const errExt = (AppState.currentTrack?.extension || '').toLowerCase();
    if (errExt === 'mid' || errExt === 'midi') {
      showToast('Los archivos .MIDI son secuencias digitales para DAW (FL Studio, Ableton), no audio grabado. Puedes descargarlo directamente.', 'warning');
    } else {
      showToast('El navegador no pudo reproducir este archivo directamente. Puedes descargarlo a tu celular.', 'warning');
    }
    const status = document.getElementById('playerTrackStatus');
    if (status) status.textContent = 'Formato no reproducible en el navegador';
    const disc = document.getElementById('modalVinylDisc');
    if (disc) disc.classList.remove('spinning');
    const waves = document.getElementById('modalSoundWaves');
    if (waves) waves.classList.remove('active');
    if (playPauseBtn) playPauseBtn.innerHTML = '▶';
    const modalBtn = document.getElementById('btnModalPlayPause');
    if (modalBtn) modalBtn.innerHTML = '▶';
  });

  // Barra para adelantar / atrasar canción en el dock flotante
  const scrubTrack = document.getElementById('audioScrubTrack');
  if (scrubTrack) {
    scrubTrack.onclick = (e) => {
      if (!audio.duration) return;
      const rect = scrubTrack.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(1, clickX / rect.width));
      audio.currentTime = pct * audio.duration;
    };
  }
}

/** Inicia la reproducción de una pista de audio */
function playAudioTrack(item, openModal = false) {
  if (item) recordRecentFile(item);
  const dock = document.getElementById('audioDock');
  const title = document.getElementById('playerTrackTitle');
  const audio = AppState.currentAudio;

  if (title) title.textContent = item.name;
  if (dock) dock.classList.add('active');

  const isSameTrack = AppState.currentTrack && AppState.currentTrack.path === item.path;
  AppState.currentTrack = item;

  if (!isSameTrack || !audio.src) {
    audio.src = `/api/stream?path=${encodeURIComponent(item.path)}`;
    audio.play().catch(err => {
      console.warn('Auto-reproducción bloqueada por navegador:', err);
      showToast('Toca el botón play para iniciar audio', 'info');
    });
  } else if (audio.paused) {
    audio.play().catch(() => {});
  }

  highlightActiveCard(item.path, true);

  if (openModal) {
    renderAudioPreviewModal(item);
  }
}

/** Renderiza el visor/reproductor completo de audio antes de descargar */
function renderAudioPreviewModal(item) {
  const modal = document.getElementById('fileViewerModal');
  const title = document.getElementById('viewerTitle');
  const body = document.getElementById('viewerBody');
  const dlBtn = document.getElementById('viewerDownloadBtn');

  if (!modal || !body) return;

  if (title) title.textContent = item.name;
  if (dlBtn) dlBtn.onclick = () => downloadFile(item.path, item.name);

  const isCurrent = AppState.currentTrack && AppState.currentTrack.path === item.path;
  const isPlaying = isCurrent && AppState.currentAudio && !AppState.currentAudio.paused;

  body.innerHTML = `
    <div class="audio-preview-container">
      <div class="audio-preview-visual">
        <div class="vinyl-disc ${isPlaying ? 'spinning' : ''}" id="modalVinylDisc">
          <div class="vinyl-center">🎵</div>
        </div>
        <div class="sound-wave-bars ${isPlaying ? 'active' : ''}" id="modalSoundWaves">
          <span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
      </div>

      <div class="audio-preview-meta">
        <div class="audio-preview-title">${escapeHtml(item.name)}</div>
        <div class="audio-preview-tags">
          <span class="badge-tag">🎵 ${escapeHtml(item.extension ? item.extension.toUpperCase() : 'AUDIO')}</span>
          <span class="badge-tag">💾 ${item.size_human}</span>
          <span class="badge-tag">📅 ${item.mtime_human}</span>
        </div>
      </div>

      <div class="audio-preview-player">
        <div class="preview-scrubber">
          <span id="modalCurrentTime">0:00</span>
          <input type="range" id="modalSeekSlider" min="0" max="100" value="0" step="0.1" class="audio-seek-slider" />
          <span id="modalTotalDuration">0:00</span>
        </div>

        <div class="preview-controls-row">
          <button class="btn-circle-secondary" onclick="playModalPrevTrack()" title="Pista anterior">⏮</button>
          <button class="btn-circle-secondary" onclick="skipAudio(-10)" title="Retroceder 10s">⏪ 10s</button>
          <button class="btn-circle-primary" id="btnModalPlayPause" onclick="toggleModalPlayPause()" title="Reproducir / Pausar">
            ${isPlaying ? '❚❚' : '▶'}
          </button>
          <button class="btn-circle-secondary" onclick="skipAudio(10)" title="Adelantar 10s">10s ⏩</button>
          <button class="btn-circle-secondary" onclick="playModalNextTrack()" title="Pista siguiente">⏭</button>
        </div>
      </div>

      <div class="audio-preview-download-box">
        <p class="download-box-text">¿Es este el audio que buscabas? Descárgalo a tu celular:</p>
        <button class="btn-download-hero" id="btnHeroDownload">
          <span class="download-icon">⬇️</span>
          <span class="download-text">
            <strong>Descargar al Celular</strong>
            <small>${escapeHtml(item.name)} (${item.size_human})</small>
          </span>
        </button>
      </div>
    </div>
  `;

  modal.classList.add('open');

  const heroBtn = document.getElementById('btnHeroDownload');
  if (heroBtn) {
    heroBtn.onclick = () => downloadFile(item.path, item.name);
  }

  // Control deslizante de posición (Seek bar)
  const slider = document.getElementById('modalSeekSlider');
  if (slider) {
    slider.onmousedown = slider.ontouchstart = () => { slider.dataset.dragging = 'true'; };
    slider.oninput = (e) => {
      const audio = AppState.currentAudio;
      if (audio && audio.duration) {
        const modalCurrent = document.getElementById('modalCurrentTime');
        const targetTime = (e.target.value / 100) * audio.duration;
        if (modalCurrent) modalCurrent.textContent = formatAudioTime(targetTime);
      }
    };
    slider.onchange = (e) => {
      delete slider.dataset.dragging;
      const audio = AppState.currentAudio;
      if (audio && audio.duration) {
        audio.currentTime = (e.target.value / 100) * audio.duration;
      }
    };
  }

  // Si no está sonando este track o está pausado, iniciarlo
  if (!isCurrent) {
    playAudioTrack(item, false);
  } else if (AppState.currentAudio && AppState.currentAudio.duration) {
    const modalCurrent = document.getElementById('modalCurrentTime');
    const modalDuration = document.getElementById('modalTotalDuration');
    const modalSlider = document.getElementById('modalSeekSlider');
    if (modalCurrent) modalCurrent.textContent = formatAudioTime(AppState.currentAudio.currentTime);
    if (modalDuration) modalDuration.textContent = formatAudioTime(AppState.currentAudio.duration);
    if (modalSlider) modalSlider.value = (AppState.currentAudio.currentTime / AppState.currentAudio.duration) * 100;
  }
}

/** Salta un número de segundos en la reproducción (+10s o -10s) */
function skipAudio(seconds) {
  const audio = AppState.currentAudio;
  if (!audio || isNaN(audio.duration)) return;
  audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
}

/** Alterna Play/Pausa en el modal */
function toggleModalPlayPause() {
  togglePlayPause();
}

/** Pista anterior en la lista para el modal */
function playModalPrevTrack() {
  const playlist = getAudioPlaylist();
  if (!playlist.length || !AppState.currentTrack) return;
  const currentIndex = playlist.findIndex(it => it.path === AppState.currentTrack.path);
  const prevIndex = (currentIndex - 1 + playlist.length) % playlist.length;
  renderAudioPreviewModal(playlist[prevIndex]);
}

/** Pista siguiente en la lista para el modal */
function playModalNextTrack() {
  const playlist = getAudioPlaylist();
  if (!playlist.length || !AppState.currentTrack) return;
  const currentIndex = playlist.findIndex(it => it.path === AppState.currentTrack.path);
  const nextIndex = (currentIndex + 1) % playlist.length;
  renderAudioPreviewModal(playlist[nextIndex]);
}

/** Pista siguiente para el dock */
function playNextTrack() {
  const playlist = getAudioPlaylist();
  if (!playlist.length || !AppState.currentTrack) return;
  const currentIndex = playlist.findIndex(it => it.path === AppState.currentTrack.path);
  const nextIndex = (currentIndex + 1) % playlist.length;
  playAudioTrack(playlist[nextIndex], false);
  const modal = document.getElementById('fileViewerModal');
  if (modal && modal.classList.contains('open') && AppState.currentTrack.category === 'audio') {
    renderAudioPreviewModal(playlist[nextIndex]);
  }
}

/** Pista anterior para el dock */
function playPreviousTrack() {
  const playlist = getAudioPlaylist();
  if (!playlist.length || !AppState.currentTrack) return;
  const currentIndex = playlist.findIndex(it => it.path === AppState.currentTrack.path);
  const prevIndex = (currentIndex - 1 + playlist.length) % playlist.length;
  playAudioTrack(playlist[prevIndex], false);
  const modal = document.getElementById('fileViewerModal');
  if (modal && modal.classList.contains('open') && AppState.currentTrack.category === 'audio') {
    renderAudioPreviewModal(playlist[prevIndex]);
  }
}

/** Descarga la pista actualmente en reproducción */
function downloadCurrentTrack() {
  if (!AppState.currentTrack) return;
  downloadFile(AppState.currentTrack.path, AppState.currentTrack.name);
}

/** Expande el visor completo de audio desde el dock inferior */
function expandAudioViewer() {
  if (!AppState.currentTrack) return;
  renderAudioPreviewModal(AppState.currentTrack);
}

/** Destaca la tarjeta activa en la lista de archivos */
function highlightActiveCard(activePath, isPlaying = true) {
  document.querySelectorAll('.file-card.is-audio').forEach(card => {
    const playBtn = card.querySelector('.btn-play-audio');
    const isThis = card.dataset.path === activePath;
    if (isThis) {
      card.classList.add('is-playing');
      if (playBtn) playBtn.innerHTML = isPlaying ? '❚❚ Sonando' : '▶ Pausado';
    } else {
      card.classList.remove('is-playing');
      if (playBtn) playBtn.innerHTML = '▶ Escuchar';
    }
  });
}

/** Alterna entre Play y Pause */
function togglePlayPause() {
  const audio = AppState.currentAudio;
  if (!audio.src) return;
  if (audio.paused) {
    audio.play();
  } else {
    audio.pause();
  }
}

/** Cierra el dock del reproductor */
function closeAudioDock() {
  const dock = document.getElementById('audioDock');
  const audio = AppState.currentAudio;
  if (dock) dock.classList.remove('active');
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
  }
  highlightActiveCard('', false);
}

function formatAudioTime(seconds) {
  if (isNaN(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

// ==========================================================================
// Subida de Archivos con Barra de Progreso
// ==========================================================================

function openUploadModal() {
  const modal = document.getElementById('uploadModal');
  const pathLabel = document.getElementById('uploadTargetFolder');
  if (pathLabel) {
    pathLabel.textContent = AppState.currentPath ? `/${AppState.currentPath}` : '/ (Carpeta Raíz)';
  }
  resetUploadProgress();
  if (modal) modal.classList.add('open');
}

function closeUploadModal() {
  const modal = document.getElementById('uploadModal');
  if (modal) modal.classList.remove('open');
  resetUploadProgress();
}

function resetUploadProgress() {
  const progContainer = document.getElementById('uploadProgressContainer');
  const progFill = document.getElementById('uploadProgressBarFill');
  const progText = document.getElementById('uploadProgressPct');
  if (progContainer) progContainer.style.display = 'none';
  if (progFill) progFill.style.width = '0%';
  if (progText) progText.textContent = '0%';
}

/** Realiza la subida de archivos mediante XMLHttpRequest para tracking */
function handleUploadFiles(fileList) {
  if (!fileList || fileList.length === 0) return;

  const formData = new FormData();
  formData.append('path', AppState.currentPath);

  for (let i = 0; i < fileList.length; i++) {
    formData.append('files', fileList[i]);
  }

  const progContainer = document.getElementById('uploadProgressContainer');
  const progFill = document.getElementById('uploadProgressBarFill');
  const progText = document.getElementById('uploadProgressPct');
  const fileCount = document.getElementById('uploadFileCount');

  if (progContainer) progContainer.style.display = 'block';
  if (fileCount) fileCount.textContent = `Subiendo ${fileList.length} archivo(s)...`;

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload', true);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      if (progFill) progFill.style.width = `${pct}%`;
      if (progText) progText.textContent = `${pct}%`;
    }
  };

  xhr.onload = () => {
    try {
      const res = JSON.parse(xhr.responseText);
      if (xhr.status === 200 && res.success) {
        showToast(res.message, 'success');
        closeUploadModal();
        loadDirectory(AppState.currentPath);
      } else {
        showToast(res.error || 'Error al subir archivo', 'error');
      }
    } catch (e) {
      showToast('Error procesando respuesta del servidor', 'error');
    }
  };

  xhr.onerror = () => {
    showToast('Error de conexión al subir archivo', 'error');
  };

  xhr.send(formData);
}

// ==========================================================================
// Creación de Carpeta (mkdir)
// ==========================================================================

function openMkdirModal() {
  const modal = document.getElementById('mkdirModal');
  const input = document.getElementById('folderNameInput');
  if (input) input.value = '';
  if (modal) modal.classList.add('open');
  setTimeout(() => input && input.focus(), 150);
}

function closeMkdirModal() {
  const modal = document.getElementById('mkdirModal');
  if (modal) modal.classList.remove('open');
}

async function submitMkdir() {
  const input = document.getElementById('folderNameInput');
  const folderName = input ? input.value.trim() : '';

  if (!folderName) {
    showToast('Ingresa un nombre para la carpeta', 'error');
    return;
  }

  try {
    const res = await fetch('/api/mkdir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: AppState.currentPath, name: folderName }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error creando carpeta');

    showToast(data.message, 'success');
    closeMkdirModal();
    loadDirectory(AppState.currentPath);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ==========================================================================
// Modal QR
// ==========================================================================

function openQrModal() {
  const modal = document.getElementById('qrModal');
  const img = document.getElementById('qrModalImage');
  if (img) img.src = `/api/qr?t=${Date.now()}`;
  if (modal) modal.classList.add('open');
}

function closeQrModal() {
  const modal = document.getElementById('qrModal');
  if (modal) modal.classList.remove('open');
}

function copyServerUrl() {
  if (!AppState.serverInfo) return;
  navigator.clipboard.writeText(AppState.serverInfo.access_url)
    .then(() => showToast('¡Enlace copiado al portapapeles!', 'success'))
    .catch(() => showToast('No se pudo copiar automáticamente', 'info'));
}

/** Ejecuta la búsqueda profunda desde el botón Buscar o la tecla Enter */
async function handleSearchSubmit(e) {
  if (e) e.preventDefault();
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;

  const query = searchInput.value.trim();
  if (!query) {
    clearSearch();
    return;
  }

  AppState.searchQuery = query;
  searchInput.blur(); // Ocultar teclado virtual en móviles

  // Realizar búsqueda profunda recursiva en el servidor (en todo el disco o carpeta)
  showLoading(true, `Buscando "${query}" en este disco...`);
  try {
    const url = `/api/search?path=${encodeURIComponent(AppState.currentPath)}&q=${encodeURIComponent(query)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Error al realizar la búsqueda en el servidor');
    const data = await res.json();

    renderSearchResults(data.results || [], query, data.limit_reached);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    showLoading(false);
  }
}

/** Renderiza los resultados de la búsqueda profunda */
function renderSearchResults(results, query, limitReached) {
  hideDrivesPanel();
  hideRecentsPanel();

  const container = document.getElementById('explorerContainer');
  const emptyState = document.getElementById('emptyState');
  if (!container) return;

  container.innerHTML = '';

  // Banner informativo con botón para salir de la búsqueda
  const banner = document.createElement('div');
  banner.style.cssText = `
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: var(--radius-md);
    padding: 10px 14px;
    margin-bottom: 8px;
    gap: 8px;
  `;
  banner.innerHTML = `
    <div style="font-size: 0.88rem; color: var(--text-primary);">
      🔍 <strong>${results.length}</strong> resultado(s) para "<strong>${escapeHtml(query)}</strong>"
      ${limitReached ? '<span style="font-size: 0.76rem; color: var(--accent-amber);"> (mostrando los primeros 100)</span>' : ''}
    </div>
    <button class="btn-card-action" onclick="clearSearch()" style="background: rgba(255,255,255,0.08); font-size: 0.8rem; padding: 4px 10px;">
      ✕ Volver
    </button>
  `;
  container.appendChild(banner);

  if (results.length === 0) {
    if (emptyState) emptyState.style.display = 'none';
    const noResults = document.createElement('div');
    noResults.style.cssText = 'grid-column: 1 / -1; text-align: center; padding: 36px 16px; color: var(--text-muted);';
    noResults.innerHTML = `
      <div style="font-size: 2.2rem; margin-bottom: 10px;">🔎</div>
      <p style="font-size: 0.95rem; font-weight: 600; color: var(--text-primary); margin-bottom: 6px;">No se encontraron archivos con ese nombre</p>
      <p style="font-size: 0.82rem;">Verifica cómo está escrito o prueba con una palabra más corta.</p>
      <button class="btn-action" onclick="clearSearch()" style="margin-top: 14px; display: inline-flex;">
        ← Volver a los archivos
      </button>
    `;
    container.appendChild(noResults);
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  container.style.display = 'grid';

  results.forEach(item => {
    const card = document.createElement('div');
    card.className = `file-card ${item.is_dir ? 'is-folder' : ''} ${item.category === 'audio' ? 'is-audio' : ''}`;
    card.dataset.path = item.path;

    let iconClass = 'icon-document';
    let iconEmoji = '📄';

    if (item.is_dir) {
      iconClass = 'icon-folder';
      iconEmoji = '📁';
    } else if (item.category === 'audio') {
      iconClass = 'icon-audio';
      iconEmoji = '🎵';
    } else if (item.category === 'midi' || (item.extension && ['mid', 'midi'].includes(item.extension.toLowerCase()))) {
      iconClass = 'icon-audio';
      iconEmoji = '🎹';
    } else if (item.category === 'video') {
      iconClass = 'icon-video';
      iconEmoji = '🎬';
    } else if (item.category === 'image') {
      iconClass = 'icon-image';
      iconEmoji = '🖼️';
    } else if (item.category === 'archive') {
      iconClass = 'icon-archive';
      iconEmoji = '📦';
    }

    const isCurrentPlaying = AppState.currentTrack && AppState.currentTrack.path === item.path && AppState.currentAudio && !AppState.currentAudio.paused;
    if (isCurrentPlaying) card.classList.add('is-playing');

    const folderDisplay = item.parent_path ? escapeHtml(item.parent_path.split('/').slice(-2).join('/')) : 'Raíz';

    card.innerHTML = `
      <div class="card-left">
        ${item.category === 'image' ? `
          <div class="item-icon icon-image has-thumb" style="padding:0; overflow:hidden; border-radius:10px; background:rgba(0,0,0,0.3); width:40px; height:40px; flex-shrink:0;">
            <img
              src="/api/preview?path=${encodeURIComponent(item.path)}"
              alt=""
              loading="lazy"
              style="width:100%; height:100%; object-fit:cover; display:block;"
              onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';"
            />
            <div style="display:none; width:100%; height:100%; align-items:center; justify-content:center; font-size:1.3rem;">🖼️</div>
          </div>
        ` : `
          <div class="item-icon ${iconClass}">
            ${iconEmoji}
          </div>
        `}
        <div class="item-details">
          <div class="item-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
          <div class="item-meta">
            <span style="color: var(--accent-emerald);">📂 .../${folderDisplay}</span>
            <span>•</span>
            <span>${item.size_human}</span>
          </div>
        </div>
      </div>
      <div class="card-actions">
        ${item.category === 'audio' ? `
          <button class="btn-card-action btn-play-audio" title="Escuchar antes de descargar" data-action="play">
            ${isCurrentPlaying ? '❚❚ Sonando' : '▶ Escuchar'}
          </button>
        ` : ''}
        ${item.category === 'image' || item.category === 'video' || item.extension === 'pdf' ? `
          <button class="btn-card-action" title="Ver" data-action="view" style="font-weight:600; padding:6px 10px;">👁️ Ver</button>
        ` : ''}
        ${!item.is_dir ? `
          <button class="btn-card-action" title="Descargar directo" data-action="download">⬇</button>
        ` : ''}
        ${item.is_dir ? `
          <button class="btn-card-action" title="Abrir carpeta" data-action="open-folder" style="font-weight:600; padding:6px 10px;">📂 Abrir</button>
        ` : ''}
      </div>
    `;

    card.onclick = (e) => {
      const actionBtn = e.target.closest('[data-action]');
      if (actionBtn) {
        e.stopPropagation();
        const act = actionBtn.dataset.action;
        if (act === 'play') playAudioTrack(item);
        else if (act === 'download') downloadFile(item.path, item.name);
        else if (act === 'view') openFileViewer(item);
        else if (act === 'delete') confirmDeleteItem(item);
        else if (act === 'open-folder') {
          clearSearch();
          loadDirectory(item.path);
        }
        return;
      }
      if (item.is_dir) {
        clearSearch();
        loadDirectory(item.path);
      } else if (item.category === 'audio') {
        playAudioTrack(item);
      } else {
        openFileViewer(item);
      }
    };

    // Menú contextual en resultados de búsqueda
    card.oncontextmenu = (e) => {
      e.preventDefault();
      showContextMenu(e, item);
    };

    container.appendChild(card);
  });
}

/** Limpia el campo de búsqueda y restaura la vista */
function clearSearch() {
  const searchInput = document.getElementById('searchInput');
  const clearBtn = document.getElementById('btnClearSearch');
  if (searchInput) {
    searchInput.value = '';
  }
  if (clearBtn) clearBtn.style.display = 'none';
  AppState.searchQuery = '';
  loadDirectory(AppState.currentPath, false);
}

// ==========================================================================
// Event Listeners y Utilidades
// ==========================================================================

function setupEventListeners() {
  // Buscador interactivo
  const searchInput = document.getElementById('searchInput');
  const clearBtn = document.getElementById('btnClearSearch');

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const val = e.target.value;
      if (clearBtn) {
        clearBtn.style.display = val ? 'inline-flex' : 'none';
      }
      AppState.searchQuery = val;
      applyFilter();
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSearchSubmit(e);
      }
    });
  }

  // Botón refrescar
  const refreshBtn = document.getElementById('btnRefresh');
  if (refreshBtn) {
    refreshBtn.onclick = () => {
      showToast('Actualizando...', 'info');
      loadDirectory(AppState.currentPath);
      loadServerInfo();
    };
  }

  // Drag and Drop en Dropzone
  const dropZone = document.getElementById('uploadDropZone');
  const fileInput = document.getElementById('hiddenFileInput');

  if (dropZone && fileInput) {
    dropZone.onclick = () => fileInput.click();
    fileInput.onchange = () => handleUploadFiles(fileInput.files);

    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        handleUploadFiles(dt.files);
      }
    });
  }

  // Tecla Enter en modal de carpeta
  const folderInput = document.getElementById('folderNameInput');
  if (folderInput) {
    folderInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitMkdir();
    });
  }

  // Cerrar modales al tocar el fondo oscuro (backdrop)
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        if (backdrop.id === 'fileViewerModal') closeFileViewer();
        else if (backdrop.id === 'uploadModal') closeUploadModal();
        else if (backdrop.id === 'mkdirModal') closeMkdirModal();
        else if (backdrop.id === 'qrModal') closeQrModal();
        else backdrop.classList.remove('open');
      }
    });
  });

  // Cerrar modales con tecla Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeFileViewer();
      closeUploadModal();
      closeMkdirModal();
      closeQrModal();
    }
  });

  // Soporte para botón Atrás del celular y gestos de navegación (Popstate)
  window.addEventListener('popstate', (e) => {
    // Si hay un modal abierto, cerrarlo primero en vez de cambiar de carpeta
    const openModal = document.querySelector('.modal-backdrop.open');
    if (openModal) {
      if (openModal.id === 'fileViewerModal') closeFileViewer();
      else if (openModal.id === 'uploadModal') closeUploadModal();
      else if (openModal.id === 'mkdirModal') closeMkdirModal();
      else if (openModal.id === 'qrModal') closeQrModal();
      else openModal.classList.remove('open');
      return;
    }

    const path = (e.state && e.state.path !== undefined) ? e.state.path : decodePathFromHash();
    loadDirectory(path, false);
  });

  // Tecla Retroceso (Backspace) en teclado para subir de carpeta
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      if (AppState.parentPath !== null && AppState.parentPath !== undefined) {
        e.preventDefault();
        navigateBack();
      }
    }
  });
}

/** Muestra indicador de carga */
function showLoading(isLoading, msg = 'Cargando archivos...') {
  const loader = document.getElementById('loadingIndicator');
  if (loader) {
    loader.style.display = isLoading ? 'block' : 'none';
    const textEl = loader.querySelector('p');
    if (textEl) textEl.textContent = msg;
  }
}

// ==========================================================================
// Menú Contextual Personalizado (Clic Derecho / Pulsación Larga)
// ==========================================================================

function getOrCreateContextMenu() {
  let menu = document.getElementById('customContextMenu');
  if (!menu) {
    menu = document.createElement('div');
    menu.id = 'customContextMenu';
    menu.className = 'custom-context-menu';
    document.body.appendChild(menu);

    // Cerrar al hacer clic fuera o presionar Escape
    document.addEventListener('click', (e) => {
      if (menu.style.display === 'flex' && !menu.contains(e.target)) {
        hideContextMenu();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hideContextMenu();
    });

    // Cerrar al hacer scroll
    window.addEventListener('scroll', () => hideContextMenu(), { passive: true });
  }
  return menu;
}

function hideContextMenu() {
  const menu = document.getElementById('customContextMenu');
  if (menu) menu.style.display = 'none';
}

function showContextMenu(e, item) {
  if (!item) return;
  if (e && e.preventDefault) e.preventDefault();
  const menu = getOrCreateContextMenu();

  const isFolder = item.is_dir;
  const isAudio = item.category === 'audio';

  let itemsHtml = `
    <div class="context-menu-header">${isFolder ? '📁 Carpeta' : '📄 Archivo'}: ${escapeHtml(item.name)}</div>
  `;

  if (isFolder) {
    itemsHtml += `
      <button type="button" class="context-menu-item" data-menu-action="open">
        <span>📂</span>
        <span>Abrir carpeta</span>
      </button>
    `;
  } else {
    if (isAudio) {
      itemsHtml += `
        <button type="button" class="context-menu-item" data-menu-action="play">
          <span>▶</span>
          <span>Reproducir / Escuchar</span>
        </button>
      `;
    } else {
      itemsHtml += `
        <button type="button" class="context-menu-item" data-menu-action="view">
          <span>👁️</span>
          <span>Ver archivo</span>
        </button>
      `;
    }
    itemsHtml += `
      <button type="button" class="context-menu-item" data-menu-action="download">
        <span>⬇</span>
        <span>Descargar</span>
      </button>
      <div class="context-menu-separator"></div>
      <button type="button" class="context-menu-item context-danger" data-menu-action="delete">
        <span>🗑️</span>
        <span>Eliminar archivo</span>
      </button>
    `;
  }

  menu.innerHTML = itemsHtml;

  // Manejar clics de las opciones
  menu.querySelectorAll('[data-menu-action]').forEach(btn => {
    btn.onclick = (ev) => {
      ev.stopPropagation();
      const act = btn.getAttribute('data-menu-action');
      hideContextMenu();
      if (act === 'open') {
        loadDirectory(item.path);
      } else if (act === 'delete') {
        confirmDeleteItem(item);
      } else if (act === 'play') {
        playAudioTrack(item);
      } else if (act === 'view') {
        openFileViewer(item);
      } else if (act === 'download') {
        downloadFile(item.path, item.name);
      }
    };
  });

  menu.style.display = 'flex';

  // Posicionamiento inteligente para evitar salirse de la pantalla
  const menuWidth = 210;
  const menuHeight = isFolder ? 105 : 155;
  let posX = (e.clientX !== undefined) ? e.clientX : 20;
  let posY = (e.clientY !== undefined) ? e.clientY : 20;

  if (posX + menuWidth > window.innerWidth) {
    posX = window.innerWidth - menuWidth - 10;
  }
  if (posY + menuHeight > window.innerHeight) {
    posY = window.innerHeight - menuHeight - 10;
  }
  if (posX < 10) posX = 10;
  if (posY < 10) posY = 10;

  menu.style.left = `${posX}px`;
  menu.style.top = `${posY}px`;
}

// ==========================================================================
// Historial y Recientes (Carpetas y Archivos en localStorage)
// ==========================================================================

const RECENT_FOLDERS_KEY = 'navbyte_recent_folders';
const RECENT_FILES_KEY = 'navbyte_recent_files';
const DRIVES_COLLAPSED_KEY = 'navbyte_drives_collapsed';
const RECENTS_COLLAPSED_KEY = 'navbyte_recents_collapsed';

/** Resuelve el nombre del disco, icono y subruta limpia para cualquier ruta relativa */
function resolveDriveInfo(relPath) {
  if (!relPath) return { driveName: 'Disco Local', driveIcon: '🖥️', subPath: '', isUsb: false };

  const drives = AppState.drives || [];

  // Buscar coincidencia en la lista de drives detectados (ordenados por longitud descendente)
  const sortedDrives = [...drives].sort((a, b) => (b.path || '').length - (a.path || '').length);

  for (const drive of sortedDrives) {
    if (!drive.path) continue;
    if (relPath === drive.path) {
      return {
        driveName: drive.name,
        driveIcon: drive.mount_point === '/' ? '🖥️' : '💾',
        subPath: '',
        isUsb: drive.mount_point.startsWith('/media')
      };
    }
    if (relPath.startsWith(drive.path + '/')) {
      const sub = relPath.substring(drive.path.length + 1);
      return {
        driveName: drive.name,
        driveIcon: drive.mount_point === '/' ? '🖥️' : '💾',
        subPath: sub,
        isUsb: drive.mount_point.startsWith('/media')
      };
    }
  }

  // Fallbacks inteligentes según prefijo (Linux /media/USER/... o /home/USER/... o Windows C:/...)
  const winMatch = relPath.match(/^([a-zA-Z]:)[\\/](.*)$/);
  if (winMatch) {
    const driveLetter = winMatch[1].toUpperCase();
    return {
      driveName: `Disco ${driveLetter}`,
      driveIcon: '🖥️',
      subPath: winMatch[2],
      isUsb: false
    };
  }

  const mediaMatch = relPath.match(/^media\/[^/]+\/([^/]+)(?:\/(.*))?$/);
  if (mediaMatch) {
    const diskName = mediaMatch[1];
    const sub = mediaMatch[2] || '';
    return {
      driveName: diskName,
      driveIcon: '💾',
      subPath: sub,
      isUsb: true
    };
  }

  const homeMatch = relPath.match(/^home\/[^/]+(?:\/(.*))?$/);
  if (homeMatch) {
    const sub = homeMatch[1] || '';
    return {
      driveName: 'Disco Local',
      driveIcon: '🖥️',
      subPath: sub,
      isUsb: false
    };
  }

  return {
    driveName: 'Disco Local',
    driveIcon: '🖥️',
    subPath: relPath,
    isUsb: false
  };
}

/** Verifica si una ruta es la raíz exacta de un disco */
function isDriveRoot(path) {
  if (!path || path === '.' || path === '') return true;
  const drives = AppState.drives || [];
  if (drives.some(d => d.path === path)) return true;
  if (/^[a-zA-Z]:[\\/]?$/.test(path)) return true;
  if (/^home\/[^/]+$/.test(path)) return true;
  if (/^media\/[^/]+\/[^/]+$/.test(path)) return true; // ej: media/usuario/DISK_NAME
  return false;
}

/** Obtiene la categoría de un archivo según su extensión */
function getCategoryFromFilename(filename) {
  if (!filename) return 'other';
  const ext = (filename.split('.').pop() || '').toLowerCase();
  const audioExts = ['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac', 'opus', 'wma', 'aiff'];
  const videoExts = ['mp4', 'mkv', 'webm', 'avi', 'mov', 'wmv'];
  const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'];
  const archiveExts = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2'];
  if (audioExts.includes(ext)) return 'audio';
  if (videoExts.includes(ext)) return 'video';
  if (imageExts.includes(ext)) return 'image';
  if (archiveExts.includes(ext)) return 'archive';
  if (ext === 'pdf') return 'pdf';
  if (ext === 'mid' || ext === 'midi') return 'midi';
  if (['txt', 'md', 'log', 'csv', 'json', 'xml', 'yaml', 'yml', 'py', 'js', 'html', 'css', 'sh', 'sql'].includes(ext)) return 'code';
  return 'document';
}

/** Devuelve un emoji descriptivo según categoría y extensión */
function getIconForCategory(category, extension) {
  const ext = (extension || '').toLowerCase();
  if (category === 'audio') return '🎵';
  if (category === 'midi' || ext === 'mid' || ext === 'midi') return '🎹';
  if (category === 'video') return '🎬';
  if (category === 'image') return '🖼️';
  if (category === 'archive') return '📦';
  if (ext === 'pdf') return '📕';
  if (['txt', 'md', 'doc', 'docx'].includes(ext)) return '📄';
  if (['py', 'js', 'html', 'css', 'json', 'sh', 'sql'].includes(ext)) return '💻';
  return '📄';
}

/** Obtiene el historial reciente guardado en localStorage */
function getStoredRecents() {
  let folders = [];
  let files = [];
  try {
    folders = JSON.parse(localStorage.getItem(RECENT_FOLDERS_KEY) || '[]');
  } catch (e) { folders = []; }
  try {
    files = JSON.parse(localStorage.getItem(RECENT_FILES_KEY) || '[]');
  } catch (e) { files = []; }
  return { folders, files };
}

/** Limpia carpetas consecutivas para mostrar sólo el destino final real */
function sanitizeRecentFolders(list) {
  if (!Array.isArray(list)) return [];
  return list.filter((item, idx) => {
    if (!item || !item.path) return false;
    if (isDriveRoot(item.path)) return false;
    // Si esta carpeta es ancestro de otra en la lista, se descarta (se conserva sólo la más profunda)
    const isAncestorOfAnother = list.some((other, otherIdx) => {
      return otherIdx !== idx && other && other.path && other.path.startsWith(item.path + '/');
    });
    return !isAncestorOfAnother;
  });
}

/** Guarda una carpeta en el historial: sólo la última visitada sin pasos consecutivos (máx. 5) */
function recordRecentFolder(path, name) {
  if (!path || path === '.' || path === '') return;
  if (isDriveRoot(path)) return;

  const { folders } = getStoredRecents();
  const folderName = name || path.split('/').filter(Boolean).pop() || path;
  const driveInfo = resolveDriveInfo(path);

  // Filtrar carpetas que sean ancestros/padres de esta nueva ruta (elimina pasos consecutivos anteriores)
  const filtered = folders.filter(f => {
    if (!f || !f.path) return false;
    if (f.path === path) return false;
    // Si f era un paso intermedio para llegar a esta ruta, se descarta
    if (path.startsWith(f.path + '/')) return false;
    return true;
  });

  const updated = [{
    path,
    name: folderName,
    drive_name: driveInfo.driveName,
    drive_icon: driveInfo.driveIcon,
    is_usb: driveInfo.isUsb,
    visited_at: Date.now()
  }, ...filtered];

  const cleanList = sanitizeRecentFolders(updated).slice(0, 5);

  try {
    localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(cleanList));
  } catch (e) {}
}

/** Guarda un archivo en el historial de usados/vistos/descargados (máx. 10) */
function recordRecentFile(item) {
  if (!item || !item.path) return;
  const { files } = getStoredRecents();
  const driveInfo = resolveDriveInfo(item.path);

  const fileObj = {
    name: item.name,
    path: item.path,
    category: item.category || getCategoryFromFilename(item.name),
    extension: item.extension || (item.name.split('.').pop() || '').toLowerCase(),
    size_formatted: item.size_formatted || '',
    drive_name: driveInfo.driveName,
    drive_icon: driveInfo.driveIcon,
    is_usb: driveInfo.isUsb,
    visited_at: Date.now()
  };

  // Evitar duplicados y mover al inicio
  const filtered = files.filter(f => f.path !== item.path);
  const updated = [fileObj, ...filtered];
  const limited = updated.slice(0, 10);

  try {
    localStorage.setItem(RECENT_FILES_KEY, JSON.stringify(limited));
  } catch (e) {}
}

/** Limpia todo el historial reciente guardado con confirmación previa */
function clearRecentHistory() {
  const confirmed = confirm('¿Estás seguro de que deseas limpiar el historial de carpetas y archivos recientes?');
  if (!confirmed) return;

  try {
    localStorage.removeItem(RECENT_FOLDERS_KEY);
    localStorage.removeItem(RECENT_FILES_KEY);
  } catch (e) {}
  renderRecentsPanel();
  showToast('Historial reciente limpiado', 'info');
}

// ==========================================================================
// Panel Desplegable: Unidades / Particiones del PC
// ==========================================================================

/** Carga las unidades detectadas y renderiza el panel de drives */
async function loadAndRenderDrives() {
  try {
    const res = await fetch('/api/drives');
    if (!res.ok) return;
    const data = await res.json();
    AppState.drives = data.drives || [];
    renderDrivesPanel(AppState.drives);
    renderRecentsPanel(); // Actualiza recientes con los nombres de discos resueltos
  } catch (err) {
    console.warn('No se pudieron cargar unidades:', err);
  }
}

/** Conmuta el acordeón de Unidades del PC y recuerda el estado */
function toggleDrivesAccordion() {
  const panel = document.getElementById('drivesPanel');
  if (!panel) return;
  panel.classList.toggle('collapsed');
  const isCollapsed = panel.classList.contains('collapsed');
  try {
    localStorage.setItem(DRIVES_COLLAPSED_KEY, isCollapsed ? '1' : '0');
  } catch (e) {}
}

/** Muestra el panel de unidades en la raíz como acordeón */
function renderDrivesPanel(drives) {
  let panel = document.getElementById('drivesPanel');
  const explorerContainer = document.getElementById('explorerContainer');

  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'drivesPanel';
    panel.className = 'section-accordion';
    if (explorerContainer && explorerContainer.parentNode) {
      explorerContainer.parentNode.insertBefore(panel, explorerContainer);
    }
  }

  // Restaurar estado guardado de colapso
  const isCollapsed = localStorage.getItem(DRIVES_COLLAPSED_KEY) === '1';
  if (isCollapsed) {
    panel.classList.add('collapsed');
  } else {
    panel.classList.remove('collapsed');
  }
  panel.style.display = 'block';

  panel.innerHTML = `
    <div class="accordion-header" id="drivesAccordionHeader" onclick="toggleDrivesAccordion()" title="Toca para desplegar u ocultar unidades">
      <div class="accordion-title">
        <span>💽</span>
        <span>Unidades y Particiones del PC</span>
        <span class="accordion-badge">${drives.length}</span>
      </div>
      <div class="accordion-controls">
        <span class="accordion-arrow">▼</span>
      </div>
    </div>
    <div class="accordion-content" id="drivesAccordionContent">
      <div id="drivesGrid" style="
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 10px;
        margin-bottom: 8px;
      "></div>
    </div>
  `;

  const grid = panel.querySelector('#drivesGrid');
  drives.forEach(drive => {
    const pct = drive.disk.percent_used || 0;
    const barColor = pct > 90 ? 'var(--accent-rose)' : pct > 70 ? 'var(--accent-amber)' : 'var(--accent-emerald)';

    const card = document.createElement('div');
    card.style.cssText = `
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 14px;
      cursor: pointer;
      transition: var(--transition);
      border-left: 4px solid ${barColor};
    `;

    const icon = drive.mount_point === '/' ? '🖥️' :
                 drive.mount_point.startsWith('/home') ? '🏠' :
                 drive.mount_point.startsWith('/media') ? '💾' : '📀';

    card.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
        <span style="font-size: 1.6rem;">${icon}</span>
        <div style="min-width: 0;">
          <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(drive.name)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(drive.mount_point)}</div>
        </div>
      </div>
      <div style="
        height: 5px;
        background: rgba(255,255,255,0.1);
        border-radius: 99px;
        overflow: hidden;
        margin-bottom: 6px;
      ">
        <div style="height: 100%; width: ${pct}%; background: ${barColor}; border-radius: 99px;"></div>
      </div>
      <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);">
        <span>${pct}% usado</span>
        <span>Libre: <strong style="color: var(--text-secondary);">${drive.disk.free}</strong></span>
      </div>
    `;

    card.onmouseenter = () => card.style.background = 'var(--bg-card-hover)';
    card.onmouseleave = () => card.style.background = 'var(--bg-card)';
    card.onclick = () => loadDirectory(drive.path);

    grid.appendChild(card);
  });
}

/** Oculta el panel de unidades cuando se está dentro de una subcarpeta */
function hideDrivesPanel() {
  const panel = document.getElementById('drivesPanel');
  if (panel) panel.style.display = 'none';
}

// ==========================================================================
// Panel Desplegable: Recientes y Últimos Visitados (5 carpetas, 10 archivos)
// ==========================================================================

/** Conmuta el acordeón de Recientes y recuerda el estado */
function toggleRecentsAccordion() {
  const panel = document.getElementById('recentsPanel');
  if (!panel) return;
  panel.classList.toggle('collapsed');
  const isCollapsed = panel.classList.contains('collapsed');
  try {
    localStorage.setItem(RECENTS_COLLAPSED_KEY, isCollapsed ? '1' : '0');
  } catch (e) {}
}

/** Muestra el panel de recientes en la raíz como acordeón */
function renderRecentsPanel() {
  let panel = document.getElementById('recentsPanel');
  const drivesPanel = document.getElementById('drivesPanel');
  const explorerContainer = document.getElementById('explorerContainer');

  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'recentsPanel';
    panel.className = 'section-accordion';
    if (drivesPanel && drivesPanel.nextSibling) {
      drivesPanel.parentNode.insertBefore(panel, drivesPanel.nextSibling);
    } else if (explorerContainer && explorerContainer.parentNode) {
      explorerContainer.parentNode.insertBefore(panel, explorerContainer);
    }
  }

  const { folders, files } = getStoredRecents();
  // Limpiar carpetas intermedias consecutivas
  const cleanFolders = sanitizeRecentFolders(folders);
  if (cleanFolders.length !== folders.length) {
    try {
      localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(cleanFolders));
    } catch (e) {}
  }

  const totalCount = cleanFolders.length + files.length;

  const isCollapsed = localStorage.getItem(RECENTS_COLLAPSED_KEY) === '1';
  if (isCollapsed) {
    panel.classList.add('collapsed');
  } else {
    panel.classList.remove('collapsed');
  }
  panel.style.display = 'block';

  let contentHtml = '';
  if (totalCount === 0) {
    contentHtml = `
      <div style="text-align: center; padding: 20px 14px; color: var(--text-muted); font-size: 0.85rem; background: var(--bg-card); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle);">
        <div style="font-size: 1.6rem; margin-bottom: 6px;">🕒</div>
        Aún no hay elementos recientes.<br>Al abrir carpetas o reproducir archivos aparecerán aquí automáticamente.
      </div>
    `;
  } else {
    // 1. Carpetas Recientes (hasta 5)
    let foldersHtml = '';
    if (cleanFolders.length > 0) {
      foldersHtml = `
        <div class="recents-subhead">
          <span>📁 Últimas Carpetas Visitadas</span>
          <span style="font-size: 0.72rem; color: var(--accent-emerald); font-weight: normal;">(${cleanFolders.length}/5)</span>
        </div>
        <div class="recent-folders-grid" id="recentFoldersGrid"></div>
      `;
    }

    // 2. Archivos Recientes (hasta 10)
    let filesHtml = '';
    if (files.length > 0) {
      filesHtml = `
        <div class="recents-subhead">
          <span>📄 Últimos Archivos Usados</span>
          <span style="font-size: 0.72rem; color: var(--accent-emerald); font-weight: normal;">(${files.length}/10)</span>
        </div>
        <div class="recent-files-list" id="recentFilesList"></div>
      `;
    }

    contentHtml = foldersHtml + filesHtml;
  }

  panel.innerHTML = `
    <div class="accordion-header" id="recentsAccordionHeader" onclick="toggleRecentsAccordion()" title="Toca para desplegar u ocultar recientes">
      <div class="accordion-title">
        <span>🕒</span>
        <span>Recientes y Últimos Visitados</span>
        <span class="accordion-badge">${totalCount}</span>
      </div>
      <div class="accordion-controls">
        ${totalCount > 0 ? `<button type="button" class="btn-clear-history" onclick="event.stopPropagation(); clearRecentHistory();" title="Limpiar historial de recientes">🗑️ Limpiar</button>` : ''}
        <span class="accordion-arrow">▼</span>
      </div>
    </div>
    <div class="accordion-content" id="recentsAccordionContent">
      ${contentHtml}
    </div>
  `;

  // Poblar carpetas si hay
  const foldersGrid = panel.querySelector('#recentFoldersGrid');
  if (foldersGrid && cleanFolders.length > 0) {
    cleanFolders.forEach(folder => {
      const driveInfo = resolveDriveInfo(folder.path);
      const card = document.createElement('div');
      card.className = 'recent-folder-card';
      card.title = `Abrir carpeta en ${driveInfo.driveName}`;
      card.innerHTML = `
        <span style="font-size: 1.35rem;">📁</span>
        <div style="min-width: 0; flex: 1;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 3px;">
            <span class="recent-drive-badge ${driveInfo.isUsb ? 'is-usb' : 'is-local'}">
              <span>${driveInfo.driveIcon}</span>
              <span>${escapeHtml(driveInfo.driveName)}</span>
            </span>
          </div>
          <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${escapeHtml(folder.name)}
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${escapeHtml(driveInfo.subPath ? driveInfo.subPath : folder.path)}
          </div>
        </div>
        <span style="color: var(--text-muted); font-size: 0.85rem;">›</span>
      `;
      card.onclick = () => loadDirectory(folder.path);
      card.oncontextmenu = (e) => {
        e.preventDefault();
        showContextMenu(e, { name: folder.name, path: folder.path, is_dir: true });
      };
      foldersGrid.appendChild(card);
    });
  }

  // Poblar archivos si hay
  const filesList = panel.querySelector('#recentFilesList');
  if (filesList && files.length > 0) {
    files.forEach(file => {
      const driveInfo = resolveDriveInfo(file.path);
      const itemEl = document.createElement('div');
      itemEl.className = 'recent-file-item';
      const icon = getIconForCategory(file.category, file.extension);
      const isAudio = file.category === 'audio';

      itemEl.innerHTML = `
        <div class="recent-file-info" title="Abrir ${escapeHtml(file.name)}">
          <span style="font-size: 1.25rem;">${icon}</span>
          <div style="min-width: 0; flex: 1;">
            <div class="recent-file-name">${escapeHtml(file.name)}</div>
            <div class="recent-file-meta" style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 2px;">
              <span class="recent-drive-badge ${driveInfo.isUsb ? 'is-usb' : 'is-local'}">
                <span>${driveInfo.driveIcon}</span>
                <span>${escapeHtml(driveInfo.driveName)}</span>
              </span>
              <span>${file.size_formatted ? escapeHtml(file.size_formatted) + ' • ' : ''}${escapeHtml(driveInfo.subPath || file.path)}</span>
            </div>
          </div>
        </div>
        <div class="recent-file-actions">
          ${isAudio ? `
            <button type="button" class="btn-recent-action btn-recent-play" title="Reproducir audio">
              ▶ Escuchar
            </button>
          ` : `
            <button type="button" class="btn-recent-action" title="Ver archivo">
              👁️ Ver
            </button>
          `}
          <button type="button" class="btn-recent-action" title="Descargar archivo">
            ⬇
          </button>
        </div>
      `;

      const infoDiv = itemEl.querySelector('.recent-file-info');
      const actionBtns = itemEl.querySelectorAll('.btn-recent-action');

      if (isAudio) {
        const playBtn = actionBtns[0];
        const dlBtn = actionBtns[1];
        if (playBtn) playBtn.onclick = (e) => { e.stopPropagation(); playAudioTrack(file); };
        if (dlBtn) dlBtn.onclick = (e) => { e.stopPropagation(); downloadFile(file.path, file.name); };
        if (infoDiv) infoDiv.onclick = () => playAudioTrack(file);
      } else {
        const viewBtn = actionBtns[0];
        const dlBtn = actionBtns[1];
        if (viewBtn) viewBtn.onclick = (e) => { e.stopPropagation(); openFileViewer(file); };
        if (dlBtn) dlBtn.onclick = (e) => { e.stopPropagation(); downloadFile(file.path, file.name); };
        if (infoDiv) infoDiv.onclick = () => openFileViewer(file);
      }

      itemEl.oncontextmenu = (e) => {
        e.preventDefault();
        showContextMenu(e, { ...file, is_dir: false });
      };

      filesList.appendChild(itemEl);
    });
  }
}

/** Oculta el panel de recientes */
function hideRecentsPanel() {
  const panel = document.getElementById('recentsPanel');
  if (panel) panel.style.display = 'none';
}

/** Sistema de Notificaciones Toast */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✅' : type === 'error' ? '⚠️' : 'ℹ️'}</span>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toast-out 0.3s forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

/** Escapa caracteres HTML para prevenir XSS */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
