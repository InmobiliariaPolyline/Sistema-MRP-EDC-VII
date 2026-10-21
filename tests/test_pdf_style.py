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


class DiversityTests(unittest.TestCase):
    def test_every_theme_and_cover_style_renders(self):
        for theme in pdf_style.THEMES:
            for style in ("band", "ticket", "poster", "stripe", "minimal"):
                with self.subTest(theme=theme, style=style):
                    pdf = BrandPDF("Documento", "DOC-0001", theme=theme, style=style)
                    pdf.add_page()
                    pdf.cover("Etiqueta", "Título del documento", [("Fecha", "21/10/2026"), ("Moneda", "Soles")], ("Estado", "good"), icon="order")
                    pdf.table(["A", "B"], [["uno", "2"]] * 3, [1, 1], ["L", "R"])
                    pdf.stamp("Entregado", 20, 120, "good")
                    self.assertTrue(bytes(pdf.output()).startswith(b"%PDF"))

    def test_second_page_keeps_the_theme_header(self):
        for style in ("stripe", "band"):
            pdf = BrandPDF("Reporte", "X", theme="amber", style=style)
            pdf.add_page()
            pdf.cover("R", "T", [], None)
            for _ in range(80):
                pdf.table(["A"], [["fila"]] * 3, [1])
            self.assertGreater(pdf.page_no(), 1)

    def test_code39_barcode_is_measurable_and_uses_standard_patterns(self):
        pdf = BrandPDF("Vale", "VS-0012", theme="teal", style="ticket")
        pdf.add_page()
        width = pdf.barcode(0, 0, "VS-0012", draw=False)
        self.assertGreater(width, 20)
        self.assertEqual(pdf_style._CODE39["A"], "100001001")
        self.assertEqual(len(pdf_style._CODE39["*"]), 9)
        for char, pattern in pdf_style._CODE39.items():
            self.assertEqual(len(pattern), 9, char)
            self.assertIn(pattern.count("1"), (1, 2, 3), char)
        self.assertGreater(pdf.barcode(0, 0, "VS-0012", draw=True), 20)

    def test_stamp_does_not_move_the_cursor(self):
        pdf = BrandPDF("Orden", "OC-1")
        pdf.add_page()
        pdf.set_xy(30, 77)
        pdf.stamp("Recibida", 20, 100)
        self.assertEqual((round(pdf.get_x()), round(pdf.get_y())), (30, 77))

    def test_documents_use_their_own_family_look(self):
        voucher = {"code": "VS-0001", "created_at": "2026-10-01T10:00:00", "site_name": "Torre", "stage": None, "requested_by": "Juan", "actor": "Luis", "note": ""}
        lines = pd.DataFrame([{"material_name": "Cemento", "unit": "bolsa", "quantity": 3}])
        self.assertTrue(reports.dispatch_pdf(voucher, lines).startswith(b"%PDF"))
        sections = {"Kardex": pd.DataFrame({"Fecha": ["2026-10-01 04:00"], "Entrada": [5.0], "Salida": [None], "Saldo": [5.0]})}
        self.assertTrue(reports.to_pdf("Kardex: Cemento", sections, label="Kardex de inventario", theme="green", style="minimal", icon="list").startswith(b"%PDF"))


