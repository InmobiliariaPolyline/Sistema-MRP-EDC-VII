"""Reglas de dinero y stock sobre la base local (SQLite): recepción de órdenes,
despacho a obra, borrado/edición de órdenes, stock mínimo y precios."""
import tempfile
import unittest
from pathlib import Path

from db import local_repository as repo


class StockRulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_path = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "test.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "Volumen (m³)", min_stock=5)
        repo.upsert_material("Acero", "Varilla 3/8", 7850, "Peso (kg)")
        mats = {r["name"]: r["id"] for r in repo.list_materials().to_dict("records")}
        self.concreto, self.varilla = mats["Concreto normal"], mats["Varilla 3/8"]
        repo.upsert_supplier("Aceros del Sur", None, None, None, None)
        self.supplier = repo.list_suppliers().iloc[0]["id"]
        repo.create_project_site("Torre Central", "Lima", None, None)
        self.site = repo.list_project_sites().iloc[0]["id"]

    def tearDown(self):
        repo.DB_PATH = self._old_path
        self.tmp.cleanup()

    def test_min_stock_is_set_from_inventory_and_never_moves_the_stock(self):
        repo.add_movement(self.varilla, "entrada", 40, None, "stock", "admin")
        repo.set_min_stock(self.varilla, 25)
        row = repo.list_materials().set_index("id").loc[self.varilla]
        self.assertEqual(float(row["min_stock"]), 25.0)
        stock = repo.stock_levels().set_index("material_id").loc[self.varilla]
        self.assertEqual(float(stock["stock"]), 40.0)       # el mínimo es solo un aviso: las existencias siguen igual
        # editar la ficha del catálogo conserva el mínimo que ya tenía
        repo.upsert_material("Acero", "Varilla 3/8", 7850, "Peso (kg)", self.varilla, float(row["min_stock"]))
        self.assertEqual(float(repo.list_materials().set_index("id").loc[self.varilla]["min_stock"]), 25.0)

    def _order(self, qty_c=10.0, qty_v=100.0):
        code = repo.create_order(
            self.supplier, "Aceros del Sur", self.site, None,
            [
                {"material_id": self.concreto, "material_name": "Concreto normal", "unit": "m³", "quantity": qty_c, "unit_price": 100.0},
                {"material_id": self.varilla, "material_name": "Varilla 3/8", "unit": "kg", "quantity": qty_v, "unit_price": 5.0},
            ],
        )
        order = repo.list_orders().query("code == @code").iloc[0]
        return order["id"], repo.list_order_items(order["id"])

    def _stock(self, material_id):
        levels = repo.stock_levels().set_index("material_id")
        return float(levels.loc[material_id, "stock"])

    # --- recepción ---
    def test_partial_then_full_reception_updates_stock_and_status(self):
        order_id, items = self._order()
        first = items.iloc[0]
        self.assertEqual(repo.receive_order_items(order_id, {first["id"]: 4.0}, "admin"), "parcial")
        self.assertEqual(self._stock(first["material_id"]), 4.0)
        receipts = {r["id"]: float(r["quantity"]) - float(r["received_qty"]) for r in repo.list_order_items(order_id).to_dict("records")}
        self.assertEqual(repo.receive_order_items(order_id, receipts, "admin"), "recibida")
        self.assertEqual(self._stock(self.concreto), 10.0)
        self.assertEqual(self._stock(self.varilla), 100.0)

    def test_cannot_receive_more_than_ordered_and_nothing_is_saved(self):
        order_id, items = self._order()
        ids = items["id"].tolist()
        with self.assertRaises(ValueError):
            repo.receive_order_items(order_id, {ids[0]: 3.0, ids[1]: 9999.0}, "admin")
        self.assertEqual(self._stock(self.concreto), 0.0)  # la primera línea tampoco se aplicó
        self.assertEqual(float(repo.list_order_items(order_id).iloc[0]["received_qty"]), 0.0)

    def test_cancelled_order_cannot_receive(self):
        order_id, items = self._order()
        repo.set_order_status(order_id, "cancelada")
        with self.assertRaises(ValueError):
            repo.receive_order_items(order_id, {items.iloc[0]["id"]: 1.0})

    # --- borrar / editar órdenes ---
    def test_order_with_received_material_cannot_be_deleted(self):
        order_id, items = self._order()
        repo.receive_order_items(order_id, {items.iloc[0]["id"]: 2.0})
        with self.assertRaises(ValueError):
            repo.delete_order(order_id)
        self.assertEqual(self._stock(self.concreto), 2.0)

    def test_untouched_order_can_be_deleted(self):
        order_id, _ = self._order()
        repo.delete_order(order_id)
        self.assertTrue(repo.list_orders().empty)

    def test_pending_order_can_be_edited_but_not_after_reception(self):
        order_id, items = self._order()
        repo.update_order(
            order_id, None, "Cambio de cantidades",
            [{"material_id": self.concreto, "material_name": "Concreto normal", "unit": "m³", "quantity": 7.0, "unit_price": 90.0}],
        )
        edited = repo.list_order_items(order_id)
        self.assertEqual(len(edited), 1)
        self.assertEqual(float(edited.iloc[0]["quantity"]), 7.0)
        repo.receive_order_items(order_id, {edited.iloc[0]["id"]: 1.0})
        with self.assertRaises(ValueError):
            repo.update_order(order_id, None, None, [{"material_id": self.concreto, "material_name": "x", "quantity": 1, "unit_price": 1}])

    def test_edit_can_add_remove_and_change_quantities_in_one_save(self):
        order_id, items = self._order(qty_c=10.0, qty_v=100.0)
        repo.upsert_material("Madera", "Triplay 18 mm", None, "m²")
        triplay = {r["name"]: r["id"] for r in repo.list_materials().to_dict("records")}["Triplay 18 mm"]
        repo.update_order(
            order_id, self.site, "Reenviar al proveedor",
            [
                {"material_id": self.concreto, "material_name": "Concreto normal", "unit": "m³", "quantity": 12.0, "unit_price": 100.0},  # cantidad cambiada
                {"material_id": triplay, "material_name": "Triplay 18 mm", "unit": "m²", "quantity": 4.0, "unit_price": 40.0},  # agregado
            ],  # la varilla se quitó
        )
        edited = repo.list_order_items(order_id).set_index("material_name")
        self.assertEqual(sorted(edited.index), ["Concreto normal", "Triplay 18 mm"])
        self.assertEqual(float(edited.loc["Concreto normal", "quantity"]), 12.0)
        order = repo.list_orders().iloc[0]
        self.assertEqual(float(order["total"]), 12 * 100 + 4 * 40)
        self.assertEqual(order["notes"], "Reenviar al proveedor")

    # --- despacho ---
    def test_dispatch_creates_voucher_and_reduces_stock(self):
        repo.add_movement(self.concreto, "entrada", 10, None, "ingreso", "admin")
        code = repo.create_dispatch(self.site, None, "Juan Pérez", "Vaciado de losa", [{"material_id": self.concreto, "quantity": 4}], "admin")
        self.assertEqual(code, "VS-0001")
        self.assertEqual(self._stock(self.concreto), 6.0)
        voucher = repo.list_dispatches().iloc[0]
        self.assertEqual(voucher["requested_by"], "Juan Pérez")
        self.assertEqual(len(repo.list_dispatch_lines(voucher["id"])), 1)
        self.assertEqual(repo.create_dispatch(self.site, None, None, None, [{"material_id": self.concreto, "quantity": 1}], "admin"), "VS-0002")

    def test_dispatch_is_all_or_nothing_when_stock_is_short(self):
        repo.add_movement(self.concreto, "entrada", 10, None, None, "admin")
        with self.assertRaises(ValueError):
            repo.create_dispatch(
                self.site, None, None, None,
                [{"material_id": self.concreto, "quantity": 3}, {"material_id": self.varilla, "quantity": 5}], "admin",
            )
        self.assertEqual(self._stock(self.concreto), 10.0)
        self.assertTrue(repo.list_dispatches().empty)

    def test_dispatch_sums_repeated_material_before_checking_stock(self):
        repo.add_movement(self.concreto, "entrada", 5, None, None, "admin")
        with self.assertRaises(ValueError):
            repo.create_dispatch(self.site, None, None, None, [{"material_id": self.concreto, "quantity": 3}, {"material_id": self.concreto, "quantity": 3}], "admin")

    def test_manual_exit_cannot_make_stock_negative(self):
        with self.assertRaises(ValueError):
            repo.add_movement(self.concreto, "salida", 1, None, "merma", "admin")
        with self.assertRaises(ValueError):
            repo.add_movement(self.concreto, "entrada", 0, None, None, "admin")

    # --- stock mínimo y tablero ---
    def test_low_stock_counts_materials_at_or_below_their_minimum(self):
        totals = repo.dashboard_totals()
        self.assertEqual(totals["low_stock"], 1)  # concreto: mínimo 5 y stock 0
        repo.add_movement(self.concreto, "entrada", 20, None, None, "admin")
        totals = repo.dashboard_totals()
        self.assertEqual(totals["low_stock"], 0)
        self.assertEqual(totals["materials_in_stock"], 1)

    def test_stock_levels_do_not_depend_on_movement_limit(self):
        for _ in range(30):
            repo.add_movement(self.varilla, "entrada", 1, None, None, "admin")
        self.assertEqual(self._stock(self.varilla), 30.0)

    # --- precios ---
    def test_price_change_is_recorded_in_history(self):
        repo.set_supplier_material(self.supplier, self.concreto, True, True, 100.0)
        repo.set_supplier_material(self.supplier, self.concreto, True, True, 100.0)  # sin cambio: no suma historial
        repo.set_supplier_material(self.supplier, self.concreto, True, True, 110.0)
        history = repo.list_price_history(material_id=self.concreto)
        self.assertEqual([float(p) for p in history["price"]][::-1], [100.0, 110.0])

    def test_bulk_prices_apply_and_make_available(self):
        applied = repo.bulk_set_supplier_prices(self.supplier, [{"material_id": self.concreto, "price": 95}, {"material_id": self.varilla, "price": 4.5}])
        self.assertEqual(applied, 2)
        offers = repo.list_offers().set_index("material_id")
        self.assertEqual(float(offers.loc[self.concreto, "price"]), 95.0)
        self.assertTrue(bool(offers.loc[self.varilla, "available"]))
        self.assertEqual(len(repo.list_price_history(supplier_id=self.supplier)), 2)


if __name__ == "__main__":
    unittest.main()
