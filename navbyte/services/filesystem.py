# -*- coding: utf-8 -*-
"""
NavByte - Servicio de Sistema de Archivos
Manejo seguro de rutas, resolución canónica con os.path.realpath,
detección multiplataforma de unidades y listado de directorios.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional

from ..config import EXT_CATEGORIES, SYSTEM_SKIP_DIRS
from ..security import is_protected_system_path


def format_size(bytes_size: int) -> str:
    """Convierte bytes a formato legible (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}" if unit != "B" else f"{bytes_size} B"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def get_file_category(ext: str) -> str:
    """Retorna la categoría del archivo según su extensión."""
    ext = ext.lower()
    for category, extensions in EXT_CATEGORIES.items():
        if ext in extensions:
            return category
    return "other"


def safe_resolve_path(rel_path: str, shared_dir: str) -> Tuple[str, bool]:
    """
    Resuelve de forma segura una ruta relativa dentro de SHARED_DIR.
    Previene:
      1. Path Traversal (../../etc/passwd).
      2. Symlink Traversal (enlaces simbólicos apuntando fuera de la carpeta autorizada) usando realpath.
      3. Acceso a archivos críticos y credenciales del sistema (is_protected_system_path).
    Retorna (ruta_absoluta, es_valida).
    """
    if not rel_path or not rel_path.strip():
        real_shared = os.path.realpath(shared_dir)
        return real_shared, True

    clean_rel = rel_path.strip().strip("/\\")
    if not clean_rel:
        real_shared = os.path.realpath(shared_dir)
        return real_shared, True

    # Soporte para Windows (ej: C:\ o D:\)
    if sys.platform == "win32":
        if len(clean_rel) >= 2 and clean_rel[1] == ":":
            target = os.path.abspath(clean_rel)
            real_target = os.path.realpath(target)
            if is_protected_system_path(real_target):
                return shared_dir, False
            return real_target, True

        if shared_dir in ("/", "\\"):
            system_drive = os.environ.get("SystemDrive", "C:")
            target = os.path.abspath(os.path.join(f"{system_drive}\\", clean_rel))
            real_target = os.path.realpath(target)
            if is_protected_system_path(real_target):
                return shared_dir, False
            return real_target, True

    target = os.path.abspath(os.path.join(shared_dir, clean_rel))
    real_target = os.path.realpath(target)
    real_shared = os.path.realpath(shared_dir)

    # 1. Comprobar que no sea un archivo protegido del sistema (claves SSH, shadow, etc.)
    if is_protected_system_path(real_target):
        return real_shared, False

    # 2. Si la carpeta compartida no es la raíz, validar estrictamente la contención
    if shared_dir != "/" and shared_dir != "\\":
        try:
            common = os.path.commonpath([real_shared, real_target])
            if common != real_shared:
                return real_shared, False
        except ValueError:
            return real_shared, False

    return real_target, True


