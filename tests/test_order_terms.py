"""Condiciones de la orden (fecha prometida, moneda, IGV) y recepción contra documento (base local)."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from db import local_repository as repo
from modules import ordenes
from utils import clock, money


class MoneyTests(unittest.TestCase):
    def test_default_terms_are_soles_without_igv(self):
        terms = money.normalize_terms(None)
        self.assertEqual(terms, {"expected_date": None, "currency": "PEN", "exchange_rate": 1.0, "tax_rate": 0.0, "prices_include_tax": False, "payment_terms": None})
        self.assertTrue(money.is_default(terms))

    def test_dollars_need_an_exchange_rate_and_soles_ignore_it(self):
        with self.assertRaises(ValueError):
            money.normalize_terms({"currency": "USD"})
        self.assertEqual(money.normalize_terms({"currency": "PEN", "exchange_rate": 9})["exchange_rate"], 1.0)
        self.assertEqual(money.normalize_terms({"currency": "USD", "exchange_rate": 3.8})["exchange_rate"], 3.8)

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValueError):
            money.normalize_terms({"currency": "EUR"})
        with self.assertRaises(ValueError):
            money.normalize_terms({"tax_rate": 1.5})

    def test_amounts(self):
        a = money.amounts(1000, 0.18, 3.8)
        self.assertAlmostEqual(a["tax"], 180.0)
        self.assertAlmostEqual(a["total"], 1180.0)
        self.assertAlmostEqual(a["total_base"], 4484.0)
        self.assertAlmostEqual(a["subtotal_base"], 3800.0)

    def test_format(self):
        self.assertEqual(money.fmt(1234.5, "PEN"), "S/ 1,234.50")
        self.assertEqual(money.fmt(10, "USD"), "US$ 10.00")


class OrderTermsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Aceros del Sur", None, None, None, None)
        self.supplier = repo.list_suppliers().iloc[0]["id"]
        self.items = [{"material_id": self.mat, "material_name": "Concreto normal", "unit": "m³", "quantity": 10.0, "unit_price": 100.0}]

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def _order(self, terms=None):
        code = repo.create_order(self.supplier, "Aceros del Sur", None, None, self.items, terms)
        return repo.list_orders().query("code == @code").iloc[0]

    def test_order_without_terms_behaves_as_before(self):
        order = self._order()
        self.assertEqual(order["currency"], "PEN")
        self.assertAlmostEqual(float(order["subtotal"]), 1000.0)
        self.assertAlmostEqual(float(order["total"]), 1000.0)
        self.assertAlmostEqual(float(order["total_base"]), 1000.0)

    def test_igv_and_dollars_are_calculated_and_converted_to_soles(self):
        order = self._order({"currency": "USD", "exchange_rate": 3.8, "tax_rate": 0.18, "expected_date": date(2030, 1, 15)})
        self.assertEqual(order["currency"], "USD")
        self.assertAlmostEqual(float(order["total"]), 1180.0)
        self.assertAlmostEqual(float(order["subtotal_base"]), 3800.0)
        self.assertAlmostEqual(float(order["total_base"]), 4484.0)
        self.assertEqual(str(order["expected_date"])[:10], "2030-01-15")

    def test_terms_can_be_edited_while_the_order_is_open(self):
        order = self._order()
        repo.update_order(order["id"], None, None, self.items, {"currency": "PEN", "tax_rate": 0.18})
        updated = repo.list_orders().iloc[0]
        self.assertAlmostEqual(float(updated["total"]), 1180.0)
        repo.update_order(order["id"], None, None, self.items)  # sin terms no los toca
        self.assertAlmostEqual(float(repo.list_orders().iloc[0]["total"]), 1180.0)

    def test_late_orders_are_only_open_orders_past_their_promised_date(self):
        past = clock.today() - timedelta(days=5)
        late = self._order({"expected_date": past})
        self._order({"expected_date": clock.today() + timedelta(days=5)})
        self._order()
        done = self._order({"expected_date": past})
        repo.set_order_status(done["id"], "cancelada")
        found = ordenes.late_orders(repo.list_orders())
        self.assertEqual(found["code"].tolist(), [late["code"]])
        self.assertEqual(int(found.iloc[0]["days_late"]), 5)
        self.assertIn(late["id"], ordenes.attention_orders(repo.list_orders())["id"].tolist())

    def test_late_orders_on_empty_table(self):
        self.assertTrue(ordenes.late_orders(pd.DataFrame()).empty)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Aceros del Sur", None, None, None, None)
        supplier = repo.list_suppliers().iloc[0]["id"]
        repo.create_order(supplier, "Aceros del Sur", None, None, [{"material_id": self.mat, "material_name": "Concreto normal", "unit": "m³", "quantity": 10.0, "unit_price": 100.0}])
        self.order_id = repo.list_orders().iloc[0]["id"]
        self.line = repo.list_order_items(self.order_id).iloc[0]["id"]

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_each_reception_keeps_its_document_and_notes(self):
        repo.receive_order_items(self.order_id, {self.line: 4.0}, "admin", {"document_ref": " T001-77 ", "delivered_by": "Luis", "notes": "2 rotas"})
        repo.receive_order_items(self.order_id, {self.line: 6.0}, "admin")
        receipts = repo.list_receipts(self.order_id)
        self.assertEqual(len(receipts), 2)
        newest, oldest = receipts.iloc[0], receipts.iloc[1]
        self.assertEqual(oldest["document_ref"], "T001-77")
        self.assertEqual(oldest["delivered_by"], "Luis")
        self.assertEqual(oldest["notes"], "2 rotas")
        self.assertIsNone(newest["document_ref"])
        self.assertEqual(int(oldest["lines_count"]), 1)

    def test_movement_note_mentions_the_document(self):
        repo.receive_order_items(self.order_id, {self.line: 4.0}, "admin", {"document_ref": "T001-77"})
        move = repo.list_movements(limit=10).iloc[0]
        self.assertIn("T001-77", move["note"])

    def test_failed_reception_leaves_no_receipt(self):
        with self.assertRaises(ValueError):
            repo.receive_order_items(self.order_id, {self.line: 99.0}, "admin", {"document_ref": "X"})
        self.assertTrue(repo.list_receipts(self.order_id).empty)


if __name__ == "__main__":
    unittest.main()
