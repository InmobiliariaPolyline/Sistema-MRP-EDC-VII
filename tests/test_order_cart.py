"""Pedido con varios proveedores: mover una línea, cambiar de proveedor sin perder lo agregado y alternativas más baratas."""
import unittest

import pandas as pd
import streamlit as st

from modules import orden_form, ordenes


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
        self.assertIn("2 órdenes", orden_form.grand_total_html(2, "S/ 5.00"))


if __name__ == "__main__":
    unittest.main()
