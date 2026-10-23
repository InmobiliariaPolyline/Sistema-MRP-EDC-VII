"""Roles admin e invitado: acceso temporal de 24 horas, pantallas permitidas y credenciales que se conservan."""
import sqlite3
import tempfile
from contextlib import closing
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import local_repository as repo
from modules import session
from utils import access

NOW = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)


def guest(until=None):
    return {"role": "invitado", "active": True, "access_until": until}


class AccessRulesTests(unittest.TestCase):
    def test_roles_are_normalized(self):
        self.assertEqual(access.normalize_role("admin"), "admin")
        self.assertEqual(access.normalize_role("operador"), "invitado")
        self.assertEqual(access.normalize_role(None), "invitado")
        self.assertTrue(access.is_admin({"role": "admin"}))
        self.assertFalse(access.is_admin({"role": "operador"}))

    def test_expiry_is_24_hours_from_now(self):
        self.assertEqual(access.new_expiry(NOW), "2026-10-23T15:00:00+00:00")
        self.assertEqual(access.new_expiry(NOW, hours=1), "2026-10-22T16:00:00+00:00")

    def test_guest_enters_only_while_the_access_is_alive(self):
        self.assertTrue(access.allowed(guest("2026-10-23T15:00:00+00:00"), NOW))
        self.assertFalse(access.allowed(guest("2026-10-22T15:00:00+00:00"), NOW))      # justo al vencer
        self.assertFalse(access.allowed(guest("2026-10-21T10:00:00+00:00"), NOW))
        self.assertFalse(access.allowed(guest(None), NOW))                              # sin fecha: hay que reactivarlo
        self.assertFalse(access.allowed({**guest("2026-10-23T15:00:00+00:00"), "active": False}, NOW))
        self.assertFalse(access.allowed(None, NOW))

    def test_admin_never_expires(self):
        self.assertTrue(access.allowed({"role": "admin", "active": True}, NOW))
        self.assertTrue(access.allowed({"role": "admin", "active": True, "access_until": "2000-01-01T00:00:00+00:00"}, NOW))

    def test_stored_formats_are_understood(self):
        self.assertTrue(access.allowed(guest("2026-10-23 15:00:00"), NOW))              # SQLite, sin zona = UTC
        self.assertTrue(access.allowed(guest("2026-10-23T15:00:00Z"), NOW))

    def test_guest_sees_only_consultation_screens(self):
        every = ["Dashboard", "Órdenes de compra", "Proveedores", "Materiales", "Inventario", "Obras", "Trabajadores", "Reportes", "Historial", "Respaldo", "Sistema", "Manual de Usuario"]
        self.assertEqual(access.routes_for({"role": "admin"}, every), every)
        self.assertEqual(access.routes_for({"role": "invitado"}, every), ["Dashboard", "Sistema", "Manual de Usuario"])
        for forbidden in ("Órdenes de compra", "Inventario", "Trabajadores", "Historial", "Respaldo"):
            self.assertNotIn(forbidden, access.GUEST_ROUTES)

    def test_description_tells_what_to_do(self):
        self.assertIn("quedan 24 h 00 min", access.describe(guest("2026-10-23T15:00:00+00:00"), NOW))
        self.assertIn("vencido", access.describe(guest("2026-10-21T10:00:00+00:00"), NOW))
        self.assertIn("reactivarlo", access.describe(guest(None), NOW))
        self.assertIn("sin vencimiento", access.describe({"role": "admin"}, NOW))

    def test_session_state_carries_the_normalized_role(self):
        state = session.user_state({"id": "1", "username": "ana", "name": "Ana", "role": "operador", "access_until": "x"})
        self.assertEqual((state["role"], state["access_until"]), ("invitado", "x"))


class AccessDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def _guest(self, until):
        wid = repo.create_worker("Ana Pérez", None, None, None, None, None)
        repo.grant_worker_access(wid, "ana", "hash", "Ana Pérez", "invitado", until)
        return repo.list_workers().iloc[0].to_dict()

    def test_grant_keeps_credentials_and_the_expiry(self):
        worker = self._guest("2026-10-23T15:00:00+00:00")
        self.assertEqual((worker["username"], worker["role"], worker["access_until"]), ("ana", "invitado", "2026-10-23T15:00:00+00:00"))
        self.assertEqual(repo.get_user_by_username("ana")["password_hash"], "hash")

    def test_suspend_and_reactivate_keep_the_account(self):
        worker = self._guest("2026-10-23T15:00:00+00:00")
        repo.set_user_access(worker["user_id"], None)
        self.assertFalse(access.allowed(repo.get_user_by_username("ana"), NOW))
        self.assertEqual(repo.get_user_by_username("ana")["password_hash"], "hash")
        repo.set_user_access(worker["user_id"], access.new_expiry(NOW))
        self.assertTrue(access.allowed(repo.get_user_by_username("ana"), NOW))

    def test_old_operators_become_guests_without_access(self):
        with closing(sqlite3.connect(repo.DB_PATH)) as conn:
            conn.execute("insert into users (id, username, password_hash, name, role) values ('u1', 'op', 'h', 'Op', 'operador')")
            conn.commit()
        repo._init_db()
        user = repo.get_user_by_username("op")
        self.assertEqual(user["role"], "invitado")
        self.assertFalse(access.allowed(user, NOW))
        repo.set_user_access("u1", access.new_expiry(NOW))
        self.assertTrue(access.allowed(repo.get_user_by_username("op"), NOW))

    def test_new_users_default_to_guest(self):
        repo.create_user("x", "h", "X", "invitado")
        self.assertEqual(repo.get_user_by_username("x")["role"], "invitado")
        self.assertTrue(timedelta(0) < timedelta(hours=access.GUEST_HOURS))


if __name__ == "__main__":
    unittest.main()
