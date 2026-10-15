"""Devoluciones de obra al almacén y toma de inventario físico (base local)."""
import tempfile
import unittest
from pathlib import Path

from db import local_repository as repo
from utils import consumption


class ReturnsAndCountsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        repo.upsert_material("Acero", "Varilla 3/8", 7850, "kg")
        mats = {r["name"]: r["id"] for r in repo.list_materials().to_dict("records")}
        self.concreto, self.varilla = mats["Concreto normal"], mats["Varilla 3/8"]
        repo.create_project_site("Torre Central", "Lima", None, None)
        self.site = repo.list_project_sites().iloc[0]["id"]
        repo.add_movement(self.concreto, "entrada", 50, None, "stock inicial", "admin")
        repo.add_movement(self.varilla, "entrada", 20, None, "stock inicial", "admin")
        repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.concreto, "quantity": 10}], "admin")

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def _stock(self, material_id):
        return float(repo.stock_levels().set_index("material_id").loc[material_id, "stock"])

    # --- devoluciones ---
    def test_return_adds_stock_and_reduces_what_the_site_holds(self):
        repo.create_return(self.site, "Juan", "sobró", [{"material_id": self.concreto, "quantity": 4}], "admin")
        self.assertEqual(self._stock(self.concreto), 44.0)  # 50 - 10 + 4
        moves = repo.list_movements(project_site_id=self.site, limit=100)
        self.assertEqual(consumption.net_by_material(moves)[self.concreto], 6.0)
        types = set(moves["movement_type"])
        self.assertIn("devolucion", types)

    def test_cannot_return_more_than_the_site_holds(self):
        with self.assertRaises(ValueError):
            repo.create_return(self.site, None, None, [{"material_id": self.concreto, "quantity": 11}], "admin")
        repo.create_return(self.site, None, None, [{"material_id": self.concreto, "quantity": 10}], "admin")
        with self.assertRaises(ValueError):  # ya devolvió todo
            repo.create_return(self.site, None, None, [{"material_id": self.concreto, "quantity": 1}], "admin")
        self.assertEqual(self._stock(self.concreto), 50.0)

    def test_cannot_return_a_material_the_site_never_received(self):
        with self.assertRaises(ValueError):
            repo.create_return(self.site, None, None, [{"material_id": self.varilla, "quantity": 1}], "admin")

    def test_return_is_all_or_nothing(self):
        with self.assertRaises(ValueError):
            repo.create_return(
                self.site, None, None,
                [{"material_id": self.concreto, "quantity": 2}, {"material_id": self.varilla, "quantity": 1}], "admin",
            )
        self.assertEqual(self._stock(self.concreto), 40.0)  # la primera línea tampoco se aplicó

    def test_supplier_return_is_not_counted_as_site_consumption(self):
        repo.add_movement(self.varilla, "salida", 5, None, "defectuosa", "admin", movement_type="devolucion_proveedor")
        self.assertEqual(self._stock(self.varilla), 15.0)
        self.assertEqual(consumption.net_by_material(repo.list_movements(limit=100)).get(self.varilla, 0.0), 0.0)

    # --- toma de inventario ---
    def test_count_adjusts_both_ways_and_records_every_line(self):
        code = repo.create_inventory_count(
            [
                {"material_id": self.concreto, "counted_qty": 38, "reason": "rotura de bolsas"},  # sistema 40 -> falta 2
                {"material_id": self.varilla, "counted_qty": 23, "reason": ""},                  # sistema 20 -> sobra 3
            ],
            "conteo mensual", "admin",
        )
        self.assertEqual(code, "CT-0001")
        self.assertEqual(self._stock(self.concreto), 38.0)
        self.assertEqual(self._stock(self.varilla), 23.0)
        counts = repo.list_inventory_counts()
        self.assertEqual(int(counts.iloc[0]["lines_count"]), 2)
        self.assertEqual(int(counts.iloc[0]["adjusted_count"]), 2)
        lines = repo.list_count_lines(counts.iloc[0]["id"]).set_index("material_name")
        self.assertEqual(float(lines.loc["Concreto normal", "difference"]), -2.0)
        self.assertEqual(lines.loc["Concreto normal", "reason"], "rotura de bolsas")
        moves = repo.list_movements(limit=100)
        adjust = moves[moves["movement_type"] == "conteo"]
        self.assertEqual(len(adjust), 2)
        self.assertTrue((adjust["count_code"] == "CT-0001").all())

    def test_count_without_difference_creates_no_movements(self):
        repo.create_inventory_count([{"material_id": self.concreto, "counted_qty": 40}], None, "admin")
        self.assertEqual(len(repo.list_movements(limit=100).query("movement_type == 'conteo'")), 0)
        self.assertEqual(int(repo.list_inventory_counts().iloc[0]["adjusted_count"]), 0)

    def test_count_codes_increase_and_negative_counts_are_rejected(self):
        repo.create_inventory_count([{"material_id": self.concreto, "counted_qty": 40}], None, "admin")
        self.assertEqual(repo.create_inventory_count([{"material_id": self.concreto, "counted_qty": 41}], None, "admin"), "CT-0002")
        with self.assertRaises(ValueError):
            repo.create_inventory_count([{"material_id": self.concreto, "counted_qty": -1}], None, "admin")
        self.assertEqual(self._stock(self.concreto), 41.0)

    def test_count_to_zero_is_allowed(self):
        repo.create_inventory_count([{"material_id": self.varilla, "counted_qty": 0, "reason": "se acabó"}], None, "admin")
        self.assertEqual(self._stock(self.varilla), 0.0)


class ConsumptionTests(unittest.TestCase):
    def test_only_site_dispatches_and_returns_count(self):
        rows = [
            {"material_id": "a", "project_site_id": "s", "kind": "salida", "quantity": 10, "movement_type": "despacho"},
            {"material_id": "a", "project_site_id": "s", "kind": "entrada", "quantity": 3, "movement_type": "devolucion"},
            {"material_id": "a", "project_site_id": "s", "kind": "entrada", "quantity": 99, "movement_type": "recepcion"},
            {"material_id": "a", "project_site_id": None, "kind": "salida", "quantity": 50, "movement_type": "merma"},
            {"material_id": "b", "project_site_id": "s", "kind": "salida", "quantity": 2},  # movimientos viejos sin tipo
        ]
        self.assertEqual(consumption.net_by_material(rows), {"a": 7.0, "b": 2.0})


if __name__ == "__main__":
    unittest.main()
