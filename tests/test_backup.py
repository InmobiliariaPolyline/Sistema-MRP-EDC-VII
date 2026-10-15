"""Respaldo (ZIP, cifrado opcional) y lectura para restaurar."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from db import local_repository as repo
from utils import backup


class BackupTests(unittest.TestCase):
    tables = {
        "materials": pd.DataFrame([{"id": "m1", "name": "Concreto, f'c=210", "density": 2400.0}, {"id": "m2", "name": "Acero", "density": None}]),
        "suppliers": pd.DataFrame([{"id": "s1", "name": "Ferretería Ñandú", "phone": None}]),
    }

    def test_plain_zip_has_one_csv_per_table_and_a_manifest(self):
        data = backup.to_zip(self.tables, None, "parche test")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(sorted(z.namelist()), ["manifest.json", "materials.csv", "suppliers.csv"])
            manifest = json.loads(z.read("manifest.json"))
        self.assertEqual(manifest["tables"], {"materials": 2, "suppliers": 1})
        self.assertFalse(manifest["encrypted"])
        self.assertEqual(manifest["app_version"], "parche test")

    def test_round_trip_keeps_text_accents_commas_and_empty_values(self):
        manifest, rows = backup.rows_from_zip(backup.to_zip(self.tables))
        self.assertEqual(rows["materials"][0]["name"], "Concreto, f'c=210")
        self.assertEqual(rows["suppliers"][0]["name"], "Ferretería Ñandú")
        self.assertIsNone(rows["suppliers"][0]["phone"])      # vacío -> None
        self.assertIsNone(rows["materials"][1]["density"])
        self.assertEqual(rows["materials"][0]["density"], "2400.0")  # lo demás va como texto

    def test_empty_tables_are_backed_up_and_read_back_as_no_rows(self):
        """Una tabla sin filas (muy común al empezar) no debe romper la lectura del respaldo."""
        tables = {"materials": self.tables["materials"], "attendance": pd.DataFrame(), "audit_log": pd.DataFrame(columns=["id", "summary"])}
        for password in (None, "Clave-segura-1"):
            manifest, rows = backup.rows_from_zip(backup.to_zip(tables, password), password)
            self.assertEqual(rows["attendance"], [])
            self.assertEqual(rows["audit_log"], [])
            self.assertEqual(len(rows["materials"]), 2)
            self.assertEqual(manifest["tables"]["attendance"], 0)

    def test_encrypted_zip_needs_the_password(self):
        data = backup.to_zip(self.tables, "Clave-segura-1")
        with self.assertRaises(Exception):
            backup.rows_from_zip(data, "otra-clave")
        with self.assertRaises(Exception):
            backup.rows_from_zip(data, None)
        manifest, rows = backup.rows_from_zip(data, "Clave-segura-1")
        self.assertTrue(manifest["encrypted"])
        self.assertEqual(len(rows["materials"]), 2)

    def test_encrypted_zip_does_not_contain_readable_data(self):
        data = backup.to_zip(self.tables, "Clave-segura-1")
        self.assertNotIn(b"Concreto", data)
        self.assertNotIn("Ferretería".encode("utf-8"), data)


class DumpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_dump_includes_every_app_table_in_dependency_order(self):
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        repo.upsert_supplier("Aceros del Sur", None, None, None, None)
        dump = repo.dump_tables()
        self.assertEqual(list(dump), [t for t in repo.BACKUP_TABLES if t in dump])
        self.assertEqual(len(dump["materials"]), 1)
        self.assertEqual(len(dump["suppliers"]), 1)
        self.assertIn("purchase_orders", dump)
        self.assertIn("dispatch_vouchers", dump)

    def test_full_cycle_dump_zip_read(self):
        repo.upsert_material("Acero", "Varilla 3/8", 7850, "kg", min_stock=5)
        manifest, rows = backup.rows_from_zip(backup.to_zip(repo.dump_tables(), "Clave-segura-1"), "Clave-segura-1")
        self.assertEqual(rows["materials"][0]["name"], "Varilla 3/8")
        self.assertEqual(rows["materials"][0]["min_stock"], "5.0")


if __name__ == "__main__":
    unittest.main()
