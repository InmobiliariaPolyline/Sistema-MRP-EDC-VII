"""Pedido con varios proveedores: mover una línea, cambiar de proveedor sin perder lo agregado y alternativas más baratas."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import streamlit as st

from db import local_repository as repo
from modules import orden_form, ordenes
from utils import reports


def _line(material_id="m1", qty=2.0, price=10.0):
    return {"material_id": material_id, "material_name": "Acero", "category": "Acero", "unit": "kg", "quantity": qty, "unit_price": price}


class CartTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        st.session_state[ordenes.CART_KEY] = {"a": {"name": "A", "lines": [_line(), _line("m2", 1.0, 5.0)], "terms": ordenes._default_terms()}}

    def tearDown(self):
        st.session_state.clear()

    def test_move_creates_the_target_group_with_its_price(self):
        ordenes._move_line("a", "m1", "b", "B", 8.0, "2026-10-01")
        cart = st.session_state[ordenes.CART_KEY]
        self.assertEqual([ln["material_id"] for ln in cart["a"]["lines"]], ["m2"])
        self.assertEqual((cart["b"]["name"], cart["b"]["lines"][0]["unit_price"], cart["b"]["lines"][0]["quantity"]), ("B", 8.0, 2.0))

    def test_move_adds_up_when_the_target_already_has_the_material(self):
        ordenes._move_line("a", "m1", "b", "B", 8.0)
        ordenes._move_line("a", "m2", "b", "B", 4.0)
        ordenes._move_line("b", "m1", "a", "A", 9.0)
        cart = st.session_state[ordenes.CART_KEY]
        self.assertEqual({ln["material_id"]: ln["quantity"] for ln in cart["a"]["lines"]}, {"m1": 2.0})
        self.assertEqual([ln["material_id"] for ln in cart["b"]["lines"]], ["m2"])

    def test_empty_group_disappears(self):
        ordenes._move_line("a", "m1", "b", "B", 8.0)
        ordenes._move_line("a", "m2", "b", "B", 4.0)
        self.assertNotIn("a", st.session_state[ordenes.CART_KEY])

    def test_move_of_a_missing_line_changes_nothing(self):
        ordenes._move_line("a", "zzz", "b", "B", 8.0)
        ordenes._move_line("x", "m1", "b", "B", 8.0)
        self.assertEqual(list(st.session_state[ordenes.CART_KEY]), ["a"])

    def test_jump_keeps_the_cart_and_selects_the_material(self):
        ordenes._jump_to_supplier("B", "Acero · Perfil")
        self.assertEqual((st.session_state["new_order_supplier"], st.session_state["new_order_material"]), ("B", "Acero · Perfil"))
        self.assertEqual(len(st.session_state[ordenes.CART_KEY]["a"]["lines"]), 2)
        ordenes._jump_to_supplier("A")
        self.assertEqual(st.session_state["new_order_material"], "Acero · Perfil")

    def test_clear_draft_removes_the_cart_and_the_form_keys(self):
        st.session_state.update({"new_order_site": "x", "new_order_a_date": 1, "otra": 2})
        ordenes._clear_order_draft()
        self.assertEqual(dict(st.session_state), {"otra": 2})

    def test_alternatives_are_the_other_priced_suppliers_cheapest_first(self):
        offers = pd.DataFrame([
            {"supplier_id": "a", "supplier_name": "A", "material_id": "m1", "price": 10.0},
            {"supplier_id": "b", "supplier_name": "B", "material_id": "m1", "price": 9.0},
            {"supplier_id": "c", "supplier_name": "C", "material_id": "m1", "price": 7.0},
            {"supplier_id": "d", "supplier_name": "D", "material_id": "m1", "price": None},
            {"supplier_id": "e", "supplier_name": "E", "material_id": "m2", "price": 1.0},
        ])
        self.assertEqual([r["supplier_id"] for r in ordenes._alternatives(offers, "m1", "a")], ["c", "b"])
        self.assertEqual(ordenes._alternatives(pd.DataFrame(), "m1", "a"), [])

    def test_group_html_escapes(self):
        self.assertNotIn("<i>", orden_form.group_head_html("<i>x</i>", 2, "S/ 1.00", True))
        self.assertIn("2 proveedores", orden_form.grand_total_html(2, "S/ 5.00"))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Acero", "Perfil", 7850, "unid")
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Uno", None, None, None, None)
        repo.upsert_supplier("Dos", None, None, None, None)
        self.sup = dict(zip(repo.list_suppliers()["name"], repo.list_suppliers()["id"]))
        self.items = [{"material_id": self.mat, "material_name": "Perfil", "unit": "unid", "quantity": 2.0, "unit_price": 10.0}]

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_batch_codes_count_up_and_orders_keep_their_batch(self):
        self.assertEqual(repo.next_batch_code(), "PD-0001")
        a = repo.create_order(self.sup["Uno"], "Uno", None, None, self.items, None, "PD-0001")
        b = repo.create_order(self.sup["Dos"], "Dos", None, None, self.items, None, "PD-0001")
        repo.create_order(self.sup["Uno"], "Uno", None, None, self.items)
        orders = repo.list_orders()
        self.assertEqual(sorted(orders[orders["batch_code"] == "PD-0001"]["code"]), sorted([a, b]))
        self.assertEqual(orders["batch_code"].notna().sum(), 2)
        self.assertEqual(repo.next_batch_code(), "PD-0002")

    def test_batch_pdf_builds(self):
        repo.create_order(self.sup["Uno"], "Uno", None, None, self.items, {"tax_rate": 0.18, "payment_terms": "Contado"}, "PD-0001")
        repo.create_order(self.sup["Dos"], "Dos", None, None, self.items, None, "PD-0001")
        orders = repo.list_orders()
        entries = [{"order": row, "items": repo.list_order_items(row["id"])} for row in orders.to_dict("records")]
        self.assertTrue(reports.batch_pdf("PD-0001", entries, {}).startswith(b"%PDF"))
        total, lines = ordenes._batch_totals(orders.to_dict("records"))
        self.assertAlmostEqual(total, 2 * 20.0 + 3.6)
        self.assertEqual(lines, 2)


class BatchActionTests(unittest.TestCase):
    def _m(self, status, oid="x"):
        return {"id": oid, "code": f"OC-{oid}", "status": status}

    def test_summary_status(self):
        self.assertEqual(ordenes.batch_status([self._m("pendiente"), self._m("pendiente")])[0], "Pendiente")
        self.assertEqual(ordenes.batch_status([self._m("pendiente"), self._m("enviada")])[0], "En curso")
        self.assertEqual(ordenes.batch_status([self._m("recibida"), self._m("cancelada")])[0], "Recibido")
        self.assertEqual(ordenes.batch_status([self._m("cancelada"), self._m("cancelada")])[0], "Cancelada")
        self.assertEqual(ordenes.batch_status([self._m("recibida"), self._m("parcial")])[0], "En curso")

    def test_targets_respect_each_state(self):
        members = [self._m("pendiente", "1"), self._m("enviada", "2"), self._m("parcial", "3"), self._m("recibida", "4"), self._m("cancelada", "5")]
        self.assertEqual([m["id"] for m in ordenes.batch_targets(members, "enviada")], ["1"])
        self.assertEqual([m["id"] for m in ordenes.batch_targets(members, "cancelada")], ["1", "2"])

    def test_can_delete_only_without_received_material(self):
        members = [self._m("pendiente", "1"), self._m("enviada", "2")]
        none = pd.DataFrame({"received_qty": [0, 0]})
        some = pd.DataFrame({"received_qty": [0, 1.5]})
        self.assertTrue(ordenes.batch_can_delete(members, {"1": none, "2": none}))
        self.assertFalse(ordenes.batch_can_delete(members, {"1": none, "2": some}))
        self.assertFalse(ordenes.batch_can_delete([self._m("parcial", "3")], {}))


class BatchStatusDbTests(BatchTests):
    def test_apply_status_changes_only_eligible_orders(self):
        a = repo.create_order(self.sup["Uno"], "Uno", None, None, self.items, None, "PD-0001")
        repo.create_order(self.sup["Dos"], "Dos", None, None, self.items, None, "PD-0001")
        first = repo.list_orders().query("code == @a").iloc[0]["id"]
        repo.set_order_status(first, "enviada")
        members = repo.list_orders().to_dict("records")
        ordenes._apply_batch_status("PD-0001", members, "enviada")      # solo la pendiente cambia
        self.assertEqual(sorted(repo.list_orders()["status"]), ["enviada", "enviada"])
        ordenes._apply_batch_status("PD-0001", repo.list_orders().to_dict("records"), "cancelada")
        self.assertEqual(set(repo.list_orders()["status"]), {"cancelada"})


if __name__ == "__main__":
    unittest.main()
