"""Sugerencia de compra e importación de listas de precios (funciones puras)."""
import io
import unittest

import pandas as pd

from modules.sugerencias import best_offers, compute_suggestions
from utils import pricelist


def frame(rows, columns):
    return pd.DataFrame(rows, columns=columns)


LEVEL_COLS = ["material_id", "category", "material_name", "unit", "min_stock", "entradas", "salidas", "stock"]
BUDGET_COLS = ["id", "project_site_id", "material_id", "category", "material_name", "unit", "planned_qty", "planned_unit_price"]
ORDER_COLS = ["id", "status"]
ITEM_COLS = ["order_id", "material_id", "quantity", "received_qty"]
MOVE_COLS = ["material_id", "kind", "quantity", "project_site_id"]
OFFER_COLS = ["supplier_id", "supplier_name", "material_id", "available", "price"]


class SuggestionTests(unittest.TestCase):
    def levels(self, stock=0.0, minimum=0.0):
        return frame([["m1", "Concreto", "Concreto normal", "m³", minimum, stock, 0, stock]], LEVEL_COLS)

    def budget(self, qty=20.0, site="s1"):
        return frame([["b1", site, "m1", "Concreto", "Concreto normal", "m³", qty, 100.0]], BUDGET_COLS)

    def offers(self):
        return frame(
            [["p1", "Caro", "m1", True, 120.0], ["p2", "Barato", "m1", True, 99.0], ["p3", "Baratísimo no disponible", "m1", False, 50.0]],
            OFFER_COLS,
        )

    def test_deficit_is_budget_minus_stock_and_goes_to_cheapest_available_supplier(self):
        out = compute_suggestions(self.budget(20), frame([], ORDER_COLS), frame([], ITEM_COLS), self.levels(stock=5), frame([], MOVE_COLS), self.offers())
        row = out.iloc[0]
        self.assertEqual(row["deficit"], 15.0)
        self.assertEqual(row["supplier_name"], "Barato")  # el más barato entre los disponibles
        self.assertEqual(row["unit_price"], 99.0)

    def test_already_dispatched_material_is_not_demand_again(self):
        moves = frame([["m1", "salida", 8.0, "s1"]], MOVE_COLS)
        out = compute_suggestions(self.budget(20), frame([], ORDER_COLS), frame([], ITEM_COLS), self.levels(stock=0), moves, self.offers())
        self.assertEqual(out.iloc[0]["deficit"], 12.0)

    def test_open_orders_in_transit_cover_the_need(self):
        orders = frame([["o1", "enviada"], ["o2", "cancelada"], ["o3", "recibida"]], ORDER_COLS)
        items = frame([["o1", "m1", 10.0, 4.0], ["o2", "m1", 100.0, 0.0], ["o3", "m1", 100.0, 100.0]], ITEM_COLS)
        out = compute_suggestions(self.budget(20), orders, items, self.levels(stock=0), frame([], MOVE_COLS), self.offers())
        self.assertEqual(out.iloc[0]["incoming"], 6.0)  # solo lo que falta llegar de la orden abierta
        self.assertEqual(out.iloc[0]["deficit"], 14.0)

    def test_nothing_to_buy_when_stock_and_orders_cover_everything(self):
        out = compute_suggestions(self.budget(20), frame([], ORDER_COLS), frame([], ITEM_COLS), self.levels(stock=30), frame([], MOVE_COLS), self.offers())
        self.assertTrue(out.empty)

    def test_minimum_stock_adds_to_the_need_even_without_budget(self):
        out = compute_suggestions(frame([], BUDGET_COLS), frame([], ORDER_COLS), frame([], ITEM_COLS), self.levels(stock=2, minimum=10), frame([], MOVE_COLS), self.offers())
        self.assertEqual(out.iloc[0]["deficit"], 8.0)

    def test_demand_adds_up_across_sites(self):
        budgets = pd.concat([self.budget(10, "s1"), self.budget(15, "s2")], ignore_index=True)
        out = compute_suggestions(budgets, frame([], ORDER_COLS), frame([], ITEM_COLS), self.levels(stock=0), frame([], MOVE_COLS), self.offers())
        self.assertEqual(out.iloc[0]["demand"], 25.0)

    def test_material_without_priced_offer_has_no_supplier(self):
        out = compute_suggestions(self.budget(5), frame([], ORDER_COLS), frame([], ITEM_COLS), self.levels(), frame([], MOVE_COLS), frame([], OFFER_COLS))
        self.assertTrue(out.iloc[0:1]["supplier_id"].isna().all())

    def test_best_offer_falls_back_to_unavailable_when_no_other(self):
        offers = frame([["p3", "Solo no disponible", "m1", False, 50.0]], OFFER_COLS)
        self.assertEqual(best_offers(offers)["m1"]["supplier_name"], "Solo no disponible")


class PriceListTests(unittest.TestCase):
    catalog = pd.DataFrame(
        [
            {"id": "a", "category": "Concreto", "name": "Concreto normal (peso normal)", "metric_label": "m³"},
            {"id": "b", "category": "Acero", "name": "Varilla corrugada 3/8", "metric_label": "kg"},
            {"id": "c", "category": "Madera", "name": "Triplay 18 mm", "metric_label": "m²"},
        ]
    )

    def test_prices_in_several_formats(self):
        self.assertEqual(pricelist.parse_price("S/ 1,250.90"), 1250.9)
        self.assertEqual(pricelist.parse_price("1.250,90"), 1250.9)
        self.assertEqual(pricelist.parse_price("12,50"), 12.5)
        self.assertEqual(pricelist.parse_price(15), 15.0)
        self.assertIsNone(pricelist.parse_price(0))
        self.assertIsNone(pricelist.parse_price("consultar"))

    def test_header_row_is_found_below_a_title(self):
        csv = "Lista de precios Octubre\n\nCódigo;Descripción;Precio unitario\n1;Varilla corrugada 3/8;15,75\n"
        table = pricelist.read_table(csv.encode("utf-8"), "lista.csv")
        self.assertEqual(len(table), 1)

    def test_match_states_and_fuzzy_names(self):
        table = pd.DataFrame(
            {
                "Material": ["varilla corrugada 3/8", "Triplay 18mm", "Concreto normal (peso normal)", "Producto raro", "Varilla corrugada 3/8"],
                "Precio": ["15.75", "40", "99", "10", "abc"],
            }
        )
        result = pricelist.match_rows(table, self.catalog, {"a": 99.0, "b": 14.0})
        states = result["estado"].tolist()
        self.assertEqual(states[0], "cambia")  # 14 -> 15.75
        self.assertEqual(states[1], "nuevo")  # «Triplay 18mm» ~ «Triplay 18 mm»
        self.assertEqual(result.iloc[1]["coincidencia"], "parecida")
        self.assertEqual(states[2], "igual")
        self.assertEqual(states[3], "sin coincidencia")
        self.assertEqual(states[4], "sin precio válido")

    def test_template_round_trip_reads_back_with_the_same_columns(self):
        data = pricelist.template_bytes(self.catalog, {"a": 100.0})
        table = pricelist.read_table(data, "plantilla.xlsx")
        result = pricelist.match_rows(table, self.catalog, {"a": 100.0})
        self.assertEqual(len(result), 3)
        self.assertEqual(result.iloc[0]["estado"], "igual")
        self.assertEqual(result.iloc[1]["estado"], "sin precio válido")  # sin precio en la plantilla


if __name__ == "__main__":
    unittest.main()
