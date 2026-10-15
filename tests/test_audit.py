"""Historial de cambios con valor anterior y nuevo."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from db import local_repository as repo
from utils import audit

LABELS = {"name": "Nombre", "price": "Precio", "available": "Disponible", "when": "Fecha"}


class DiffTests(unittest.TestCase):
    def test_only_real_changes_are_reported_with_readable_values(self):
        changes = audit.diff(
            {"name": "Cemento", "price": 10, "available": False, "when": None},
            {"name": "Cemento", "price": 12.5, "available": True, "when": date(2026, 10, 20)},
            LABELS,
        )
        self.assertEqual(
            changes,
            [
                {"field": "Precio", "before": "10", "after": "12.5"},
                {"field": "Disponible", "before": "No", "after": "Sí"},
                {"field": "Fecha", "before": None, "after": "2026-10-20"},
            ],
        )

    def test_equal_numbers_in_different_types_and_empty_values_are_not_changes(self):
        self.assertEqual(audit.diff({"price": 10}, {"price": 10.0}, LABELS), [])
        self.assertEqual(audit.diff({"price": "10"}, {"price": 10.0}, LABELS), [])
        self.assertEqual(audit.diff({"name": None}, {"name": "  "}, LABELS), [])
        self.assertEqual(audit.diff({"name": float("nan")}, {"name": None}, LABELS), [])
        self.assertEqual(audit.diff({}, {}, LABELS), [])

    def test_only_listed_fields_are_compared(self):
        self.assertEqual(audit.diff({"name": "a", "extra": 1}, {"name": "a", "extra": 2}, LABELS), [])

    def test_line_changes_quantity_added_and_removed(self):
        before = [{"material_name": "Cemento", "quantity": 10}, {"material_name": "Arena", "quantity": 5}, {"material_name": "Grava", "quantity": 2}]
        after = [{"material_name": "Cemento", "quantity": 12}, {"material_name": "Arena", "quantity": 5.0}, {"material_name": "Ladrillo", "quantity": 100}]
        self.assertEqual(
            audit.diff_lines(before, after),
            [
                {"field": "Cemento (cantidad)", "before": "10", "after": "12"},
                {"field": "Grava (línea quitada)", "before": "2", "after": None},
                {"field": "Ladrillo (línea nueva)", "before": None, "after": "100"},
            ],
        )

    def test_description_is_short_and_marks_empty_values(self):
        changes = [{"field": f"Campo {i}", "before": None if i == 0 else str(i), "after": str(i + 1)} for i in range(8)]
        text = audit.describe(changes)
        self.assertTrue(text.startswith("Campo 0: — → 1; Campo 1: 1 → 2"))
        self.assertTrue(text.endswith("y 2 más"))

    def test_json_round_trip_tolerates_empty_and_broken_values(self):
        changes = [{"field": "Ñandú", "before": "a", "after": None}]
        self.assertEqual(audit.from_json(audit.to_json(changes)), changes)
        self.assertEqual(audit.from_json(changes), changes)
        for value in (None, "", "no es json", float("nan"), '{"no": "lista"}'):
            self.assertEqual(audit.from_json(value), [])
        self.assertIsNone(audit.to_json([]))


class AuditLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_changes_are_stored_and_read_back_as_a_list(self):
        changes = [{"field": "Precio", "before": "10", "after": "12"}]
        repo.log_action("admin", "Catálogo editado (Precio: 10 → 12)", "catalogo", "s1:m1", changes)
        repo.log_action("admin", "Orden creada")
        log = repo.list_audit().set_index("summary")
        self.assertEqual(log.loc["Catálogo editado (Precio: 10 → 12)", "changes"], changes)
        self.assertEqual(log.loc["Catálogo editado (Precio: 10 → 12)", "entity_type"], "catalogo")
        self.assertEqual(log.loc["Orden creada", "changes"], [])
        self.assertIsNone(log.loc["Orden creada", "entity_id"])

    def test_old_local_database_gets_the_new_columns(self):
        import sqlite3

        old = Path(self.tmp.name) / "old.db"
        conn = sqlite3.connect(old)
        conn.executescript("create table audit_log (id text primary key, actor text not null, summary text not null, created_at text default (datetime('now')));"
                           "insert into audit_log (id, actor, summary) values ('1', 'a', 'viejo');")
        conn.commit()
        conn.close()
        repo.DB_PATH = old
        repo._init_db()
        log = repo.list_audit()
        self.assertEqual(log.iloc[0]["summary"], "viejo")
        self.assertEqual(log.iloc[0]["changes"], [])

    def test_the_backup_keeps_the_changes_as_valid_json(self):
        import json

        from utils import backup

        repo.log_action("admin", "x", "orden", "o1", [{"field": "Estado", "before": "Pendiente", "after": "Enviada"}])
        manifest, rows = backup.rows_from_zip(backup.to_zip(repo.dump_tables(), "Clave-1"), "Clave-1")
        stored = rows["audit_log"][0]["changes"]
        self.assertEqual(json.loads(stored), [{"field": "Estado", "before": "Pendiente", "after": "Enviada"}])


if __name__ == "__main__":
    unittest.main()
