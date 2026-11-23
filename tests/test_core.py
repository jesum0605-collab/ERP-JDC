import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import execute, fetch_one


class ErpCoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp_dir.name) / "test.db")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database,
                "SECRET_KEY": "test-secret-key",
                "TELEMETRY_API_KEY": "test-telemetry-key",
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            admin_role = fetch_one("SELECT id FROM roles WHERE name = 'admin'")
            execute(
                "INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)",
                ("admin@test.local", generate_password_hash("admin-password-123"), "Admin Test"),
            )
            admin_id = fetch_one("SELECT id FROM users WHERE email = 'admin@test.local'")['id']
            execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (admin_id, admin_role['id']))

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf(self, client=None):
        client = client or self.client
        client.get("/login", follow_redirects=True)
        with client.session_transaction() as session:
            return session["csrf_token"]

    def login_admin(self):
        token = self.csrf()
        response = self.client.post(
            "/login",
            data={"email": "admin@test.local", "password": "admin-password-123", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

    def test_login_and_admin_user_management(self):
        self.login_admin()
        self.assertEqual(self.client.get("/admin/usuarios").status_code, 200)

        with self.app.app_context():
            rrhh_role = fetch_one("SELECT id FROM roles WHERE name = 'rrhh'")
        token = self.csrf()
        response = self.client.post(
            "/admin/usuarios/nuevo",
            data={
                "csrf_token": token,
                "full_name": "Usuario RRHH",
                "email": "rrhh@test.local",
                "password": "rrhh-password-123",
                "role_ids": str(rrhh_role["id"]),
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(fetch_one("SELECT id FROM users WHERE email = 'rrhh@test.local'"))

    def test_last_active_admin_cannot_be_removed_or_deactivated(self):
        self.login_admin()
        with self.app.app_context():
            admin_role = fetch_one("SELECT id FROM roles WHERE name = 'admin'")
        token = self.csrf()
        response = self.client.post(
            "/admin/usuarios/1/roles",
            data={"csrf_token": token, "role_ids": ""},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNotNone(
                fetch_one("SELECT 1 FROM user_roles WHERE user_id = 1 AND role_id = ?", (admin_role["id"],))
            )
        token = self.csrf()
        response = self.client.post(
            "/admin/usuarios/1/estado",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(fetch_one("SELECT is_active FROM users WHERE id = 1")["is_active"], 1)

    def test_telemetry_requires_api_key_and_persists_event(self):
        payload = {
            "source_type": "gps_device",
            "device_id": "cuadrilla-test",
            "event_type": "location",
            "occurred_at": "2026-10-22T14:30:00Z",
            "payload": {"latitude": 10.39, "longitude": -75.47},
        }
        self.assertEqual(self.client.post("/api/telemetry", json=payload).status_code, 401)
        response = self.client.post(
            "/api/telemetry",
            json=payload,
            headers={"X-API-Key": "test-telemetry-key"},
        )
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            self.assertIsNotNone(fetch_one("SELECT id FROM telemetry_events WHERE device_id = ?", ("cuadrilla-test",)))

    def test_lookup_and_related_context_cross_records(self):
        self.login_admin()
        with self.app.app_context():
            execute(
                "INSERT INTO employees (identification_number, first_name, last_name, position, status) VALUES (?, ?, ?, ?, 'active')",
                ("EMP-001", "Carlos", "Jardines", "Supervisor",),
            )
            employee_id = fetch_one("SELECT id FROM employees WHERE identification_number='EMP-001'")["id"]
            execute(
                "INSERT INTO projects (code, name, client_name, location, status, project_manager_employee_id) VALUES (?, ?, ?, ?, 'active', ?)",
                ("PR-001", "Parque Costero", "Cliente Costa", "Cartagena", employee_id),
            )
            project_id = fetch_one("SELECT id FROM projects WHERE code='PR-001'")["id"]
        lookup = self.client.get("/api/lookups/projects?q=Parque")
        self.assertEqual(lookup.status_code, 200)
        self.assertEqual(lookup.json["items"][0]["id"], project_id)
        context = self.client.get(f"/api/records/project/{project_id}/context")
        self.assertEqual(context.status_code, 200)
        self.assertEqual(context.json["record"]["manager_name"], "Carlos Jardines")

    def test_universal_delete_is_logical_and_audited(self):
        self.login_admin()
        with self.app.app_context():
            execute(
                "INSERT INTO employees (identification_number, first_name, last_name, status) VALUES (?, ?, ?, 'active')",
                ("TEST-001", "Empleado", "Prueba"),
            )
            employee_id = fetch_one("SELECT id FROM employees WHERE identification_number = 'TEST-001'")["id"]
        token = self.csrf()
        response = self.client.post(
            f"/api/employees/{employee_id}/delete",
            json={"confirm": "1"},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = fetch_one("SELECT deleted_at FROM employees WHERE id = ?", (employee_id,))
            audit = fetch_one(
                "SELECT id FROM audit_log WHERE entity_type = 'employees' AND entity_id = ?",
                (employee_id,),
            )
            self.assertIsNotNone(employee["deleted_at"])
            self.assertIsNotNone(audit)

    def test_backup_command_creates_sqlite_copy(self):
        backup_dir = Path(self.temp_dir.name) / "backups"
        with self.app.app_context():
            result = self.app.test_cli_runner().invoke(
                args=["backup-db", "--destination", str(backup_dir)]
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(len(list(backup_dir.glob("*.db"))), 1)


if __name__ == "__main__":
    unittest.main()
