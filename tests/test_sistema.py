"""Módulo Sistema: versión, entorno y novedades (sin secretos)."""
import tempfile
import unittest
from pathlib import Path

from core.version import APP_VERSION
from modules import sistema


class SistemaTests(unittest.TestCase):
    def test_changelog_entries_newest_first_with_titles_and_dates(self):
        entries = sistema.changelog_entries(limit=3)
        self.assertEqual(len(entries), 3)
        numbers = [int(e["version"].split()[1]) for e in entries]
        self.assertEqual(numbers, sorted(numbers, reverse=True))
        self.assertTrue(all(e["title"] for e in entries))

    def test_changelog_parsing_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.md"
            path.write_text("# Registro\n\n## Parche 012 — Con fecha · 2026-01-02\ntexto\n## Parche 011 — Sin fecha\n## Otro título\n## Parche 9 — Corto · 2025-12-31\n", encoding="utf-8")
            self.assertEqual(
                sistema.changelog_entries(path=path),
                [
                    {"version": "parche 012", "title": "Con fecha", "date": "2026-01-02"},
                    {"version": "parche 011", "title": "Sin fecha", "date": ""},
                    {"version": "parche 9", "title": "Corto", "date": "2025-12-31"},
                ],
            )
            self.assertEqual(sistema.changelog_entries(path=Path(tmp) / "no-existe.md"), [])

    def test_environment_and_support_text_hold_no_secrets(self):
        info = sistema.environment()
        text = sistema.support_text(info)
        self.assertIn(APP_VERSION, text)
        self.assertIn("Streamlit", text)
        for forbidden in ("SUPABASE", "password", "clave:", "sb_secret", "eyJ"):
            self.assertNotIn(forbidden, text)
        self.assertIn(info["security_tone"], ("good", "warn", "bad"))

    def test_flow_describes_the_real_process(self):
        self.assertEqual([step for step, _ in sistema.FLOW][:2], ["Proveedor", "Orden de compra"])
        self.assertIn("pago se hace aparte", dict(sistema.FLOW)["Orden de compra"])


if __name__ == "__main__":
    unittest.main()
