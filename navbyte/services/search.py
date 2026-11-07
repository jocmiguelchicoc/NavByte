# -*- coding: utf-8 -*-
"""
NavByte - Servicio de Búsqueda de Archivos
Búsqueda recursiva con límites de tiempo (timeout), límites de resultados,
exclusión de carpetas virtuales y protección de archivos confidenciales.
"""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from ..config import SYSTEM_SKIP_DIRS
from ..security import is_protected_system_path
from .filesystem import get_file_category, format_size, detect_system_drives

SKIP_FOLDERS = {
    "$recycle.bin", "system volume information", "found.000", "found.001",
    ".git", ".cache", "node_modules", "__pycache__", ".vscode", ".idea",
    "proc", "sys", "dev", "run", "snap", "boot", "lost+found",
}


def search_files(
    abs_path: str,
    rel_path: str,
    query: str,
    shared_dir: str,
    max_results: int = 80,
    max_seconds: float = 5.0
) -> Dict[str, Any]:
    """
    Busca recursivamente archivos y carpetas que coincidan con 'query'.
    Protege contra cuelgues limitando el tiempo máximo de búsqueda y excluyendo
    directorios virtuales y archivos protegidos del sistema.
    """
    start_time = time.time()
    results: List[Dict[str, Any]] = []

    if not query:
        return {"results": [], "query": "", "total": 0, "limit_reached": False, "elapsed_seconds": 0}

    query = query.lower()
    max_results = min(max_results, 200)

    try:
        search_roots = []
        if not rel_path or rel_path in (".", "/"):
            drives = detect_system_drives(shared_dir)
            search_roots = [d["mount_point"] for d in drives if d["mount_point"] != "/"]
            if not search_roots:
                search_roots = [shared_dir]
        else:
            search_roots = [abs_path]

        for s_root in search_roots:
            if len(results) >= max_results or (time.time() - start_time) > max_seconds:
                break

            for root, dirs, files in os.walk(s_root, topdown=True):
                root_lower = root.lower()

                # Evitar carpetas del sistema y de exclusión
                if any(sf in root_lower for sf in SKIP_FOLDERS) or any(f"/{sd}" in root_lower for sd in SYSTEM_SKIP_DIRS):
                    dirs[:] = []
                    continue

                # Filtrar subdirectorios in-place
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d.lower() not in SKIP_FOLDERS
                    and d.lower() not in SYSTEM_SKIP_DIRS
                ]

                # 1. Comprobar si directorios coinciden
                for d in dirs:
                    if query in d.lower():
                        full_dir_path = os.path.join(root, d)
                        real_dir_path = os.path.realpath(full_dir_path)
                        if is_protected_system_path(real_dir_path):
                            continue

                        try:
                            stat = os.stat(full_dir_path)
                            item_rel = os.path.relpath(full_dir_path, shared_dir).replace("\\", "/")
                            parent_rel = os.path.relpath(root, shared_dir).replace("\\", "/")
                            if parent_rel == ".":
                                parent_rel = ""

                            results.append({
                                "name": d,
                                "path": item_rel,
                                "parent_path": parent_rel,
                                "is_dir": True,
                                "size": 0,
                                "size_human": "Carpeta",
                                "mtime": stat.st_mtime,
                                "mtime_human": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                                "extension": "",
                                "category": "folder",
                                "can_stream": False,
                            })
                            if len(results) >= max_results:
                                break
                        except (OSError, PermissionError):
                            continue

                if len(results) >= max_results or (time.time() - start_time) > max_seconds:
                    break

                # 2. Comprobar archivos coincidentes
                for f in files:
                    if f.startswith("."):
                        continue
                    if query in f.lower():
                        full_file_path = os.path.join(root, f)
                        real_file_path = os.path.realpath(full_file_path)
                        if is_protected_system_path(real_file_path):
                            continue

                        try:
                            stat = os.stat(full_file_path)
                            size = stat.st_size
                            ext = Path(f).suffix.lower()
                            category = get_file_category(ext)
                            item_rel = os.path.relpath(full_file_path, shared_dir).replace("\\", "/")
                            parent_rel = os.path.relpath(root, shared_dir).replace("\\", "/")
                            if parent_rel == ".":
                                parent_rel = ""

                            results.append({
                                "name": f,
                                "path": item_rel,
                                "parent_path": parent_rel,
                                "is_dir": False,
                                "size": size,
                                "size_human": format_size(size),
                                "mtime": stat.st_mtime,
                                "mtime_human": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                                "extension": ext[1:] if ext else "",
                                "category": category,
                                "can_stream": category in ("audio", "video"),
                            })
                            if len(results) >= max_results:
                                break
                        except (OSError, PermissionError):
                            continue

                if len(results) >= max_results or (time.time() - start_time) > max_seconds:
                    break

    except Exception:
        pass

    results.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    return {
        "query": query,
        "base_path": rel_path,
        "results": results,
        "total": len(results),
        "limit_reached": len(results) >= max_results,
        "elapsed_seconds": round(time.time() - start_time, 2),
    }

