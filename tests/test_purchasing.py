"""Plazos y mínimo de compra del proveedor, completar pedidos y registro del envío (base local)."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from db import local_repository as repo
from modules import sugerencias


class SupplierTermsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        for name, minimum in (("Cemento", 10), ("Arena", 10), ("Clavos", 0), ("Pintura", 5)):
            repo.upsert_material("Obra", name, None, "unidad", min_stock=minimum)
        self.mats = {r["name"]: r["id"] for r in repo.list_materials().to_dict("records")}
        repo.upsert_supplier("Ferretería Norte", None, None, None, None, lead_time_days=5, min_order_amount=500.0)
        repo.upsert_supplier("Sin datos", None, None, None, None)
        self.sup = {r["name"]: r["id"] for r in repo.list_suppliers().to_dict("records")}

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_terms_are_saved_edited_and_cleared(self):
        norte = repo.list_suppliers().set_index("name").loc["Ferretería Norte"]
        self.assertEqual(int(norte["lead_time_days"]), 5)
        self.assertEqual(float(norte["min_order_amount"]), 500.0)
        none = repo.list_suppliers().set_index("name").loc["Sin datos"]
        self.assertIsNone(none["lead_time_days"])
        self.assertIsNone(none["min_order_amount"])
        repo.upsert_supplier("Ferretería Norte", None, None, None, None, self.sup["Ferretería Norte"], None, None)
        cleared = repo.list_suppliers().set_index("name").loc["Ferretería Norte"]
        self.assertIsNone(cleared["lead_time_days"])

    def test_summary_flags_what_is_missing_to_reach_the_minimum_and_the_arrival_date(self):
        chosen = [
            {"supplier_id": self.sup["Ferretería Norte"], "quantity": 10, "unit_price": 20.0},   # 200
            {"supplier_id": self.sup["Ferretería Norte"], "quantity": 5, "unit_price": 20.0},    # +100 = 300
            {"supplier_id": self.sup["Sin datos"], "quantity": 1, "unit_price": 10.0},
        ]
        rows = {r["supplier_name"]: r for r in sugerencias.supplier_summary(chosen, repo.list_suppliers(), today=date(2026, 10, 15))}
        norte = rows["Ferretería Norte"]
        self.assertEqual((norte["lines"], norte["total"], norte["missing"]), (2, 300.0, 200.0))
        self.assertEqual(norte["arrival"], date(2026, 10, 20))
        sin = rows["Sin datos"]
        self.assertEqual((sin["missing"], sin["min_order_amount"], sin["arrival"]), (0.0, None, None))

    def test_summary_reports_no_shortfall_once_the_minimum_is_met(self):
        chosen = [{"supplier_id": self.sup["Ferretería Norte"], "quantity": 30, "unit_price": 20.0}]
        row = sugerencias.supplier_summary(chosen, repo.list_suppliers())[0]
        self.assertEqual(row["missing"], 0.0)

    def _offers(self):
        for name in ("Cemento", "Arena", "Clavos", "Pintura"):
            repo.set_supplier_material(self.sup["Ferretería Norte"], self.mats[name], True, True, 10.0)
        return repo.list_offers()

    def test_top_up_proposes_low_materials_up_to_double_the_minimum(self):
        repo.add_movement(self.mats["Cemento"], "entrada", 12, None, "stock", "a")   # 12 < 20 -> faltan 8
        repo.add_movement(self.mats["Arena"], "entrada", 25, None, "stock", "a")     # 25 >= 20 -> no
        offers, levels = self._offers(), repo.stock_levels()
        found = sugerencias.top_up_candidates(self.sup["Ferretería Norte"], offers, levels, {}, set())
        by_name = found.set_index("material_name")
        self.assertIn("Cemento", by_name.index)
        self.assertNotIn("Arena", by_name.index)     # ya tiene de sobra
        self.assertNotIn("Clavos", by_name.index)    # sin stock mínimo definido
        self.assertEqual(float(by_name.loc["Cemento", "quantity"]), 8.0)
        self.assertEqual(float(by_name.loc["Cemento", "subtotal"]), 80.0)
        self.assertEqual(float(by_name.loc["Pintura", "quantity"]), 10.0)  # mínimo 5, stock 0 -> hasta 10

    def test_top_up_counts_incoming_and_skips_excluded_and_unavailable(self):
        offers, levels = self._offers(), repo.stock_levels()
        offers.loc[offers["material_name"] == "Pintura", "available"] = False
        found = sugerencias.top_up_candidates(self.sup["Ferretería Norte"], offers, levels, {self.mats["Cemento"]: 20.0}, {self.mats["Arena"]})
        self.assertEqual(found["material_name"].tolist(), [])  # Cemento ya viene en camino, Arena excluida, Pintura no disponible

    def test_top_up_on_empty_inputs(self):
        self.assertTrue(sugerencias.top_up_candidates("x", pd.DataFrame(), pd.DataFrame(), {}, set()).empty)

    def test_incoming_by_material_only_counts_open_orders(self):
        items = [{"material_id": self.mats["Cemento"], "material_name": "Cemento", "unit": "u", "quantity": 10.0, "unit_price": 5.0}]
        repo.create_order(self.sup["Ferretería Norte"], "Ferretería Norte", None, None, items)
        repo.create_order(self.sup["Ferretería Norte"], "Ferretería Norte", None, None, items)
        orders = repo.list_orders()
        repo.set_order_status(orders.iloc[0]["id"], "cancelada")
        got = sugerencias.incoming_by_material(repo.list_orders(), repo.list_order_items())
        self.assertEqual(got, {self.mats["Cemento"]: 10.0})

    def test_marking_an_order_as_sent_records_when_and_keeps_the_first_time(self):
        items = [{"material_id": self.mats["Cemento"], "material_name": "Cemento", "unit": "u", "quantity": 1.0, "unit_price": 5.0}]
        repo.create_order(self.sup["Ferretería Norte"], "Ferretería Norte", None, None, items)
        order_id = repo.list_orders().iloc[0]["id"]
        self.assertIsNone(repo.list_orders().iloc[0]["sent_at"])
        repo.set_order_status(order_id, "enviada")
        first = repo.list_orders().iloc[0]["sent_at"]
        self.assertIsNotNone(first)
        repo.set_order_status(order_id, "enviada")
        self.assertEqual(repo.list_orders().iloc[0]["sent_at"], first)
        repo.set_order_status(order_id, "cancelada")  # otros estados no tocan la fecha de envío
        self.assertEqual(repo.list_orders().iloc[0]["sent_at"], first)


if __name__ == "__main__":
    unittest.main()