def detect_system_drives(shared_dir: str = "/") -> List[Dict[str, Any]]:
    r"""
    Detecta y retorna las particiones y unidades montadas reales del sistema.
    Soporta Linux (/proc/mounts) y Windows (letras de unidad C:\, D:\, etc.).
    Filtra montajes virtuales del SO y particiones reservadas.
    """
    drives = []

    # Soporte nativo para Windows
    if sys.platform == "win32":
        import string
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                label = ""
                fs_type = "NTFS"
                try:
                    vol_buf = ctypes.create_unicode_buffer(1024)
                    fs_buf = ctypes.create_unicode_buffer(1024)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        drive_path, vol_buf, len(vol_buf), None, None, None, fs_buf, len(fs_buf)
                    )
                    label = vol_buf.value
                    fs_type = fs_buf.value
                except Exception:
                    pass

                try:
                    total, used, free = shutil.disk_usage(drive_path)
                    disk_info = {
                        "total": format_size(total),
                        "free": format_size(free),
                        "percent_used": round((used / total) * 100, 1) if total else 0,
                    }
                except Exception:
                    disk_info = {"total": "N/A", "free": "N/A", "percent_used": 0}

                name = f"Disco {letter}: ({label})" if label else f"Disco Local ({letter}:)"
                drives.append({
                    "name": name,
                    "mount_point": drive_path,
                    "path": f"{letter}:",
                    "device": f"{letter}:",
                    "fs_type": fs_type,
                    "disk": disk_info,
                })
            bitmask >>= 1
        return drives

    # Soporte para Linux
    VIRTUAL_FS_TYPES = {
        "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup",
        "cgroup2", "pstore", "bpf", "tracefs", "fusectl", "configfs",
        "securityfs", "efivarfs", "mqueue", "hugetlbfs", "ramfs",
        "autofs", "debugfs", "overlay",
    }
    SKIP_MOUNT_PREFIXES = ("/proc", "/sys", "/dev", "/run", "/snap", "/var/lib/docker", "/boot")

    seen_mounts = set()
    home_dir = os.path.expanduser("~")
    home_rel = home_dir.lstrip("/")

    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                device, mount_point, fs_type = parts[0], parts[1], parts[2]
                mount_point = mount_point.replace('\\040', ' ').replace('\\011', '\t')

                if fs_type in VIRTUAL_FS_TYPES:
                    continue

                if any(mount_point.startswith(p) for p in SKIP_MOUNT_PREFIXES):
                    continue

                if mount_point in seen_mounts:
                    continue
                seen_mounts.add(mount_point)

                try:
                    total, used, free = shutil.disk_usage(mount_point)
                    disk_info = {
                        "total": format_size(total),
                        "free": format_size(free),
                        "percent_used": round((used / total) * 100, 1) if total else 0,
                    }
                except Exception:
                    disk_info = {"total": "N/A", "free": "N/A", "percent_used": 0}

                if mount_point == "/":
                    if os.path.isdir(home_dir):
                        display_name = "Disco Local (Archivos Personales)"
                        rel = home_rel
                    else:
                        display_name = "Disco Principal"
                        rel = "home"
                else:
                    display_name = os.path.basename(mount_point) or "Unidad de Almacenamiento"
                    if shared_dir == "/":
                        rel = mount_point.lstrip("/")
                    else:
                        try:
                            rel = os.path.relpath(mount_point, shared_dir)
                        except ValueError:
                            continue

                drives.append({
                    "name": display_name,
                    "mount_point": mount_point,
                    "path": rel,
                    "device": device,
                    "fs_type": fs_type,
                    "disk": disk_info,
                })
    except Exception:
        pass

    def sort_key(d):
        mp = d["mount_point"]
        if mp == "/": return 0
        if mp.startswith("/home"): return 1
        if mp.startswith("/media"): return 2
        return 3

    drives.sort(key=sort_key)
    return drives


def list_directory_entries(abs_path: str, shared_dir: str) -> List[Dict[str, Any]]:
    """
    Lista el contenido de un directorio filtrando archivos ocultos,
    carpetas virtuales del sistema y rutas confidenciales.
    """
    items = []
    with os.scandir(abs_path) as entries:
        for entry in entries:
            name = entry.name
            # Omitir archivos ocultos del sistema
            if name.startswith("."):
                continue

            # Omitir carpetas virtuales del SO
            if entry.is_dir(follow_symlinks=False) and name.lower() in SYSTEM_SKIP_DIRS:
                continue

            try:
                real_entry_path = os.path.realpath(entry.path)
                # Omitir archivos protegidos del sistema
                if is_protected_system_path(real_entry_path):
                    continue

                stat = entry.stat(follow_symlinks=False)
                is_dir = entry.is_dir(follow_symlinks=False)
                size = stat.st_size if not is_dir else 0
                mtime = stat.st_mtime
                mtime_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")

                ext = Path(name).suffix.lower() if not is_dir else ""
                category = "folder" if is_dir else get_file_category(ext)

                item_rel = os.path.relpath(entry.path, shared_dir).replace("\\", "/")

                items.append({
                    "name": name,
                    "path": item_rel,
                    "is_dir": is_dir,
                    "size": size,
                    "size_human": format_size(size) if not is_dir else "--",
                    "mtime": mtime,
                    "mtime_human": mtime_str,
                    "extension": ext[1:] if ext else "",
                    "category": category,
                    "can_stream": category in ("audio", "video"),
                })
            except (OSError, PermissionError):
                continue

    # Ordenar: primero directorios alfabéticamente, luego archivos alfabéticamente
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return items

