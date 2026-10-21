"""Kardex, correo, reporte de obra y los conjuntos nuevos de Reportes (base local)."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from db import local_repository as repo
from utils import kardex, mail, reports


def moves(*rows):
    """Movimientos como los devuelve list_movements: el más reciente primero."""
    return pd.DataFrame(list(reversed(rows)))


def move(created, kind, qty, movement_type=None, **extra):
    return {"created_at": created, "kind": kind, "quantity": qty, "movement_type": movement_type, **extra}


class KardexTests(unittest.TestCase):
    def test_running_balance_in_chronological_order(self):
        table = kardex.build(moves(
            move("2026-10-01T09:00:00", "entrada", 50, "recepcion", order_code="OC-0001"),
            move("2026-10-02T10:00:00", "salida", 12, "despacho", voucher_code="VS-0001", site_name="Torre", requested_by="Juan"),
            move("2026-10-03T11:00:00", "entrada", 2, "devolucion", site_name="Torre"),
            move("2026-10-04T12:00:00", "salida", 5, "conteo", count_code="CT-0001", note="rotura"),
        ))
        self.assertEqual(table["Saldo"].tolist(), [50.0, 38.0, 40.0, 35.0])
        self.assertEqual(table["Documento"].tolist(), ["OC-0001", "VS-0001", "", "CT-0001"])
        self.assertEqual(table.iloc[0]["Fecha"], "2026-10-01 04:00")   # la base guarda UTC: 09:00 UTC son las 04:00 en Lima
        self.assertIn("Juan", table.iloc[1]["Detalle"])
        self.assertTrue(pd.isna(table.iloc[0]["Salida"]) and pd.isna(table.iloc[1]["Entrada"]))

    def test_custom_labels_and_empty_input(self):
        table = kardex.build(moves(move("2026-10-01T09:00:00", "entrada", 1, "recepcion")), lambda t, k: f"<{t}>")
        self.assertEqual(table.iloc[0]["Tipo"], "<recepcion>")
        self.assertTrue(kardex.build(pd.DataFrame()).empty)
        self.assertEqual(list(kardex.build(None).columns), kardex.COLUMNS)


class MailTests(unittest.TestCase):
    def test_mailto_encodes_subject_body_and_recipient(self):
        url = mail.mailto_url(" ventas@norte.com ", "Pedido OC-0001 ñandú", "Hola\nTotal: 10 & más")
        parts = urlparse(url)
        self.assertEqual(parts.scheme, "mailto")
        self.assertEqual(unquote(parts.path), "ventas@norte.com")
        query = parse_qs(parts.query)
        self.assertEqual(query["subject"], ["Pedido OC-0001 ñandú"])
        self.assertEqual(query["body"], ["Hola\nTotal: 10 & más"])

    def test_no_recipient_and_long_bodies(self):
        self.assertTrue(mail.mailto_url(None, "a", "b").startswith("mailto:?subject="))
        url = mail.mailto_url("x@y.com", "a", "línea larga " * 400)
        body = parse_qs(urlparse(url).query)["body"][0]
        self.assertLessEqual(len(body), mail.MAX_BODY)
        self.assertIn("recortado", body)


class ReportDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "Volumen (m³)", min_stock=5)
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.upsert_supplier("Aceros del Sur", None, None, "ventas@aceros.com", None, lead_time_days=3)
        self.sup = repo.list_suppliers().iloc[0]["id"]
        repo.set_supplier_material(self.sup, self.mat, True, True, 100.0)
        repo.create_project_site("Torre Central", "Lima", None, None)
        self.site = repo.list_project_sites().iloc[0]["id"]
        repo.set_budget(self.site, self.mat, 20, 100, "Cimentación")
        repo.create_order(self.sup, "Aceros del Sur", self.site, None, [{"material_id": self.mat, "material_name": "Concreto normal", "unit": "m³", "quantity": 20.0, "unit_price": 100.0}])
        order = repo.list_orders().iloc[0]
        line = repo.list_order_items(order["id"]).iloc[0]["id"]
        repo.receive_order_items(order["id"], {line: 20.0}, "admin", {"document_ref": "T001-1"})
        self.code = repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.mat, "quantity": 6}], "admin", "Cimentación")
        repo.create_return(self.site, "Juan", None, [{"material_id": self.mat, "quantity": 1}], "admin")
        repo.create_inventory_count([{"material_id": self.mat, "counted_qty": 12, "reason": "rotura"}], None, "admin")
        repo.log_action("admin", "prueba")

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_kardex_balance_matches_the_stock_view(self):
        table = kardex.build(repo.list_movements(limit=1000, material_id=self.mat))
        stock = float(repo.stock_levels().set_index("material_id").loc[self.mat, "stock"])
        self.assertEqual(float(table["Saldo"].iloc[-1]), stock)
        self.assertEqual(stock, 12.0)
        self.assertEqual(len(table), 4)   # recepción, despacho, devolución y conteo (20 - 6 + 1 = 15 -> 12)

    def test_movements_can_be_filtered_by_material_and_site_together(self):
        self.assertEqual(len(repo.list_movements(limit=100, material_id=self.mat, project_site_id=self.site)), 2)
        self.assertTrue(repo.list_movements(limit=100, material_id="otro").empty)

    def test_every_report_dataset_builds_and_exports(self):
        from modules import reportes

        frames = {name: build() for name, build in reportes.DATASETS.items()}
        self.assertEqual(len(frames), 17)
        self.assertEqual(len(frames["Vales de salida"]), 1)
        self.assertEqual(frames["Detalle de vales de salida"].iloc[0]["Etapa"], "Cimentación")
        self.assertEqual(float(frames["Presupuestos de obra"].iloc[0]["Importe previsto"]), 2000.0)
        self.assertEqual(frames["Recepciones de órdenes"].iloc[0]["Guía o factura"], "T001-1")
        self.assertEqual(len(frames["Conteos de inventario"]), 1)
        self.assertIn("Aceros del Sur", frames["Calificación de proveedores"]["Proveedor"].tolist())
        self.assertGreaterEqual(len(frames["Historial de precios"]), 1)
        self.assertGreaterEqual(len(frames["Historial de cambios"]), 1)
        self.assertIn("Devolución de obra", frames["Movimientos de inventario"]["Motivo"].tolist())
        self.assertTrue(reports.to_excel(frames).startswith(b"PK"))
        self.assertTrue(reports.to_pdf("Todo", frames).startswith(b"%PDF"))

    def test_site_report_pdf_with_and_without_data(self):
        from modules import obras

        site = repo.list_project_sites().iloc[0].to_dict()
        df = obras.progress_by_material(self.site)
        prog = obras.site_progress(df)
        pdf = obras.site_report(site, df, prog)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual([s["stage"] for s in obras.site_report_stages(self.site)], ["Cimentación"])
        repo.create_project_site("Vacía", None, None, None)
        empty = [s for s in repo.list_project_sites().to_dict("records") if s["name"] == "Vacía"][0]
        empty_df = obras.progress_by_material(empty["id"])
        self.assertTrue(obras.site_report(empty, empty_df, obras.site_progress(empty_df)).startswith(b"%PDF"))

    def test_dispatch_text_lists_the_lines(self):
        voucher = repo.list_dispatches().iloc[0].to_dict()
        text = reports.dispatch_text(voucher, repo.list_dispatch_lines(voucher["id"]))
        self.assertIn(self.code, text)
        self.assertIn("Concreto normal: 6", text)
        self.assertIn("Etapa: Cimentación", text)


if __name__ == "__main__":
    unittest.main()
