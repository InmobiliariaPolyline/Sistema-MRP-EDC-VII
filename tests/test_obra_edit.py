"""Editar una obra: la base conserva sus órdenes y trabajadores, y el cambio se resume para el Historial."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from db import local_repository as repo
from modules import obra_form


class SiteEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.create_project_site("Torre Central", "Lima", -12.05, -77.04)
        repo.create_project_site("Casa Norte", None, None, None)
        self.sites = repo.list_project_sites()
        self.site = self.sites[self.sites["name"] == "Torre Central"].iloc[0].to_dict()

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_update_changes_the_site_and_keeps_its_orders(self):
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Aceros", None, None, None, None)
        sup = repo.list_suppliers().iloc[0]["id"]
        repo.create_order(sup, "Aceros", self.site["id"], None, [{"material_id": mat, "material_name": "Concreto normal", "unit": "m³", "quantity": 1.0, "unit_price": 5.0}])
        repo.update_project_site(self.site["id"], "Torre Sur", "Surco", -12.1, -77.0)
        row = repo.list_project_sites().query("id == @self.site['id']").iloc[0]
        self.assertEqual((row["name"], row["address"], float(row["latitude"])), ("Torre Sur", "Surco", -12.1))
        self.assertEqual(repo.list_orders().iloc[0]["site_name"], "Torre Sur")

    def test_location_can_be_removed(self):
        repo.update_project_site(self.site["id"], "Torre Central", "Lima", None, None)
        row = repo.list_project_sites().query("id == @self.site['id']").iloc[0]
        self.assertTrue(pd.isna(row["latitude"]) or row["latitude"] is None)

    def test_name_taken_ignores_case_spaces_and_itself(self):
        self.assertTrue(obra_form.name_taken("  casa   NORTE ", self.site["id"], self.sites))
        self.assertFalse(obra_form.name_taken("Torre Central", self.site["id"], self.sites))
        self.assertFalse(obra_form.name_taken("Otra", self.site["id"], self.sites))

    def test_changes_only_list_what_changed(self):
        self.assertEqual(obra_form.changes_for(self.site, "Torre Central", "Lima", -12.05, -77.04), [])
        got = obra_form.changes_for(self.site, "Torre Sur", "Lima", None, None)
        self.assertEqual([c["field"] for c in got], ["Nombre", "Ubicación"])
        self.assertIsNone(got[1]["after"])
        self.assertEqual([c["field"] for c in obra_form.changes_for(self.site, "Torre Central", None, -12.05, -77.04)], ["Dirección"])

    def test_coordinate_check(self):
        self.assertTrue(obra_form.has_coordinates(-12.0, -77.0))
        self.assertFalse(obra_form.has_coordinates(None, -77.0))
        self.assertFalse(obra_form.has_coordinates(float("nan"), 1))
        self.assertFalse(obra_form.has_coordinates(100, 0))


if __name__ == "__main__":
    unittest.main()
