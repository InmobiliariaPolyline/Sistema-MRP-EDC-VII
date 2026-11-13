"""Vista central para el agente de Coze: construcción de filas, sincronización, espera y enganche."""
import json
import threading
import unittest

from utils import vista_central as vc


def _fuente(niveles=None, ordenes=None, items=None, obras=None):
    class F:
        def niveles(self):
            return niveles or []

        def ordenes_abiertas(self):
            return ordenes or []

        def items(self, ids):
            self.ids_pedidos = ids
            return items or []

        def obras(self):
            return obras or []

    return F()


class ConstruirVistaTests(unittest.TestCase):
    def test_solo_materiales_con_minimo_y_convierte_numeros(self):
        v = vc.construir_vista(
            [
                {"material_id": "m1", "category": "Concreto", "material_name": "Cemento", "unit": "saco", "min_stock": "20", "stock": "8"},
                {"material_id": "m2", "category": "Acero", "material_name": "Varilla", "unit": "kg", "min_stock": 0, "stock": 100},
            ],
            [], [], [],
        )
        self.assertEqual(len(v["stock"]), 1)
        self.assertEqual(v["stock"][0], {"material_id": "m1", "categoria": "Concreto", "material": "Cemento", "unidad": "saco", "cantidad": 8.0, "minimo": 20.0})

    def test_pedidos_abiertos_con_totales_y_nombre_de_obra(self):
        ordenes = [
            {"id": "o1", "code": "OC-001", "supplier_name": "Aceros del Sur", "project_site_id": "s1", "status": "enviada",
             "expected_date": "2026-07-01", "created_at": "2026-06-01T10:00:00+00:00"},
            {"id": "o2", "code": "OC-002", "supplier_name": "X", "project_site_id": None, "status": "recibida"},
            {"id": "o3", "code": "OC-003", "supplier_name": "Y", "project_site_id": None, "status": "cancelada"},
        ]
        items = [
            {"order_id": "o1", "quantity": 10, "received_qty": 4},
            {"order_id": "o1", "quantity": "5", "received_qty": None},
        ]
        v = vc.construir_vista([], ordenes, items, [{"id": "s1", "name": "Torre Central"}])
        self.assertEqual([p["pedido_id"] for p in v["pedidos"]], ["OC-001"])
        p = v["pedidos"][0]
        self.assertEqual((p["obra"], p["estado"], p["lineas"], p["cantidad_pedida"], p["cantidad_recibida"]), ("Torre Central", "enviada", 2, 15.0, 4.0))
        self.assertEqual(p["llegada_estimada"], "2026-07-01")

    def test_no_incluye_precios_ni_datos_sensibles(self):
        ordenes = [{"id": "o1", "code": "OC-1", "supplier_name": "P", "status": "pendiente", "notes": "privado", "currency": "USD"}]
        items = [{"order_id": "o1", "quantity": 1, "received_qty": 0, "unit_price": 999}]
        v = vc.construir_vista([], ordenes, items, [])
        texto = json.dumps(v)
        for prohibido in ("privado", "999", "unit_price", "notes"):
            self.assertNotIn(prohibido, texto)


class SincronizarTests(unittest.TestCase):
    def test_envia_cinco_sentencias_con_los_datos_como_parametros(self):
        llamadas = []
        fuente = _fuente(
            niveles=[{"material_id": "m1", "category": "C", "material_name": "Cemento Ñandú", "unit": "saco", "min_stock": 20, "stock": 8}],
            ordenes=[{"id": "o1", "code": "OC-1", "supplier_name": "P", "status": "pendiente"}],
        )
        r = vc.sincronizar(fuente, lambda sql, params: llamadas.append((sql, params)))
        self.assertEqual(r, {"stock": 1, "pedidos": 1})
        self.assertEqual([s for s, _ in llamadas], list(vc.SENTENCIAS))
        self.assertEqual(fuente.ids_pedidos, ["o1"])
        self.assertTrue(all("Cemento" not in s for s, _ in llamadas))
        self.assertIn("Cemento", llamadas[0][1][0])
        self.assertIsNone(llamadas[4][1])
        self.assertIn("sync_estado", llamadas[4][0])

    def test_sin_ordenes_no_pide_items(self):
        fuente = _fuente()
        vc.sincronizar(fuente, lambda *_: None)
        self.assertFalse(hasattr(fuente, "ids_pedidos"))

    def test_mensaje_seguro_quita_cadenas_de_conexion(self):
        m = vc.mensaje_seguro(RuntimeError("fallo postgresql://writer:secreto@host/db fin"))
        self.assertNotIn("secreto", m)
        self.assertIn("[conexión]", m)


