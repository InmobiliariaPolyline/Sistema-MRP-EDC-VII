"""Estilo de los PDF: fuente Inter incluida, textos largos o vacíos, varias páginas y todos los documentos."""
import unittest
from pathlib import Path

import pandas as pd

from utils import pdf_style, reports
from utils.pdf_style import BrandPDF


def sample_order(**extra):
    order = {"code": "OC-0001", "created_at": "2026-10-12T09:30:00", "status": "pendiente", "supplier_name": "Ferretería Norte S.A.C.",
             "site_name": None, "notes": None, "expected_date": None, "currency": "PEN", "tax_rate": 0.0, "exchange_rate": 1}
    order.update(extra)
    return order


def sample_items(n=3, name="Cemento Portland tipo I"):
    return pd.DataFrame([{"material_name": f"{name} {i}", "unit": "bolsa", "quantity": 10.0 + i, "unit_price": 25.5, "received_qty": 0.0} for i in range(n)])


class FontsAndHelpersTests(unittest.TestCase):
    def test_inter_fonts_and_license_are_in_the_project(self):
        for name in ("Inter_Regular.ttf", "Inter_SemiBold.ttf", "Inter_Bold.ttf", "OFL.txt"):
            self.assertTrue((pdf_style.FONTS / name).stat().st_size > (100 if name.endswith(".txt") else 100_000), name)

    def test_fit_and_wrap_respect_the_width(self):
        pdf = BrandPDF("Prueba")
        pdf.add_page()
        pdf.font(9)
        long = "Cemento Portland tipo I resistente a sulfatos " * 5
        fitted = pdf.fit(long, 40)
        self.assertTrue(fitted.endswith("…"))
        self.assertLessEqual(pdf.get_string_width(fitted), 40)
        self.assertEqual(pdf.fit("corto", 40), "corto")
        self.assertEqual(pdf.fit(None, 40), "")
        lines = pdf.wrap(long, 60, max_lines=2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(pdf.get_string_width(l) <= 60 for l in lines))
        self.assertEqual(pdf.wrap("", 60), [""])

    def test_every_icon_draws(self):
        pdf = BrandPDF("Iconos")
        pdf.add_page()
        for name in pdf_style._ICONS:
            pdf.icon(name, 20, 40, 8)
        self.assertTrue(bytes(pdf.output()).startswith(b"%PDF"))

    def test_unicode_characters_are_supported(self):
        pdf = BrandPDF("Texto")
        pdf.add_page()
        pdf.font(10)
        pdf.cell(0, 6, "→ ✓ — · • ≥ × ° ñ Ñ á é í ó ú ü € № S/ 1,234.50")
        self.assertTrue(bytes(pdf.output()).startswith(b"%PDF"))

    def test_long_tables_continue_on_new_pages_with_page_numbers(self):
        pdf = BrandPDF("Tabla")
        pdf.add_page()
        pdf.cover("Reporte", "Prueba")
        rows = [[str(i), f"Material {i}", f"{i:,.2f}"] for i in range(120)]
        pdf.table(["N.º", "Material", "Cantidad"], rows, [1, 6, 2], ["L", "L", "R"])
        self.assertGreaterEqual(pdf.page_no(), 3)
        self.assertTrue(bytes(pdf.output()).startswith(b"%PDF"))


class DocumentTests(unittest.TestCase):
    def test_order_pdf_with_everything_and_with_almost_nothing(self):
        full = reports.order_pdf(
            sample_order(site_name="Torre Central", notes="Entregar antes del viernes", expected_date="2026-10-20", currency="USD", tax_rate=0.18, exchange_rate=3.8, status="parcial", sent_at="2026-10-13T10:00:00"),
            sample_items(), {"contact_name": "Ana", "phone": "+51 987", "email": "a@b.pe"},
        )
        bare = reports.order_pdf(sample_order(), sample_items(1), None)
        for pdf in (full, bare):
            self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(full), len(bare) // 2)

    def test_order_pdf_with_long_names_many_lines_and_missing_values(self):
        items = sample_items(80, "Cemento Portland tipo I resistente a sulfatos para cimentaciones profundas en suelos agresivos")
        items.loc[0, "unit"] = None
        items.loc[1, "received_qty"] = float("nan")
        pdf = reports.order_pdf(sample_order(notes="nota larga " * 80, status="inventado"), items, {"contact_name": None})
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_dispatch_pdf_variants(self):
        lines = pd.DataFrame([{"material_name": "Arena gruesa", "unit": None, "quantity": 6.5}])
        voucher = {"code": "VS-0001", "created_at": "2026-10-14T16:45:00", "site_name": "Torre", "stage": None, "requested_by": None, "actor": None, "note": None}
        self.assertTrue(reports.dispatch_pdf(voucher, lines).startswith(b"%PDF"))
        voucher.update(stage="Cimentación", requested_by="Juan Pérez", actor="Luis", note="Para la losa " * 30)
        self.assertTrue(reports.dispatch_pdf(voucher, pd.concat([lines] * 60, ignore_index=True)).startswith(b"%PDF"))

    def test_generic_report_with_empty_numeric_and_text_sections(self):
        frames = {
            "Vacío": pd.DataFrame(),
            "Números": pd.DataFrame({"Material": ["a", None], "Cantidad": [1.5, float("nan")], "Activo": [True, False]}),
            "Muchas columnas": pd.DataFrame([[f"valor largo {i} " * 3 for i in range(14)]] * 5, columns=[f"Columna {i}" for i in range(14)]),
        }
        self.assertTrue(reports.to_pdf("Todo junto", frames).startswith(b"%PDF"))

    def test_site_report_with_empty_data(self):
        site = {"name": "Obra vacía", "address": None}
        empty = pd.DataFrame(columns=["Material", "Unidad", "Presupuesto", "Pedido", "Recibido", "Despachado", "Presupuesto $", "Pedido $", "Recibido $", "Despachado $"])
        pdf = reports.site_report_pdf(site, {"planned": 0.0, "ordered": 0.0, "pct_consumed": None}, empty, [], pd.DataFrame(columns=["code", "created_at", "stage", "requested_by", "lines_count"]), 0)
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
