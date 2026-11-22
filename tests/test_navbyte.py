# -*- coding: utf-8 -*-
"""
Tests unitarios y de seguridad exhaustivos para NavByte.
Verifica autenticación, rate limiting, prevención de path traversal y symlink traversal,
protección CSRF, cabeceras de seguridad y operaciones sobre archivos.
"""

import os
import shutil
import tempfile
import unittest
from navbyte import create_app
from navbyte.security import (
    save_auth_config,
    is_protected_system_path,
    clear_failed_login,
)
from navbyte.services.filesystem import safe_resolve_path


class NavByteSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from navbyte.security import AUTH_CONFIG_FILE, PASSWORD_HASH_FILE
        cls.auth_backup = None
        cls.hash_backup = None
        if os.path.exists(AUTH_CONFIG_FILE):
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                cls.auth_backup = f.read()
        if os.path.exists(PASSWORD_HASH_FILE):
            with open(PASSWORD_HASH_FILE, "r", encoding="utf-8") as f:
                cls.hash_backup = f.read()

    @classmethod
    def tearDownClass(cls):
        from navbyte.security import AUTH_CONFIG_FILE, PASSWORD_HASH_FILE
        if cls.auth_backup is not None:
            with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(cls.auth_backup)
        if cls.hash_backup is not None:
            with open(PASSWORD_HASH_FILE, "w", encoding="utf-8") as f:
                f.write(cls.hash_backup)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        save_auth_config("admin", password_raw="TestClave123!")
        self.app = create_app(shared_dir=self.test_dir, readonly=False, trusted_proxies=False)
        self.client = self.app.test_client()
        clear_failed_login("127.0.0.1")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_security_headers_present(self):
        """Verifica que las cabeceras HTTP de seguridad se agreguen a las respuestas."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_unauthenticated_access_denied(self):
        """Verifica que los endpoints protegidos devuelvan 401 sin sesión activa."""
        res = self.client.get("/api/browse")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertTrue(data.get("auth_required"))

        res = self.client.get("/api/info")
        self.assertEqual(res.status_code, 401)

    def test_rate_limiting_anti_brute_force(self):
        """Verifica el bloqueo tras 5 intentos fallidos de login."""
        clear_failed_login("127.0.0.1")
        for i in range(5):
            res = self.client.post("/api/login", json={"username": "admin", "password": "wrongpassword"})
            if i < 4:
                self.assertEqual(res.status_code, 401)
            else:
                self.assertEqual(res.status_code, 429)
                self.assertTrue(res.get_json().get("blocked"))

        # El intento subsecuente debe ser bloqueado inmediatamente
        res = self.client.post("/api/login", json={"username": "admin", "password": "TestClave123!"})
        self.assertEqual(res.status_code, 429)

        clear_failed_login("127.0.0.1")

    def test_login_success_and_session(self):
        """Verifica inicio de sesión exitoso con credenciales correctas y navegación."""
        clear_failed_login("127.0.0.1")
        res = self.client.post("/api/login", json={"username": "admin", "password": "TestClave123!"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("success"))

        # El acceso a browse ahora debe responder 200
        res = self.client.get("/api/browse")
        self.assertEqual(res.status_code, 200)

    def test_path_traversal_prevention(self):
        """Verifica que safe_resolve_path bloquee escapes de directorio con .."""
        target, is_valid = safe_resolve_path("../../../etc/passwd", self.test_dir)
        self.assertFalse(is_valid)

        # Rutas críticas del sistema siempre protegidas
        self.assertTrue(is_protected_system_path("/home/user/.ssh/id_rsa"))
        self.assertTrue(is_protected_system_path("/etc/shadow"))
        self.assertTrue(is_protected_system_path("/etc/sudoers"))
        self.assertTrue(is_protected_system_path(os.path.join(self.test_dir, ".secret_key")))
        self.assertTrue(is_protected_system_path(os.path.join(self.test_dir, ".auth_credentials.json")))

    def test_symlink_traversal_prevention(self):
        """Verifica que safe_resolve_path bloquee enlaces simbólicos hacia fuera."""
        secret_dir = tempfile.mkdtemp()
        secret_file = os.path.join(secret_dir, "secret.txt")
        with open(secret_file, "w") as f:
            f.write("super_secret")

        try:
            symlink_path = os.path.join(self.test_dir, "leak_link")
            os.symlink(secret_file, symlink_path)

            resolved, is_valid = safe_resolve_path("leak_link", self.test_dir)
            # Debe detectarse que el archivo real está fuera de shared_dir
            self.assertFalse(is_valid)
        except OSError:
            pass  # Si el sistema de archivos no soporta symlinks en pruebas
        finally:
            shutil.rmtree(secret_dir, ignore_errors=True)

    def test_delete_folder_blocked(self):
        """Verifica que no se permita eliminar carpetas enteras."""
        # Loguear cliente
        self.client.post("/api/login", json={"username": "admin", "password": "TestClave123!"})
        sub_dir = os.path.join(self.test_dir, "carpeta_prueba")
        os.makedirs(sub_dir, exist_ok=True)

        res = self.client.post("/api/delete", json={"path": "carpeta_prueba"})
        self.assertEqual(res.status_code, 403)
        self.assertTrue(os.path.exists(sub_dir))

    def test_csrf_origin_check(self):
        """Verifica que peticiones POST con Origin o Referer falso sean bloqueadas."""
        res = self.client.post(
            "/api/login",
            json={"username": "admin", "password": "TestClave123!"},
            headers={"Origin": "https://malicious-website.com"}
        )
        self.assertEqual(res.status_code, 403)

    def test_upload_root_blocked(self):
        """Verifica que no se permita subir directamente a la raíz del sistema."""
        self.client.post("/api/login", json={"username": "admin", "password": "TestClave123!"})
        import io
        data = {
            "path": "",
            "files": (io.BytesIO(b"prueba"), "test.txt")
        }
        res = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("raíz", res.get_json().get("error", ""))

    def test_upload_subfolder_success(self):
        """Verifica que la subida a un subdirectorio válido funcione correctamente."""
        self.client.post("/api/login", json={"username": "admin", "password": "TestClave123!"})
        sub_dir = os.path.join(self.test_dir, "mis_archivos")
        os.makedirs(sub_dir, exist_ok=True)

        import io
        data = {
            "path": "mis_archivos",
            "files": (io.BytesIO(b"contenido de prueba"), "documento.txt")
        }
        res = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("success"))
        self.assertTrue(os.path.exists(os.path.join(sub_dir, "documento.txt")))

    def test_mkdir_root_blocked(self):
        """Verifica que no se permita crear carpetas en la raíz sin entrar a una unidad."""
        self.client.post("/api/login", json={"username": "admin", "password": "TestClave123!"})
        res = self.client.post("/api/mkdir", json={"path": "", "name": "carpeta_raiz"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("raíz", res.get_json().get("error", ""))


if __name__ == "__main__":
    unittest.main()
