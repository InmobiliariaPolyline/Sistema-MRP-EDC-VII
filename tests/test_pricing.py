"""Vigencia de precios de proveedores."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from db import local_repository as repo
from utils import pricing

NOW = datetime(2026, 10, 15, 12, 0, 0)


class PricingTests(unittest.TestCase):
    def test_age_in_days_for_the_two_date_formats_in_use(self):
        self.assertEqual(pricing.price_age_days("2026-10-05 12:00:00", NOW), 10)           # SQLite
        self.assertEqual(pricing.price_age_days("2026-10-05T12:00:00", NOW), 10)           # ISO
        self.assertEqual(pricing.price_age_days("2026-10-05T12:00:00+00:00", datetime(2026, 10, 15, 12, tzinfo=__import__("datetime").timezone.utc)), 10)

    def test_unknown_dates_are_not_flagged(self):
        for value in (None, "", "None", "nan", "no es fecha"):
            self.assertIsNone(pricing.price_age_days(value, NOW))
            self.assertFalse(pricing.is_stale(value, 90, NOW))

    def test_stale_only_after_the_limit(self):
        self.assertFalse(pricing.is_stale("2026-07-17 12:00:00", 90, NOW))   # 90 días justos
        self.assertTrue(pricing.is_stale("2026-07-16 12:00:00", 90, NOW))    # 91
        self.assertTrue(pricing.is_stale("2026-07-16 12:00:00", 30, NOW))

    def test_description(self):
        self.assertEqual(pricing.describe("2026-10-15 08:00:00", 90, NOW), "actualizado hoy")
        self.assertEqual(pricing.describe("2026-10-05 12:00:00", 90, NOW), "actualizado hace 10 d")
        self.assertIn("vencido", pricing.describe("2026-01-01 12:00:00", 90, NOW))
        self.assertEqual(pricing.describe(None, 90, NOW), "sin fecha de actualización")


class CatalogDatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Aceros del Sur", None, None, None, None)
        self.sup = repo.list_suppliers().iloc[0]["id"]

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_catalog_and_offers_carry_the_price_date(self):
        repo.set_supplier_material(self.sup, self.mat, True, True, 120.0)
        catalog = repo.get_supplier_catalog(self.sup)
        self.assertEqual(pricing.price_age_days(catalog.iloc[0]["price_updated_at"]), 0)
        offers = repo.list_offers()
        self.assertEqual(pricing.price_age_days(offers.iloc[0]["price_updated_at"]), 0)

    def test_old_price_is_reported_stale_and_updating_it_renews_the_date(self):
        repo.set_supplier_material(self.sup, self.mat, True, True, 120.0)
        old = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
        with repo._connect() as conn:
            conn.execute("update supplier_materials set price_updated_at = ?", (old,))
        self.assertTrue(pricing.is_stale(repo.list_offers().iloc[0]["price_updated_at"], 90))
        repo.set_supplier_material(self.sup, self.mat, True, True, 130.0)
        self.assertFalse(pricing.is_stale(repo.list_offers().iloc[0]["price_updated_at"], 90))


if __name__ == "__main__":
    unittest.main()
