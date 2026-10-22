"""Planes de pago en cuotas: texto, cronograma, unidad principal, tarjetas del formulario y PDF por pago."""
import unittest
from datetime import date

import pandas as pd

from modules import orden_form
from utils import money, reports, units

TERMS = "En 3 cuotas mensuales · 1.ª a los 30 días · inicial 20 %"
ORDER = {
    "code": "OC-9", "created_at": "2026-10-21T10:00:00", "supplier_name": "Sodimac <X>", "currency": "PEN", "tax_rate": 0.18,
    "prices_include_tax": False, "exchange_rate": 1, "status": "pendiente", "payment_terms": TERMS, "site_name": "Obra",
}
ITEMS = pd.DataFrame([{"material_name": "Acero", "unit": "kg", "quantity": 10, "unit_price": 100.0, "received_qty": 0}])


class PlanTextTests(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(money.parse_plan(TERMS), {"count": 3, "every": "mensuales", "first_days": 30, "initial_pct": 20})
        self.assertEqual(money.installment_terms(3, "mensuales", 30, 20), TERMS)
        self.assertEqual(money.installment_terms(2, "semanales", 0, 0), "En 2 cuotas semanales")

    def test_invalid_plans(self):
        for bad in ("Contado", "Crédito 30 días", "En 1 cuotas mensuales", "En 3 cuotas anuales", None):
            self.assertIsNone(money.parse_plan(bad))
        with self.assertRaises(ValueError):
            money.installment_terms(1)

    def test_schedule_adds_up(self):
        schedule = money.payment_schedule("2026-10-21", 1000.01, TERMS)
        self.assertEqual([p["label"] for p in schedule], ["Inicial (20 %)", "Cuota 1", "Cuota 2", "Cuota 3"])
        self.assertAlmostEqual(sum(p["amount"] for p in schedule), 1000.01, places=2)
        self.assertEqual(schedule[0]["due"], date(2026, 10, 21))
        self.assertEqual(schedule[1]["due"], date(2026, 11, 20))
        self.assertEqual(money.due_date("2026-10-21", TERMS), schedule[-1]["due"])

    def test_single_payment_forms(self):
        self.assertEqual(len(money.payment_schedule("2026-10-21", 500, "Contado")), 1)
        credit = money.payment_schedule("2026-10-21", 500, "Crédito 30 días")
        self.assertEqual(credit[0]["due"], date(2026, 11, 20))
        self.assertEqual(money.payment_schedule("2026-10-21", 500, "No indicada"), [])

    def test_month_end(self):
        schedule = money.payment_schedule("2026-01-31", 300, "En 3 cuotas mensuales · 1.ª a los 0 días")
        self.assertEqual([p["due"] for p in schedule], [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)])


class UnitsAndHtmlTests(unittest.TestCase):
    def test_primary_unit(self):
        self.assertEqual(units.primary("Peso (kg) / Longitud (m)"), "kg")
        self.assertEqual(units.primary("unidad"), "unid.")
        self.assertEqual(units.primary(None), "unid.")

    def test_line_card_escapes(self):
        line = {"material_name": "<b>x</b>", "category": "A&B", "unit": "kg", "quantity": 2, "unit_price": 10.0}
        html = orden_form.line_card_html(0, line, "PEN")
        self.assertNotIn("<b>x</b>", html)
        self.assertNotIn("\n\n", html)

    def test_summary_states_igv(self):
        for terms, text in (({"tax_rate": 0.18, "prices_include_tax": False, "currency": "PEN", "exchange_rate": 1, "payment_terms": "Contado"}, "se suma"),
                            ({"tax_rate": 0.18, "prices_include_tax": True, "currency": "PEN", "exchange_rate": 1, "payment_terms": "Contado"}, "incluido")):
            self.assertIn(text, orden_form.summary_html(1000.0, terms))


class PaymentPdfTests(unittest.TestCase):
    def test_pdfs_build(self):
        for data in (reports.order_pdf(ORDER, ITEMS), reports.payment_pdf(ORDER, ITEMS, 2), reports.payment_schedule_pdf(ORDER, ITEMS)):
            self.assertTrue(data.startswith(b"%PDF"))

    def test_payment_number_checked(self):
        with self.assertRaises(ValueError):
            reports.payment_pdf(ORDER, ITEMS, 9)

    def test_whatsapp_lists_payments(self):
        text = reports.order_whatsapp_text(ORDER, ITEMS)
        self.assertIn("Cuota 3", text)
        self.assertIn("Importe total: S/ 1,180.00", text)


if __name__ == "__main__":
    unittest.main()
