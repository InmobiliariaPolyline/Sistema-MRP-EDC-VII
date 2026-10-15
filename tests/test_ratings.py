"""Calificación de proveedores por plazos y cantidades."""
import unittest
from datetime import date

import pandas as pd

from utils import ratings

TODAY = date(2026, 10, 15)


def order(oid, supplier="s1", status="recibida", expected=None, created="2026-09-01", name="Norte"):
    return {"id": oid, "supplier_id": supplier, "supplier_name": name, "status": status, "expected_date": expected, "created_at": created}


def item(oid, qty, received):
    return {"order_id": oid, "quantity": qty, "received_qty": received}


def receipt(oid, when):
    return {"order_id": oid, "received_at": when}


def rate(orders, items=(), receipts=()):
    return ratings.rate_suppliers(pd.DataFrame(orders), pd.DataFrame(list(items)), pd.DataFrame(list(receipts)), today=TODAY)


class RatingsTests(unittest.TestCase):
    def test_no_orders_gives_empty_table(self):
        self.assertTrue(rate([]).empty)

    def test_on_time_and_late_deliveries(self):
        result = rate(
            [order("a", expected="2026-09-10"), order("b", expected="2026-09-10"), order("c", expected="2026-09-10")],
            [item("a", 10, 10), item("b", 10, 10), item("c", 10, 10)],
            [receipt("a", "2026-09-09 10:00:00"), receipt("b", "2026-09-10T08:00:00"), receipt("c", "2026-09-14 09:00:00")],
        ).iloc[0]
        self.assertEqual((int(result["timed"]), int(result["on_time"])), (3, 2))   # el día justo cuenta como a tiempo
        self.assertAlmostEqual(result["on_time_pct"], 200 / 3)
        self.assertEqual(result["avg_delay_days"], 4.0)
        self.assertEqual(result["fill_pct"], 100.0)

    def test_last_receipt_decides_when_the_order_was_completed(self):
        result = rate([order("a", expected="2026-09-10")], [item("a", 10, 10)], [receipt("a", "2026-09-05 10:00:00"), receipt("a", "2026-09-20 10:00:00")]).iloc[0]
        self.assertEqual(int(result["on_time"]), 0)
        self.assertEqual(result["avg_delay_days"], 10.0)

    def test_open_orders_past_their_date_are_late_but_not_yet_due_ones_are_ignored(self):
        result = rate([order("a", status="enviada", expected="2026-10-10"), order("b", status="pendiente", expected="2026-10-30")]).iloc[0]
        self.assertEqual((int(result["orders"]), int(result["timed"]), int(result["on_time"])), (2, 1, 0))
        self.assertEqual(result["avg_delay_days"], 5.0)

    def test_cancelled_orders_and_orders_without_a_date_do_not_affect_timing(self):
        result = rate([order("a", status="cancelada", expected="2026-01-01"), order("b", expected=None)], [item("b", 4, 4)], [receipt("b", "2026-09-02")]).iloc[0]
        self.assertEqual(int(result["orders"]), 1)
        self.assertEqual(int(result["timed"]), 0)
        self.assertIsNone(result["on_time_pct"])
        self.assertEqual(result["score"], 100.0)     # solo hay cantidades completas

    def test_old_partial_orders_lower_the_fill_rate_recent_ones_do_not(self):
        old = rate([order("a", status="parcial", created="2026-08-01")], [item("a", 10, 4)]).iloc[0]
        self.assertEqual(old["fill_pct"], 40.0)
        recent = rate([order("a", status="parcial", created="2026-10-10")], [item("a", 10, 4)]).iloc[0]
        self.assertIsNone(recent["fill_pct"])
        self.assertEqual(recent["label"], "Sin historial")

    def test_score_weights_and_labels(self):
        result = rate(
            [order("a", expected="2026-09-10"), order("b", expected="2026-09-10")],
            [item("a", 10, 10), item("b", 10, 10)],
            [receipt("a", "2026-09-09"), receipt("b", "2026-09-30")],
        ).iloc[0]
        self.assertAlmostEqual(result["score"], 0.6 * 50 + 0.4 * 100)   # 70
        self.assertEqual(result["label"], "Regular")
        self.assertEqual([ratings.label(s) for s in (95, 80, 60, 20, None)], ["Excelente", "Buena", "Regular", "Baja", "Sin historial"])

    def test_ranking_orders_best_first_and_suppliers_are_separate(self):
        result = rate(
            [order("a", "s1", expected="2026-09-10", name="Bueno"), order("b", "s2", expected="2026-09-10", name="Malo")],
            [item("a", 10, 10), item("b", 10, 10)],
            [receipt("a", "2026-09-01"), receipt("b", "2026-10-01")],
        )
        self.assertEqual(result["supplier_name"].tolist(), ["Bueno", "Malo"])


if __name__ == "__main__":
    unittest.main()
