"""RUC, datos de la empresa, IGV real (18 %) y condición de pago."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from db import local_repository as repo
from utils import money, reports
from utils import ruc as ruc_rules

SUNAT = "20131312955"          # SUNAT
SUPERMERCADOS = "20100070970"  # Supermercados Peruanos S.A.


class RucTests(unittest.TestCase):
    def test_known_rucs_are_valid_and_one_wrong_digit_is_not(self):
        for value in (SUNAT, SUPERMERCADOS, "20 1313 12955", "20-13131295-5"):
            self.assertTrue(ruc_rules.is_valid(value), value)
        self.assertFalse(ruc_rules.is_valid("20131312956"))
        self.assertFalse(ruc_rules.is_valid("20100070971"))

    def test_check_digit_special_cases(self):
        # el dígito calculado 10 se escribe 0 y 11 se escribe 1
        for first_ten in ("2000000000", "2000000001", "1000000000", "2012345678", "2098765432"):
            digit = ruc_rules.check_digit(first_ten)
            self.assertIn(digit, range(10))
            self.assertTrue(ruc_rules.is_valid(first_ten + str(digit)))

    def test_issues_explain_the_problem(self):
        self.assertEqual(ruc_rules.issues("", "RUC"), [])
        self.assertIn("obligatorio", ruc_rules.issues("", "RUC", required=True)[0])
        self.assertIn("11 dígitos", ruc_rules.issues("2013131295")[0])
        self.assertIn("11 dígitos", ruc_rules.issues("201313129555")[0])
        self.assertIn("empezar con", ruc_rules.issues("30131312955")[0])
        self.assertIn("verificador", ruc_rules.issues("20131312956")[0])
        self.assertEqual(ruc_rules.issues(SUNAT), [])

    def test_kind_and_clean(self):
        self.assertEqual(ruc_rules.kind(SUNAT), "Persona jurídica")
        self.assertEqual(ruc_rules.kind("10412345678"), "Persona natural")
        self.assertIsNone(ruc_rules.kind("123"))
        self.assertEqual(ruc_rules.clean(" 20.131.312-955 "), SUNAT)
        self.assertEqual(ruc_rules.clean(None), "")


class IgvTests(unittest.TestCase):
    def test_igv_is_18_percent(self):
        self.assertEqual(money.IGV, 0.18)

    def test_prices_without_igv_get_18_percent_on_top(self):
        a = money.amounts(1000, 0.18)
        self.assertAlmostEqual(a["net"], 1000.0)
        self.assertAlmostEqual(a["tax"], 180.0)
        self.assertAlmostEqual(a["total"], 1180.0)

    def test_prices_that_include_igv_are_split(self):
        a = money.amounts(1180, 0.18, prices_include_tax=True)
        self.assertAlmostEqual(a["net"], 1000.0)
        self.assertAlmostEqual(a["tax"], 180.0)
        self.assertAlmostEqual(a["total"], 1180.0)
        self.assertAlmostEqual(a["subtotal_base"], 1000.0)   # sin IGV, para comparar con el presupuesto

    def test_amounts_are_rounded_to_cents_like_an_invoice(self):
        a = money.amounts(15.75, 0.18)          # 15.75 × 0,18 = 2,835 -> 2,84 (el .5 sube)
        self.assertEqual((a["net"], a["tax"], a["total"]), (15.75, 2.84, 18.59))
        self.assertAlmostEqual(a["net"] + a["tax"], a["total"])
        b = money.amounts(99.99, 0.18, prices_include_tax=True)
        self.assertEqual(b["total"], 99.99)
        self.assertAlmostEqual(b["net"] + b["tax"], b["total"])   # lo que se separa siempre suma el total
        self.assertEqual(money.cents(0.125), 0.13)
        self.assertEqual(money.cents(2.675), 2.68)
        out = money.add_amounts(pd.DataFrame([{"subtotal": 15.75, "tax_rate": 0.18, "exchange_rate": 1.0, "prices_include_tax": False}]))
        self.assertEqual((float(out["tax"].iloc[0]), float(out["total"].iloc[0])), (2.84, 18.59))

    def test_exempt_and_dollar_orders(self):
        self.assertEqual(money.amounts(500, 0)["total"], 500.0)
        self.assertEqual(money.amounts(500, 0, prices_include_tax=True)["tax"], 0.0)   # incluir IGV sin tasa no tiene efecto
        d = money.amounts(1180, 0.18, 3.8, True)
        self.assertAlmostEqual(d["total_base"], 1180 * 3.8)
        self.assertAlmostEqual(d["subtotal_base"], 1000 * 3.8)

    def test_modes_round_trip(self):
        for mode, (_, rate, include) in money.TAX_MODES.items():
            self.assertEqual(money.tax_mode(rate, include), mode)
            self.assertEqual(money.tax_from_mode(mode), (rate, include))
        self.assertEqual(money.default_terms()["tax_rate"], 0.18)
        self.assertFalse(money.default_terms()["prices_include_tax"])

    def test_include_flag_needs_a_tax_rate_and_payment_terms_are_checked(self):
        self.assertFalse(money.normalize_terms({"tax_rate": 0, "prices_include_tax": True})["prices_include_tax"])
        self.assertTrue(money.normalize_terms({"tax_rate": 0.18, "prices_include_tax": True})["prices_include_tax"])
        self.assertEqual(money.normalize_terms({"payment_terms": "Crédito 30 días"})["payment_terms"], "Crédito 30 días")
        self.assertIsNone(money.normalize_terms({"payment_terms": "  "})["payment_terms"])
        with self.assertRaises(ValueError):
            money.normalize_terms({"payment_terms": "Cuando se pueda"})

    def test_credit_days_and_due_date(self):
        self.assertEqual(money.credit_days("Crédito 30 días"), 30)
        self.assertEqual(money.credit_days("Crédito 7 días"), 7)
        self.assertIsNone(money.credit_days("Contado"))
        self.assertIsNone(money.credit_days(None))
        self.assertEqual(money.due_date("2026-10-12T09:30:00", "Crédito 30 días"), date(2026, 11, 11))
        self.assertEqual(money.due_date(date(2026, 1, 31), "Crédito 15 días"), date(2026, 2, 15))
        self.assertIsNone(money.due_date("2026-10-12", "Contado"))
        self.assertIsNone(money.due_date("no es fecha", "Crédito 30 días"))

    def test_table_amounts_mix_both_ways_of_pricing(self):
        orders = pd.DataFrame(
            [
                {"subtotal": 1000.0, "tax_rate": 0.18, "exchange_rate": 1.0, "prices_include_tax": False},
                {"subtotal": 1180.0, "tax_rate": 0.18, "exchange_rate": 1.0, "prices_include_tax": True},
                {"subtotal": 500.0, "tax_rate": 0.0, "exchange_rate": 1.0, "prices_include_tax": None},
            ]
        )
        out = money.add_amounts(orders)
        self.assertEqual([round(v, 2) for v in out["net"]], [1000.0, 1000.0, 500.0])
        self.assertEqual([round(v, 2) for v in out["tax"]], [180.0, 180.0, 0.0])
        self.assertEqual([round(v, 2) for v in out["total"]], [1180.0, 1180.0, 500.0])
        self.assertTrue(money.add_amounts(orders.iloc[0:0]).empty)


class CompanyAndOrdersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Aceros del Sur", None, None, None, None, ruc=SUPERMERCADOS)
        self.supplier = repo.list_suppliers().iloc[0]["id"]

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_company_profile_is_empty_then_saved_then_updated(self):
        empty = repo.get_company()
        self.assertTrue(all(v is None for v in empty.values()))
        repo.set_company(" Constructora Andina S.A.C. ", "Andina", "20 13131295-5", "Av. Lima 123", "admin")
        company = repo.get_company()
        self.assertEqual((company["legal_name"], company["ruc"], company["updated_by"]), ("Constructora Andina S.A.C.", SUNAT, "admin"))
        repo.set_company("Andina SAC", None, SUNAT, None, "otro")
        self.assertEqual(repo.get_company()["legal_name"], "Andina SAC")
        self.assertIsNone(repo.get_company()["trade_name"])
        with repo._connect() as conn:
            self.assertEqual(conn.execute("select count(*) from company_profile").fetchone()[0], 1)   # siempre una sola ficha

    def test_invalid_company_ruc_is_rejected_and_nothing_is_saved(self):
        with self.assertRaises(ValueError):
            repo.set_company("X", None, "20131312956", None)
        self.assertIsNone(repo.get_company()["ruc"])

    def test_supplier_ruc_is_saved_validated_and_can_be_cleared(self):
        self.assertEqual(repo.list_suppliers().iloc[0]["ruc"], SUPERMERCADOS)
        with self.assertRaises(ValueError):
            repo.upsert_supplier("Aceros del Sur", None, None, None, None, self.supplier, ruc="123")
        repo.upsert_supplier("Aceros del Sur", None, None, None, None, self.supplier, ruc=None)
        self.assertIsNone(repo.list_suppliers().iloc[0]["ruc"])

    def test_company_is_part_of_the_backup(self):
        repo.set_company("Andina", None, SUNAT, None)
        self.assertIn("company_profile", repo.dump_tables())

    def _order(self, terms):
        items = [{"material_id": self.mat, "material_name": "Concreto normal", "unit": "m³", "quantity": 10.0, "unit_price": 118.0}]
        code = repo.create_order(self.supplier, "Aceros del Sur", None, None, items, terms)
        return repo.list_orders().query("code == @code").iloc[0]

    def test_orders_store_the_igv_mode_and_payment_terms(self):
        added = self._order({"tax_rate": 0.18, "payment_terms": "Crédito 30 días"})
        self.assertEqual((float(added["net"]), round(float(added["tax"]), 2), round(float(added["total"]), 2)), (1180.0, 212.4, 1392.4))
        self.assertEqual(added["payment_terms"], "Crédito 30 días")
        included = self._order({"tax_rate": 0.18, "prices_include_tax": True})
        self.assertEqual((round(float(included["net"]), 2), round(float(included["tax"]), 2), float(included["total"])), (1000.0, 180.0, 1180.0))
        self.assertTrue(bool(included["prices_include_tax"]))
        exempt = self._order({"tax_rate": 0})
        self.assertEqual(float(exempt["total"]), 1180.0)
        self.assertEqual(float(exempt["tax"]), 0.0)

    def test_editing_the_terms_changes_the_amounts(self):
        order = self._order({"tax_rate": 0.18})
        items = [{"material_id": self.mat, "material_name": "Concreto normal", "unit": "m³", "quantity": 10.0, "unit_price": 118.0}]
        repo.update_order(order["id"], None, None, items, {"tax_rate": 0.18, "prices_include_tax": True, "payment_terms": "Contado"})
        updated = repo.list_orders().iloc[0]
        self.assertEqual(round(float(updated["net"]), 2), 1000.0)
        self.assertEqual(updated["payment_terms"], "Contado")

    def test_pdf_and_message_carry_ruc_igv_and_payment(self):
        order = self._order({"tax_rate": 0.18, "prices_include_tax": True, "payment_terms": "Crédito 15 días"}).to_dict()
        items = repo.list_order_items(order["id"])
        supplier = repo.list_suppliers().iloc[0].to_dict()
        company = {"legal_name": "Constructora Andina S.A.C.", "trade_name": "Andina", "ruc": SUNAT, "fiscal_address": "Av. Lima 123"}
        self.assertTrue(reports.order_pdf(order, items, supplier, company).startswith(b"%PDF"))
        self.assertTrue(reports.order_pdf(order, items, supplier, None).startswith(b"%PDF"))       # sin datos de la empresa también sale
        text = reports.order_whatsapp_text(order, items, company)
        self.assertIn(f"RUC {SUNAT}", text)
        self.assertIn("Valor de venta: S/ 1,000.00", text)
        self.assertIn("IGV (18%): S/ 180.00", text)
        self.assertIn("Importe total: S/ 1,180.00", text)
        self.assertIn("ya incluyen IGV", text)
        self.assertIn("Crédito 15 días", text)
        self.assertNotIn("RUC", reports.order_whatsapp_text(order, items, None))


if __name__ == "__main__":
    unittest.main()
