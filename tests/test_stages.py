"""Presupuesto por etapas de obra y despacho por etapa (base local)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from db import local_repository as repo
from modules import obras, sugerencias
from utils import consumption


class StageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_material("Concreto", "Concreto normal", 2400, "m³")
        self.mat = repo.list_materials().iloc[0]["id"]
        repo.create_project_site("Torre Central", "Lima", None, None)
        self.site = repo.list_project_sites().iloc[0]["id"]
        repo.add_movement(self.mat, "entrada", 100, None, "stock", "admin")

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_same_material_can_be_budgeted_in_several_stages(self):
        repo.set_budget(self.site, self.mat, 20, 100, "Cimentación")
        repo.set_budget(self.site, self.mat, 30, 110, "Estructura")
        repo.set_budget(self.site, self.mat, 5, 90)  # sin etapa
        budgets = repo.list_budgets(self.site)
        self.assertEqual(len(budgets), 3)
        self.assertEqual(sorted(budgets["stage"].tolist()), ["", "Cimentación", "Estructura"])
        repo.set_budget(self.site, self.mat, 25, 100, " Cimentación ")  # misma etapa: reemplaza
        budgets = repo.list_budgets(self.site)
        self.assertEqual(len(budgets), 3)
        self.assertEqual(float(budgets[budgets["stage"] == "Cimentación"].iloc[0]["planned_qty"]), 25.0)
        self.assertEqual(obras.site_stages(self.site), ["Cimentación", "Estructura"])

    def test_progress_all_stages_adds_up_and_each_stage_is_separate(self):
        repo.set_budget(self.site, self.mat, 20, 100, "Cimentación")
        repo.set_budget(self.site, self.mat, 30, 110, "Estructura")
        repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.mat, "quantity": 8}], "admin", "Cimentación")
        repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.mat, "quantity": 5}], "admin")
        total = obras.progress_by_material(self.site).iloc[0]
        self.assertEqual(float(total["Presupuesto"]), 50.0)
        self.assertEqual(float(total["Presupuesto $"]), 20 * 100 + 30 * 110)
        self.assertEqual(float(total["Despachado"]), 13.0)
        cim = obras.progress_by_material(self.site, "Cimentación").iloc[0]
        self.assertEqual((float(cim["Presupuesto"]), float(cim["Despachado"])), (20.0, 8.0))
        est = obras.progress_by_material(self.site, "Estructura").iloc[0]
        self.assertEqual((float(est["Presupuesto"]), float(est["Despachado"])), (30.0, 0.0))
        none = obras.progress_by_material(self.site, "")
        self.assertEqual(float(none.iloc[0]["Despachado"]), 5.0)

    def test_dispatch_keeps_the_stage_on_voucher_and_movements(self):
        code = repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.mat, "quantity": 3}], "admin", "Cimentación")
        voucher = repo.list_dispatches().query("code == @code").iloc[0]
        self.assertEqual(voucher["stage"], "Cimentación")
        self.assertEqual(repo.list_movements(limit=10).iloc[0]["stage"], "Cimentación")

    def test_returns_reduce_the_stage_they_came_from(self):
        repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.mat, "quantity": 8}], "admin", "Cimentación")
        moves = repo.list_movements(project_site_id=self.site, limit=100)
        self.assertEqual(consumption.net_by_material(moves)[self.mat], 8.0)

    def test_suggestions_do_not_double_subtract_when_split_in_stages(self):
        repo.set_budget(self.site, self.mat, 60, 100, "Cimentación")
        repo.set_budget(self.site, self.mat, 60, 100, "Estructura")
        repo.create_dispatch(self.site, None, "Juan", None, [{"material_id": self.mat, "quantity": 20}], "admin")
        data = sugerencias.compute_suggestions(
            repo.list_budgets(), repo.list_orders(), repo.list_order_items(), repo.stock_levels(), repo.site_consumption(), repo.list_offers()
        )
        # presupuesto 120, despachado 20 -> demanda 100; stock 80 -> faltan 20
        self.assertEqual(round(float(data.iloc[0]["demand"]), 6), 100.0)
        self.assertEqual(round(float(data.iloc[0]["deficit"]), 6), 20.0)

    def test_old_local_database_is_upgraded_keeping_its_budgets(self):
        old = Path(self.tmp.name) / "old.db"
        conn = sqlite3.connect(old)
        conn.executescript(
            """
            create table materials (id text primary key, category text, name text, density real, metric_label text, min_stock real default 0, created_at text, updated_at text);
            create table project_sites (id text primary key, name text, address text, latitude real, longitude real, created_at text);
            create table site_budgets (id text primary key, project_site_id text, material_id text, planned_qty real, planned_unit_price real,
                created_at text, updated_at text, unique (project_site_id, material_id));
            insert into materials (id, category, name) values ('m1', 'c', 'n');
            insert into project_sites (id, name) values ('s1', 'obra');
            insert into site_budgets values ('b1', 's1', 'm1', 7, 3, null, null);
            """
        )
        conn.commit()
        conn.close()
        repo.DB_PATH = old
        repo._init_db()
        budgets = repo.list_budgets("s1")
        self.assertEqual(len(budgets), 1)
        self.assertEqual(float(budgets.iloc[0]["planned_qty"]), 7.0)
        self.assertEqual(budgets.iloc[0]["stage"], "")
        repo.set_budget("s1", "m1", 9, 3, "Fase 1")  # ya admite etapas
        self.assertEqual(len(repo.list_budgets("s1")), 2)


if __name__ == "__main__":
    unittest.main()
