"""Sincronización con la «vista central» que lee el agente de Coze (solo resúmenes).

- OPCIONAL: sin CENTRAL_DATABASE_URL no hace nada y la app se comporta exactamente igual.
- Nunca rompe una operación: corre en segundo plano, con límite de tiempo, y los errores solo se registran.
- Escribe con el rol `writer_mrp`, que solo puede tocar las tablas del MRP en el esquema `central`.
- Cada ejecución deja la «foto» completa en UNA transacción: o queda todo o no cambia nada, y repetirla no duplica.
- Copia solo materiales con stock mínimo y órdenes abiertas; no copia precios, contactos de proveedores,
  trabajadores, usuarios ni adjuntos.
"""
from __future__ import annotations

import functools
import json
import logging
import threading
from datetime import date, datetime
from typing import Any, Callable, Iterable, Protocol

log = logging.getLogger(__name__)

ESTADOS_ABIERTOS = ("pendiente", "enviada", "parcial")
ESPERA_S = 5.0          # agrupa ráfagas de cambios en una sola sincronización
PAGINA = 1000           # PostgREST devuelve como máximo 1000 filas por petición
LOTE_IDS = 100          # tamaño de los grupos de ids en consultas .in_()

# Funciones de db/repository.py que modifican datos que afectan a la vista.
FUNCIONES_ESCRITURA = (
    "upsert_material", "set_min_stock", "delete_material",
    "create_order", "set_order_status", "delete_order", "update_order", "receive_order_items",
    "add_movement", "create_dispatch", "create_return", "create_inventory_count",
    "create_project_site", "update_project_site", "delete_project_site",
)


class Fuente(Protocol):
    def niveles(self) -> list[dict]: ...
    def ordenes_abiertas(self) -> list[dict]: ...
    def items(self, ids_ordenes: list[str]) -> list[dict]: ...
    def obras(self) -> list[dict]: ...


# Las columnas de la base central son numeric(14,2): un valor mayor haría fallar TODA la sincronización por una sola fila.
LIMITE_NUM = 999_999_999_999.99


def _num(v: Any) -> float:
    """Número seguro para la base central: texto o None => 0; NaN/infinito => 0; acotado a ±LIMITE_NUM."""
    try:
        n = float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
    if n != n or n in (float("inf"), float("-inf")):
        return 0.0
    return max(-LIMITE_NUM, min(LIMITE_NUM, n))