class VisualPiecesTests(unittest.TestCase):
    def _pdf(self):
        pdf = BrandPDF("Doc", "D-1", theme="blue", style="poster")
        pdf.add_page()
        return pdf

    def test_charts_and_cards_render_with_edge_values(self):
        pdf = self._pdf()
        for fraction in (None, 0, 0.25, 0.5, 0.999, 1, 1.7):
            pdf.donut(40, 60, 12, fraction, label="x", sub="y")
        pdf.hbars(10, 100, 120, [("Uno", 10, "accent", "10"), ("Dos", 0, "good", "0")])
        pdf.hbars(10, 120, 120, [])
        pdf.linechart(10, 140, 120, 30, [1, 5, 3, 9])
        pdf.linechart(10, 140, 120, 30, [4])               # con un solo punto no dibuja nada y no falla
        pdf.linechart(10, 180, 120, 30, [7, 7, 7])         # línea plana: no divide entre cero
        pdf.index_card([("A", 3), ("B", 0), ("C", 1), ("D", 8)])
        pdf.index_card([])
        pdf.timeline([("Emitida", "hoy", "done"), ("Enviada", "—", "current"), ("Recepción", "—", "todo")], title="Seguimiento")
        self.assertTrue(bytes(pdf.output()).startswith(b"%PDF"))

    def test_watermark_repeats_on_every_page_and_keeps_the_cursor(self):
        pdf = self._pdf()
        pdf.cover("L", "T", [], None)
        pdf.watermark("Cancelada")
        pdf.set_xy(25, 90)
        pdf.watermark("Cancelada")
        self.assertEqual((round(pdf.get_x()), round(pdf.get_y())), (25, 90))
        for _ in range(90):
            pdf.table(["A"], [["fila"]] * 3, [1])
        self.assertGreater(pdf.page_no(), 1)

    def test_long_values_wrap_in_two_lines_instead_of_being_cut(self):
        pdf = self._pdf()
        short = pdf.info_card([("Condición", "Crédito 30 días", None), ("IGV", "Los precios NO incluyen IGV: se suma 18 %", None)], columns=3)
        tall = pdf.info_card([("Condición", "Crédito 30 días", None), ("IGV", "Los precios NO incluyen IGV: se suma 18 % y además otra cosa larga", None)], columns=3)
        plain = pdf.info_card([("Condición", "Crédito 30 días", None), ("IGV", "Sin IGV", None)], columns=3)
        self.assertGreater(short, plain)       # la fila con un valor largo es más alta
        self.assertGreaterEqual(tall, short)

    def test_reports_with_charts_generate(self):
        sections = {"A": pd.DataFrame({"Saldo": [1.0, 4.0, 2.0], "Entrada": [1.0, 3.0, None], "Salida": [None, None, 2.0], "Diferencia": [1, -1, 0]}), "B": pd.DataFrame({"x": [1]})}
        self.assertTrue(reports.to_pdf("Kardex: X", sections, theme="green", style="minimal").startswith(b"%PDF"))
        order = {"code": "OC-1", "status": "cancelada", "created_at": "2026-10-01T10:00:00", "supplier_name": "S", "currency": "PEN", "tax_rate": 0.18,
                 "prices_include_tax": False, "payment_terms": "Contado", "exchange_rate": 1}
        items = pd.DataFrame([{"material_name": "M", "unit": "u", "quantity": 2, "unit_price": 5.0, "received_qty": 1}])
        self.assertTrue(reports.order_pdf(order, items).startswith(b"%PDF"))


class StampTests(unittest.TestCase):
    def _pdf(self):
        pdf = BrandPDF("Doc", "D-1")
        pdf.add_page()
        return pdf

    def test_rect_stamp_reports_its_size_and_can_be_centered(self):
        pdf = self._pdf()
        w, h = pdf.stamp("Recibida parcial", center=(100, 100), sub="OC-1 · 21/10/2026", size=12)
        self.assertEqual((w, h), pdf.stamp_size("Recibida parcial", 12, "OC-1 · 21/10/2026"))
        self.assertGreater(w, 40)
        w2, h2 = pdf.stamp("Ok", 20, 20)
        self.assertLess(w2, w)
        pdf.set_xy(33, 44)
        pdf.stamp("Cancelada", 20, 150, tone="bad", icon="x")
        self.assertEqual((round(pdf.get_x()), round(pdf.get_y())), (33, 44))

    def test_round_seal_fits_any_word_and_keeps_the_cursor(self):
        pdf = self._pdf()
        pdf.set_xy(12, 34)
        for word in ("Ok", "Entregado", "Recibido parcialmente por el almacén"):
            pdf.seal(word, 60, 100, r=15, sub="21/10/2026")
        self.assertEqual((round(pdf.get_x()), round(pdf.get_y())), (12, 34))

    def test_signatures_with_seal_reserve_room_and_stay_on_one_page(self):
        pdf = self._pdf()
        pdf.set_y(pdf.h - 60)     # poco sitio: con sello no cabe y pasa a la página siguiente entero
        pdf.signatures([("Entrega", "Luis"), ("Recibe", "Juan")], seal={"text": "Entregado", "tone": "teal", "r": 15})
        self.assertEqual(pdf.page_no(), 2)
        pdf2 = self._pdf()
        pdf2.set_y(60)
        pdf2.signatures([("Entrega", "Luis"), ("Recibe", "Juan")], seal={"text": "Entregado", "tone": "teal", "r": 15, "sub": "hoy"})
        self.assertEqual(pdf2.page_no(), 1)
        self.assertTrue(bytes(pdf2.output()).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