class PlanificadorTests(unittest.TestCase):
    def test_agrupa_rafagas_en_una_ejecucion(self):
        veces = []
        hecho = threading.Event()
        p = vc.Planificador(lambda: (veces.append(1), hecho.set()), espera_s=0.05)
        p.programar(); p.programar(); p.programar()
        self.assertTrue(hecho.wait(2))
        threading.Event().wait(0.2)
        self.assertEqual(len(veces), 1)

    def test_un_cambio_durante_la_ejecucion_repite_una_vez(self):
        veces = []
        hecho = threading.Event()
        en_curso = threading.Event()
        p = None

        def ejecutar():
            veces.append(1)
            if len(veces) == 1:
                en_curso.set()
                p.programar()          # llega un cambio mientras corre
                threading.Event().wait(0.15)
            else:
                hecho.set()

        p = vc.Planificador(ejecutar, espera_s=0.05)
        p.programar()
        self.assertTrue(hecho.wait(3))
        self.assertEqual(len(veces), 2)

    def test_un_error_al_ejecutar_no_se_propaga(self):
        hecho = threading.Event()

        def falla():
            hecho.set()
            raise RuntimeError("boom")

        p = vc.Planificador(falla, espera_s=0.01)
        p.programar()
        self.assertTrue(hecho.wait(2))
        threading.Event().wait(0.1)   # si se propagara, el hilo dejaría una excepción sin manejar


class EnganchesTests(unittest.TestCase):
    def test_envolver_devuelve_el_resultado_y_avisa_solo_si_termino_bien(self):
        avisos = []
        f = vc.envolver(lambda x: x * 2, lambda: avisos.append(1))
        self.assertEqual(f(4), 8)
        self.assertEqual(avisos, [1])

        def mala():
            raise ValueError("falló")

        g = vc.envolver(mala, lambda: avisos.append(1))
        with self.assertRaises(ValueError):
            g()
        self.assertEqual(avisos, [1])  # no avisó

    def test_si_avisar_falla_la_funcion_original_no_se_ve_afectada(self):
        def avisar():
            raise RuntimeError("sin red")

        f = vc.envolver(lambda: "ok", avisar)
        self.assertEqual(f(), "ok")

    def test_instalar_envuelve_solo_lo_que_existe_y_conserva_el_nombre(self):
        def set_min_stock():
            return 1

        espacio = {"set_min_stock": set_min_stock, "list_materials": lambda: 2}
        avisos = []
        envueltas = vc.instalar(espacio, ("set_min_stock", "no_existe"), lambda: avisos.append(1))
        self.assertEqual(envueltas, ["set_min_stock"])
        self.assertEqual(espacio["set_min_stock"].__name__, "set_min_stock")
        espacio["set_min_stock"]()
        espacio["list_materials"]()
        self.assertEqual(avisos, [1])  # las lecturas no disparan sincronización

    def test_las_funciones_de_escritura_listadas_existen_en_ambos_repositorios(self):
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        for archivo in ("db/supabase_repository.py", "db/local_repository.py"):
            fuente = (raiz / archivo).read_text(encoding="utf-8")
            definidas = set(re.findall(r"^def ([a-z_0-9]+)\(", fuente, re.M))
            faltan = [n for n in vc.FUNCIONES_ESCRITURA if n not in definidas]
            self.assertEqual(faltan, [], f"{archivo} no define: {faltan}")


class ConexionNeonTests(unittest.TestCase):
    """Regresión: el pooler de Neon rechaza `options=-c statement_timeout=...` al conectar."""

    def _psycopg_falso(self):
        import sys
        import types

        registro = {"connect": None, "sentencias": [], "commit": False}

        class Cur:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, sql, params=None): registro["sentencias"].append(sql)

        class Conn:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def cursor(self): return Cur()
            def commit(self): registro["commit"] = True

        def connect(url, **kwargs):
            registro["connect"] = (url, kwargs)
            return Conn()

        falso = types.ModuleType("psycopg")
        falso.connect = connect
        return falso, registro, sys

    def test_no_manda_parametros_de_arranque_y_pide_el_limite_dentro_de_la_transaccion(self):
        falso, registro, sys = self._psycopg_falso()
        anterior = sys.modules.get("psycopg")
        sys.modules["psycopg"] = falso
        try:
            vc._ejecutar_en_neon("postgresql://u:p@host-pooler/db", _fuente())
        finally:
            if anterior is None:
                sys.modules.pop("psycopg", None)
            else:
                sys.modules["psycopg"] = anterior
        url, kwargs = registro["connect"]
        self.assertNotIn("options", kwargs)
        self.assertEqual(registro["sentencias"][0], "SET LOCAL statement_timeout = '15s'")
        self.assertEqual(len(registro["sentencias"]), 1 + len(vc.SENTENCIAS))
        self.assertTrue(registro["commit"])


if __name__ == "__main__":
    unittest.main()