def _fecha(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def construir_vista(niveles: Iterable[dict], ordenes: Iterable[dict], items: Iterable[dict], obras: Iterable[dict]) -> dict:
    """Convierte las filas de origen en las filas de la vista central (función pura)."""
    stock = [
        {
            "material_id": str(n["material_id"]),
            "categoria": n.get("category"),
            "material": n.get("material_name") or "",
            "unidad": n.get("unit") or None,
            "cantidad": _num(n.get("stock")),
            "minimo": _num(n.get("min_stock")),
        }
        for n in niveles
        if _num(n.get("min_stock")) > 0
    ]

    por_orden: dict[str, dict[str, float]] = {}
    for it in items:
        acc = por_orden.setdefault(str(it["order_id"]), {"lineas": 0, "pedida": 0.0, "recibida": 0.0})
        acc["lineas"] += 1
        acc["pedida"] += _num(it.get("quantity"))
        acc["recibida"] += _num(it.get("received_qty"))

    nombre_obra = {str(o["id"]): o.get("name") for o in obras}
    pedidos = []
    for o in ordenes:
        if o.get("status") not in ESTADOS_ABIERTOS:
            continue
        acc = por_orden.get(str(o["id"]), {"lineas": 0, "pedida": 0.0, "recibida": 0.0})
        pedidos.append(
            {
                "pedido_id": str(o["code"]),
                "proveedor": o.get("supplier_name"),
                "obra": nombre_obra.get(str(o.get("project_site_id"))) if o.get("project_site_id") else None,
                "estado": o["status"],
                "llegada_estimada": _fecha(o.get("expected_date")),
                "lineas": int(acc["lineas"]),
                "cantidad_pedida": acc["pedida"],
                "cantidad_recibida": acc["recibida"],
                "creado_en": _fecha(o.get("created_at")),
            }
        )
    return {"stock": stock, "pedidos": pedidos}


_SQL_STOCK = """
INSERT INTO central.mrp_stock (material_id, categoria, material, unidad, cantidad, minimo, actualizado_en)
SELECT t.material_id, t.categoria, t.material, t.unidad, t.cantidad, t.minimo, now()
  FROM jsonb_to_recordset(%s::jsonb) AS t(
    material_id text, categoria text, material text, unidad text, cantidad numeric, minimo numeric)
ON CONFLICT (material_id) DO UPDATE SET
  categoria = EXCLUDED.categoria, material = EXCLUDED.material, unidad = EXCLUDED.unidad,
  cantidad = EXCLUDED.cantidad, minimo = EXCLUDED.minimo, actualizado_en = now()
"""
_SQL_STOCK_BORRAR = """
DELETE FROM central.mrp_stock
 WHERE material_id NOT IN (SELECT t.material_id FROM jsonb_to_recordset(%s::jsonb) AS t(material_id text))
"""
_SQL_PEDIDOS = """
INSERT INTO central.mrp_pedidos
  (pedido_id, proveedor, obra, estado, llegada_estimada, lineas, cantidad_pedida, cantidad_recibida, creado_en, actualizado_en)
SELECT t.pedido_id, t.proveedor, t.obra, t.estado, t.llegada_estimada, t.lineas, t.cantidad_pedida,
       t.cantidad_recibida, t.creado_en, now()
  FROM jsonb_to_recordset(%s::jsonb) AS t(
    pedido_id text, proveedor text, obra text, estado text, llegada_estimada date, lineas int,
    cantidad_pedida numeric, cantidad_recibida numeric, creado_en timestamptz)
ON CONFLICT (pedido_id) DO UPDATE SET
  proveedor = EXCLUDED.proveedor, obra = EXCLUDED.obra, estado = EXCLUDED.estado,
  llegada_estimada = EXCLUDED.llegada_estimada, lineas = EXCLUDED.lineas,
  cantidad_pedida = EXCLUDED.cantidad_pedida, cantidad_recibida = EXCLUDED.cantidad_recibida,
  creado_en = EXCLUDED.creado_en, actualizado_en = now()
"""
_SQL_PEDIDOS_BORRAR = """
DELETE FROM central.mrp_pedidos
 WHERE pedido_id NOT IN (SELECT t.pedido_id FROM jsonb_to_recordset(%s::jsonb) AS t(pedido_id text))
"""
_SQL_ESTADO = """
INSERT INTO central.sync_estado (app, ultima_sync) VALUES ('mrp', now())
ON CONFLICT (app) DO UPDATE SET ultima_sync = now()
"""

SENTENCIAS = (_SQL_STOCK, _SQL_STOCK_BORRAR, _SQL_PEDIDOS, _SQL_PEDIDOS_BORRAR, _SQL_ESTADO)


def sincronizar(fuente: Fuente, ejecutar: Callable[[str, list | None], Any]) -> dict:
    """Lee la fuente y deja la foto en la base central usando `ejecutar(sql, params)`. Lanza si algo falla."""
    ordenes = fuente.ordenes_abiertas()
    ids = [str(o["id"]) for o in ordenes]
    vista = construir_vista(fuente.niveles(), ordenes, fuente.items(ids) if ids else [], fuente.obras())

    js_stock = json.dumps(vista["stock"], default=str)
    js_pedidos = json.dumps(vista["pedidos"], default=str)
    ejecutar(_SQL_STOCK, [js_stock])
    ejecutar(_SQL_STOCK_BORRAR, [js_stock])
    ejecutar(_SQL_PEDIDOS, [js_pedidos])
    ejecutar(_SQL_PEDIDOS_BORRAR, [js_pedidos])
    ejecutar(_SQL_ESTADO, None)
    return {"stock": len(vista["stock"]), "pedidos": len(vista["pedidos"])}


def mensaje_seguro(err: BaseException) -> str:
    """Mensaje de error sin cadenas de conexión (para no dejar credenciales en los registros)."""
    import re

    return re.sub(r"postgres(ql)?://\S+", "[conexión]", str(err), flags=re.IGNORECASE)


# ── Fuente real: Supabase ──────────────────────────────────────────────────────────────────────

class FuenteSupabase:
    """Lee directo de Supabase (sin la caché de Streamlit) para que la foto sea fresca."""

    def __init__(self, client: Any):
        self.c = client

    def _todo(self, consulta_fn: Callable[[], Any]) -> list[dict]:
        filas: list[dict] = []
        desde = 0
        while True:
            lote = consulta_fn().range(desde, desde + PAGINA - 1).execute().data or []
            filas += lote
            if len(lote) < PAGINA:
                return filas
            desde += PAGINA

    def niveles(self) -> list[dict]:
        return self._todo(lambda: self.c.table("stock_levels").select("material_id,category,material_name,unit,min_stock,stock").gt("min_stock", 0))

    def ordenes_abiertas(self) -> list[dict]:
        return self._todo(
            lambda: self.c.table("purchase_orders")
            .select("id,code,supplier_name,project_site_id,status,expected_date,created_at")
            .in_("status", list(ESTADOS_ABIERTOS))
        )

    def items(self, ids_ordenes: list[str]) -> list[dict]:
        filas: list[dict] = []
        for i in range(0, len(ids_ordenes), LOTE_IDS):
            grupo = ids_ordenes[i : i + LOTE_IDS]
            filas += self._todo(lambda g=grupo: self.c.table("purchase_order_items").select("order_id,quantity,received_qty").in_("order_id", g))
        return filas

    def obras(self) -> list[dict]:
        return self._todo(lambda: self.c.table("project_sites").select("id,name"))


# ── Planificador con espera (debounce) ─────────────────────────────────────────────────────────

class Planificador:
    """Agrupa ráfagas de cambios: varias escrituras seguidas producen una sola sincronización.

    Si llega un cambio mientras una sincronización está en curso, se repite una vez al terminar.
    """

    def __init__(self, ejecutar: Callable[[], Any], espera_s: float = ESPERA_S):
        self._ejecutar = ejecutar
        self._espera = espera_s
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._en_curso = False
        self._repetir = False

    def programar(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._espera, self._lanzar)
            self._timer.daemon = True  # no impide que el servidor termine
            self._timer.start()

    def _lanzar(self) -> None:
        with self._lock:
            self._timer = None
            if self._en_curso:
                self._repetir = True
                return
            self._en_curso = True
        try:
            self._ejecutar()
        except Exception as err:  # noqa: BLE001 - nunca debe propagarse
            log.warning("vista central: fallo inesperado: %s", mensaje_seguro(err))
        finally:
            with self._lock:
                self._en_curso = False
                repetir, self._repetir = self._repetir, False
            if repetir:
                self.programar()


# ── Conexión real y enganche con la app ────────────────────────────────────────────────────────

_planificador: Planificador | None = None
_lock_global = threading.Lock()


def _ejecutar_en_neon(url: str, fuente: Fuente) -> None:
    """Una conexión corta y UNA transacción: o se aplica todo o nada."""
    try:
        import psycopg
    except ImportError:
        log.warning("vista central: falta el paquete psycopg; no se sincroniza")
        return
    try:
        # Sin `options=`: el pooler de Neon (host «-pooler») rechaza parámetros de arranque como
        # statement_timeout. El límite se pide dentro de la transacción con SET LOCAL, que sí admite.
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '15s'")
                resultado = sincronizar(fuente, lambda sql, params: cur.execute(sql, params))
            conn.commit()
        # print (y no logging): el nivel INFO no sale en los registros de Streamlit y esta línea confirma que funcionó.
        print(f"vista central: sincronizado {resultado}", flush=True)
    except Exception as err:  # noqa: BLE001
        log.warning("vista central: no se pudo sincronizar: %s", mensaje_seguro(err))


def programar_sincronizacion() -> None:
    """Pide una sincronización (con espera). No hace nada si CENTRAL_DATABASE_URL no está configurada."""
    global _planificador
    from db.client import _get_setting, get_client  # import diferido: no exige Streamlit en las pruebas

    url = _get_setting("CENTRAL_DATABASE_URL")
    if not url:
        return
    with _lock_global:
        if _planificador is None:
            # El cliente se toma aquí (hilo de la app) y no en el temporizador, que no tiene contexto de Streamlit.
            fuente = FuenteSupabase(get_client())
            _planificador = Planificador(lambda: _ejecutar_en_neon(url, fuente))
        planificador = _planificador
    planificador.programar()


def envolver(funcion: Callable, avisar: Callable[[], None] = programar_sincronizacion) -> Callable:
    """Devuelve `funcion` avisando de que hubo un cambio solo si terminó bien. Un fallo al avisar no la afecta."""

    @functools.wraps(funcion)
    def con_aviso(*args: Any, **kwargs: Any):
        resultado = funcion(*args, **kwargs)
        try:
            avisar()
        except Exception as err:  # noqa: BLE001
            log.warning("vista central: no se pudo programar: %s", mensaje_seguro(err))
        return resultado

    return con_aviso


def instalar(espacio: dict, nombres: Iterable[str] = FUNCIONES_ESCRITURA, avisar: Callable[[], None] = programar_sincronizacion) -> list[str]:
    """Envuelve en `espacio` (p. ej. globals() de db/repository.py) las funciones de escritura que existan."""
    envueltas = []
    for nombre in nombres:
        f = espacio.get(nombre)
        if callable(f):
            espacio[nombre] = envolver(f, avisar)
            envueltas.append(nombre)
    return envueltas
