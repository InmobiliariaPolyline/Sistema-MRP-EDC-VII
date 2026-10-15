"""Consumo por obra ya sumado por la base (vista site_consumption) y su equivalencia con el cálculo en Python."""
import tempfile
import unittest
from pathlib import Path

from db import local_repository as repo
from utils import consumption


class SiteConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        for name in ("Cemento", "Arena"):
            repo.upsert_material("Obra", name, None, "unidad")
        self.mats = {r["name"]: r["id"] for r in repo.list_materials().to_dict("records")}
        repo.create_project_site("Torre", None, None, None)
        repo.create_project_site("Puente", None, None, None)
        sites = {r["name"]: r["id"] for r in repo.list_project_sites().to_dict("records")}
        self.torre, self.puente = sites["Torre"], sites["Puente"]
        for material in self.mats.values():
            repo.add_movement(material, "entrada", 500, None, "stock", "a")

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def _busy_history(self):
        cem, are = self.mats["Cemento"], self.mats["Arena"]
        repo.create_dispatch(self.torre, None, "Juan", None, [{"material_id": cem, "quantity": 40}, {"material_id": are, "quantity": 10}], "a", "Cimentación")
        repo.create_dispatch(self.torre, None, "Juan", None, [{"material_id": cem, "quantity": 15}], "a")
        repo.create_dispatch(self.puente, None, "Ana", None, [{"material_id": cem, "quantity": 7}], "a")
        repo.create_return(self.torre, "Juan", None, [{"material_id": cem, "quantity": 5}], "a", "Cimentación")
        repo.add_movement(cem, "salida", 3, None, "merma", "a")                                               # no cuenta
        repo.add_movement(cem, "salida", 2, None, "dev. proveedor", "a", movement_type="devolucion_proveedor")  # no cuenta
        repo.create_inventory_count([{"material_id": cem, "counted_qty": 100}], None, "a")                   # no cuenta

    def test_view_matches_the_python_calculation_for_every_site_and_material(self):
        self._busy_history()
        got = repo.site_consumption()
        by_python = {}
        for move in repo.list_movements(limit=10000).to_dict("records"):
            amount = consumption.site_quantity(move)
            if amount:
                key = (move["project_site_id"], move["material_id"], move.get("stage") or "")
                by_python[key] = by_python.get(key, 0.0) + amount
        by_python = {k: v for k, v in by_python.items() if abs(v) > 1e-12}
        by_view = {(r["project_site_id"], r["material_id"], r["stage"]): float(r["quantity"]) for r in got.to_dict("records")}
        self.assertEqual(by_view, by_python)
        self.assertEqual(by_view[(self.torre, self.mats["Cemento"], "Cimentación")], 35.0)   # 40 despachados − 5 devueltos
        self.assertEqual(by_view[(self.torre, self.mats["Cemento"], "")], 15.0)

    def test_filters_and_columns(self):
        self._busy_history()
        torre = repo.site_consumption(self.torre)
        self.assertEqual(set(torre["project_site_id"]), {self.torre})
        self.assertEqual(list(torre.columns), ["project_site_id", "material_id", "stage", "material_name", "category", "unit", "quantity"])
        one = repo.site_consumption(self.torre, self.mats["Arena"])
        self.assertEqual(one["material_name"].tolist(), ["Arena"])
        self.assertEqual(float(one.iloc[0]["quantity"]), 10.0)
        self.assertTrue(repo.site_consumption("no-existe").empty)

    def test_rows_that_net_to_zero_are_left_out(self):
        cem = self.mats["Cemento"]
        repo.create_dispatch(self.torre, None, "Juan", None, [{"material_id": cem, "quantity": 9}], "a")
        repo.create_return(self.torre, "Juan", None, [{"material_id": cem, "quantity": 9}], "a")
        self.assertTrue(repo.site_consumption(self.torre).empty)

    def test_return_can_name_its_stage_and_reduces_only_that_stage(self):
        cem = self.mats["Cemento"]
        repo.create_dispatch(self.torre, None, "Juan", None, [{"material_id": cem, "quantity": 20}], "a", "Estructura")
        repo.create_return(self.torre, None, None, [{"material_id": cem, "quantity": 4}], "a", "Estructura")
        rows = repo.site_consumption(self.torre)
        self.assertEqual({r["stage"]: float(r["quantity"]) for r in rows.to_dict("records")}, {"Estructura": 16.0})

    def test_no_screen_reads_every_movement_any_more(self):
        import re
        for name in ("obras", "inventario", "sugerencias"):
            source = (Path(__file__).resolve().parent.parent / "modules" / f"{name}.py").read_text(encoding="utf-8")
            hits = re.findall(r"list_movements\([^)]*limit=100000(?![^)]*material_id)", source)
            self.assertEqual(hits, [], name)


if __name__ == "__main__":
    unittest.main()
