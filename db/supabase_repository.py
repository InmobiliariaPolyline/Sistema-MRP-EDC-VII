"""Funciones de acceso a datos sobre Supabase (materiales, proveedores y
la relación proveedor-material). Nada de lógica de interfaz aquí.

Las lecturas se cachean con `st.cache_data` porque cada clic en el sidebar
dispara un rerun completo del script, y sin caché eso significa volver a
llamar a la API de Supabase por red en cada cambio de módulo (de ahí la
demora perceptible al navegar). Cada función que escribe limpia el caché
de las lecturas que dejó desactualizadas."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from db.client import get_client

_CACHE_TTL = 30  # segundos: solo evita relecturas repetidas al navegar, no es "tiempo real"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Los vacíos de las columnas de texto quedan como None, nunca como NaN.

    Con pandas 3, una columna de texto con algunos vacíos pasa a tipo `str` y sus vacíos son NaN,
    que en Python es «verdadero» y un `float`: rompe `" · ".join(...)`, hace que `x or "otro texto"`
    nunca use el texto de reemplazo y se muestra como «nan». La capa local (SQLite) ya devolvía None;
    así Supabase se comporta igual."""
    for col in df.columns:
        series = df[col]
        if (series.dtype == object or pd.api.types.is_string_dtype(series)) and series.isna().any():
            df[col] = series.astype(object).where(series.notna(), None)
    return df


def _df(data=None, *args, **kwargs) -> pd.DataFrame:
    """pd.DataFrame(...) con los vacíos de texto limpios (ver `_clean`)."""
    return _clean(pd.DataFrame(data, *args, **kwargs))


def _select_all(build, limit: int | None = None, page: int = 1000) -> list[dict]:
    """Trae TODAS las filas de una consulta. PostgREST corta cada respuesta en 1 000 filas sin avisar,
    así que se pide por páginas. `build()` debe devolver una consulta nueva y ya ordenada (con un
    orden estable, p. ej. terminando en `.order("id")`)."""
    rows: list[dict] = []
    start = 0
    while True:
        end = start + page - 1
        if limit is not None:
            end = min(end, limit - 1)
        batch = build().range(start, end).execute().data or []
        rows += batch
        if len(batch) < page or (limit is not None and len(rows) >= limit):
            break
        start += page
    return rows


def _friendly(exc: Exception) -> ValueError:
    """Convierte un error de PostgREST (por ejemplo, una excepción lanzada por un
    trigger de la base) en un ValueError con el mensaje legible."""
    message = getattr(exc, "message", None) or str(exc)
    return ValueError(message)


def _is_missing(exc: Exception) -> bool:
    """¿El error significa que todavía no se corrió el SQL del parche (columna, tabla,
    vista o función inexistente)? Entonces se usa el camino de respaldo."""
    text = f"{getattr(exc, 'code', '')} {exc}"
    return any(t in text for t in ("PGRST202", "PGRST200", "PGRST205", "42703", "42P01", "42883", "Could not find", "does not exist"))


def _invalidate_stock() -> None:
    for fn in (list_movements, stock_levels, dashboard_totals, list_dispatches, list_orders, list_order_items):
        fn.clear()


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_materials() -> pd.DataFrame:
    res = get_client().table("materials").select("*").order("category").order("name").execute()
    df = _df(res.data or [], columns=["id", "category", "name", "density", "metric_label", "min_stock", "created_at", "updated_at"])
    df["min_stock"] = pd.to_numeric(df["min_stock"], errors="coerce").fillna(0.0)
    return df


def upsert_material(
    category: str, name: str, density: float | None, metric_label: str, material_id: str | None = None, min_stock: float = 0.0
) -> None:
    payload: dict[str, Any] = {"category": category, "name": name, "density": density, "metric_label": metric_label}
    client = get_client()

    def write(data: dict) -> None:
        if material_id:
            client.table("materials").update(data).eq("id", material_id).execute()
        else:
            client.table("materials").upsert(data, on_conflict="category,name").execute()

    try:
        write({**payload, "min_stock": float(min_stock or 0)})
    except Exception as exc:
        if not _is_missing(exc):
            raise
        write(payload)  # la columna min_stock aún no existe (SQL del parche 036 pendiente)
    _invalidate_materials()


def delete_material(material_id: str) -> None:
    get_client().table("materials").delete().eq("id", material_id).execute()
    _invalidate_materials()


def _invalidate_materials() -> None:
    list_materials.clear()
    stock_levels.clear()
    dashboard_totals.clear()
    recent_activity.clear()
    get_supplier_catalog.clear()
    list_offers.clear()


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_suppliers() -> pd.DataFrame:
    res = get_client().table("suppliers").select("*").order("name").execute()
    return _df(
        res.data or [],
        columns=["id", "name", "contact_name", "phone", "email", "notes", "created_at", "updated_at"],
    )


def upsert_supplier(
    name: str,
    contact_name: str | None,
    phone: str | None,
    email: str | None,
    notes: str | None,
    supplier_id: str | None = None,
) -> None:
    payload = {"name": name, "contact_name": contact_name, "phone": phone, "email": email, "notes": notes}
    client = get_client()
    if supplier_id:
        client.table("suppliers").update(payload).eq("id", supplier_id).execute()
    else:
        client.table("suppliers").insert(payload).execute()
    _invalidate_suppliers()


def delete_supplier(supplier_id: str) -> None:
    get_client().table("suppliers").delete().eq("id", supplier_id).execute()
    _invalidate_suppliers()


def _invalidate_suppliers() -> None:
    list_suppliers.clear()
    dashboard_totals.clear()
    recent_activity.clear()
    get_supplier_catalog.clear()
    list_offers.clear()
    list_orders.clear()


# ---------------------------------------------------------------------------
# Catálogo de un proveedor (materiales que ofrece, con disponibilidad)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_supplier_catalog(supplier_id: str) -> pd.DataFrame:
    """Todos los materiales del catálogo general, indicando si este
    proveedor los ofrece y si están disponibles."""
    materials = list_materials()
    res = (
        get_client()
        .table("supplier_materials")
        .select("*")
        .eq("supplier_id", supplier_id)
        .execute()
    )
    links = _df(res.data or [], columns=["id", "supplier_id", "material_id", "available", "price"])

    if materials.empty:
        return materials.assign(link_id=None, offered=False, available=False, price=None)

    merged = materials.merge(
        links[["material_id", "id", "available", "price"]].rename(columns={"id": "link_id"}),
        left_on="id",
        right_on="material_id",
        how="left",
    )
    merged["offered"] = merged["link_id"].notna()
    merged["available"] = merged["available"].fillna(False)
    return merged.drop(columns=["material_id"])


def set_supplier_material(supplier_id: str, material_id: str, offered: bool, available: bool, price: float | None) -> None:
    client = get_client()
    if not offered:
        client.table("supplier_materials").delete().eq("supplier_id", supplier_id).eq("material_id", material_id).execute()
    else:
        client.table("supplier_materials").upsert(
            {"supplier_id": supplier_id, "material_id": material_id, "available": available, "price": price},
            on_conflict="supplier_id,material_id",
        ).execute()
    get_supplier_catalog.clear()
    list_offers.clear()
    dashboard_totals.clear()


def bulk_set_supplier_prices(supplier_id: str, rows: list[dict], make_available: bool = True) -> int:
    """Carga precios de muchos materiales de un proveedor de una vez (importación de su lista).
    Cada fila: {"material_id": ..., "price": ...}. Una sola escritura. Devuelve cuántos se aplicaron.
    El historial de precios lo anota un trigger de la base."""
    if not rows:
        return 0
    client = get_client()
    existing = (
        client.table("supplier_materials").select("material_id,available").eq("supplier_id", supplier_id).execute().data or []
    )
    current = {r["material_id"]: bool(r["available"]) for r in existing}
    payload = [
        {
            "supplier_id": supplier_id,
            "material_id": row["material_id"],
            "price": float(row["price"]),
            "available": True if make_available else current.get(row["material_id"], True),
        }
        for row in rows
    ]
    client.table("supplier_materials").upsert(payload, on_conflict="supplier_id,material_id").execute()
    get_supplier_catalog.clear()
    list_offers.clear()
    dashboard_totals.clear()
    return len(payload)


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_price_history(material_id: str | None = None, supplier_id: str | None = None, limit: int = 200) -> pd.DataFrame:
    columns = ["id", "supplier_id", "supplier_name", "material_id", "material_name", "price", "source", "recorded_at"]
    query = get_client().table("price_history").select("*, suppliers(name), materials(name)").order("recorded_at", desc=True).limit(limit)
    if material_id:
        query = query.eq("material_id", material_id)
    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    try:
        data = query.execute().data or []
    except Exception as exc:
        if _is_missing(exc):
            return _df(columns=columns)
        raise
    rows = []
    for row in data:
        supplier = row.pop("suppliers", None) or {}
        material = row.pop("materials", None) or {}
        rows.append({**row, "supplier_name": supplier.get("name"), "material_name": material.get("name")})
    return _df(rows, columns=columns)


# ---------------------------------------------------------------------------
# Usuarios (login)
# ---------------------------------------------------------------------------
# Sin caché: son lecturas ligadas a autenticación/autorización, siempre deben
# reflejar el estado real de la base (activo/inactivo, contraseña, etc.).

def count_users() -> int:
    res = get_client().table("users").select("id", count="exact").execute()
    return res.count or 0


def list_users() -> pd.DataFrame:
    res = get_client().table("users").select("*").order("name").execute()
    df = _df(
        res.data or [],
        columns=["id", "username", "password_hash", "name", "role", "active", "created_at", "updated_at"],
    )
    return df


def get_user_by_username(username: str) -> dict | None:
    res = get_client().table("users").select("*").eq("username", username).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def create_user(username: str, password_hash: str, name: str, role: str) -> None:
    get_client().table("users").insert(
        {"username": username, "password_hash": password_hash, "name": name, "role": role}
    ).execute()


def set_user_active(user_id: str, active: bool) -> None:
    get_client().table("users").update({"active": active}).eq("id", user_id).execute()


def delete_user(user_id: str) -> None:
    get_client().table("users").delete().eq("id", user_id).execute()


# ---------------------------------------------------------------------------
# Trabajadores: cuadrillas, obras y el propio catálogo de trabajadores
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_work_groups() -> pd.DataFrame:
    res = get_client().table("work_groups").select("*").order("name").execute()
    return _df(res.data or [], columns=["id", "name", "created_at"])


def create_work_group(name: str) -> None:
    get_client().table("work_groups").insert({"name": name}).execute()
    list_work_groups.clear()


def delete_work_group(group_id: str) -> None:
    get_client().table("work_groups").delete().eq("id", group_id).execute()
    list_work_groups.clear()
    list_workers.clear()


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_project_sites() -> pd.DataFrame:
    res = get_client().table("project_sites").select("*").order("name").execute()
    return _df(res.data or [], columns=["id", "name", "address", "latitude", "longitude", "created_at"])


def create_project_site(name: str, address: str | None, latitude: float | None, longitude: float | None) -> None:
    get_client().table("project_sites").insert(
        {"name": name, "address": address, "latitude": latitude, "longitude": longitude}
    ).execute()
    list_project_sites.clear()


def delete_project_site(site_id: str) -> None:
    get_client().table("project_sites").delete().eq("id", site_id).execute()
    list_project_sites.clear()
    list_workers.clear()


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_workers() -> pd.DataFrame:
    res = (
        get_client()
        .table("workers")
        .select("*, work_groups(name), project_sites(name,address,latitude,longitude), users(username,role)")
        .order("full_name")
        .execute()
    )
    rows = []
    for row in res.data or []:
        group = row.pop("work_groups", None) or {}
        site = row.pop("project_sites", None) or {}
        user = row.pop("users", None) or {}
        rows.append(
            {
                **row,
                "group_name": group.get("name"),
                "site_name": site.get("name"),
                "site_address": site.get("address"),
                "latitude": site.get("latitude"),
                "longitude": site.get("longitude"),
                "username": user.get("username"),
                "role": user.get("role"),
            }
        )
    return _df(rows)


def create_worker(
    full_name: str,
    document_id: str | None,
    phone: str | None,
    position: str | None,
    work_group_id: str | None,
    project_site_id: str | None,
) -> str:
    res = (
        get_client()
        .table("workers")
        .insert(
            {
                "full_name": full_name,
                "document_id": document_id,
                "phone": phone,
                "position": position,
                "work_group_id": work_group_id,
                "project_site_id": project_site_id,
            }
        )
        .execute()
    )
    list_workers.clear()
    return res.data[0]["id"]


def update_worker(
    worker_id: str,
    full_name: str,
    document_id: str | None,
    phone: str | None,
    position: str | None,
    work_group_id: str | None,
    project_site_id: str | None,
) -> None:
    get_client().table("workers").update(
        {
            "full_name": full_name,
            "document_id": document_id,
            "phone": phone,
            "position": position,
            "work_group_id": work_group_id,
            "project_site_id": project_site_id,
        }
    ).eq("id", worker_id).execute()
    list_workers.clear()


def delete_worker(worker_id: str) -> None:
    get_client().table("workers").delete().eq("id", worker_id).execute()
    list_workers.clear()


def grant_worker_access(worker_id: str, username: str, password_hash: str, name: str, role: str) -> None:
    client = get_client()
    res = client.table("users").insert(
        {"username": username, "password_hash": password_hash, "name": name, "role": role}
    ).execute()
    user_id = res.data[0]["id"]
    client.table("workers").update({"user_id": user_id}).eq("id", worker_id).execute()
    list_workers.clear()


def revoke_worker_access(worker_id: str, user_id: str) -> None:
    client = get_client()
    client.table("workers").update({"user_id": None}).eq("id", worker_id).execute()
    client.table("users").delete().eq("id", user_id).execute()
    list_workers.clear()


# ---------------------------------------------------------------------------
# Ofertas (qué ofrece cada proveedor y a qué precio) — para comparar precios
# y para los reportes
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_offers() -> pd.DataFrame:
    data = _select_all(
        lambda: get_client()
        .table("supplier_materials")
        .select("supplier_id,material_id,available,price,suppliers(name),materials(category,name)")
        .order("id")
    )
    rows = []
    for row in data:
        supplier = row.pop("suppliers", None) or {}
        material = row.pop("materials", None) or {}
        rows.append(
            {
                "supplier_id": row["supplier_id"],
                "supplier_name": supplier.get("name"),
                "material_id": row["material_id"],
                "category": material.get("category"),
                "material_name": material.get("name"),
                "available": bool(row.get("available")),
                "price": row.get("price"),
            }
        )
    columns = ["supplier_id", "supplier_name", "material_id", "category", "material_name", "available", "price"]
    df = _df(rows, columns=columns)
    return df.sort_values(["category", "material_name", "supplier_name"]).reset_index(drop=True) if not df.empty else df


# ---------------------------------------------------------------------------
# Órdenes de compra
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_orders() -> pd.DataFrame:
    res = (
        get_client()
        .table("purchase_orders")
        .select("*, project_sites(name), purchase_order_items(quantity,unit_price)")
        .order("created_at", desc=True)
        .execute()
    )
    rows = []
    for row in res.data or []:
        site = row.pop("project_sites", None) or {}
        items = row.pop("purchase_order_items", None) or []
        rows.append(
            {
                **row,
                "site_name": site.get("name"),
                "total": sum(float(i["quantity"]) * float(i["unit_price"]) for i in items),
                "items_count": len(items),
            }
        )
    columns = [
        "id", "code", "supplier_id", "supplier_name", "project_site_id", "site_name",
        "status", "notes", "created_at", "total", "items_count",
    ]
    df = _df(rows)
    return df[columns] if not df.empty else _df(columns=columns)


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_order_items(order_id: str | None = None) -> pd.DataFrame:
    """Líneas de una orden, o de todas (con el código de su orden) si no se pasa id."""
    def build():
        query = get_client().table("purchase_order_items").select("*, purchase_orders(code)").order("id")
        return query.eq("order_id", order_id) if order_id else query

    rows = []
    for row in _select_all(build):
        order = row.pop("purchase_orders", None) or {}
        rows.append(
            {
                "id": row["id"],
                "order_id": row["order_id"],
                "order_code": order.get("code"),
                "material_id": row.get("material_id"),
                "material_name": row["material_name"],
                "unit": row.get("unit"),
                "quantity": float(row["quantity"]),
                "unit_price": float(row["unit_price"]),
                "received_qty": float(row.get("received_qty") or 0),
                "subtotal": float(row["quantity"]) * float(row["unit_price"]),
            }
        )
    columns = ["id", "order_id", "order_code", "material_id", "material_name", "unit", "quantity", "unit_price", "received_qty", "subtotal"]
    df = _df(rows, columns=columns)
    return df.sort_values(["order_code", "material_name"]).reset_index(drop=True) if not df.empty else df


def create_order(supplier_id: str, supplier_name: str, project_site_id: str | None, notes: str | None, items: list[dict]) -> str:
    """Crea la orden con sus líneas y devuelve su código (OC-0001, OC-0002...)."""
    client = get_client()
    existing = client.table("purchase_orders").select("code").execute().data or []
    numbers = [int(r["code"].split("-")[1]) for r in existing if r["code"].startswith("OC-") and r["code"].split("-")[1].isdigit()]
    code = f"OC-{(max(numbers) if numbers else 0) + 1:04d}"

    res = client.table("purchase_orders").insert(
        {
            "code": code,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "project_site_id": project_site_id,
            "notes": notes,
        }
    ).execute()
    order_id = res.data[0]["id"]
    client.table("purchase_order_items").insert(
        [
            {
                "order_id": order_id,
                "material_id": item["material_id"],
                "material_name": item["material_name"],
                "unit": item.get("unit"),
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
            }
            for item in items
        ]
    ).execute()
    _invalidate_orders()
    return code


def set_order_status(order_id: str, status: str) -> None:
    get_client().table("purchase_orders").update({"status": status}).eq("id", order_id).execute()
    _invalidate_orders()


def delete_order(order_id: str) -> None:
    """Elimina una orden. Si ya recibió material no se puede (el stock quedaría descuadrado)."""
    client = get_client()
    received = client.table("purchase_order_items").select("id").eq("order_id", order_id).gt("received_qty", 0).limit(1).execute().data
    if received:
        raise ValueError("La orden ya recibió material: cancélala en lugar de eliminarla.")
    try:
        client.table("purchase_orders").delete().eq("id", order_id).execute()
    except Exception as exc:
        raise _friendly(exc) from exc
    _invalidate_orders()


def update_order(order_id: str, project_site_id: str | None, notes: str | None, items: list[dict]) -> None:
    """Edita obra, notas y líneas de una orden que todavía no recibió material.
    `items` reemplaza las líneas actuales (material_id, material_name, unit, quantity, unit_price)."""
    client = get_client()
    rows = client.table("purchase_orders").select("status").eq("id", order_id).limit(1).execute().data
    if not rows:
        raise ValueError("La orden no existe.")
    if rows[0]["status"] in ("recibida", "cancelada", "parcial"):
        raise ValueError("Esta orden ya no se puede editar.")
    if client.table("purchase_order_items").select("id").eq("order_id", order_id).gt("received_qty", 0).limit(1).execute().data:
        raise ValueError("La orden ya recibió material y no se puede editar.")
    if not items:
        raise ValueError("La orden debe tener al menos una línea.")
    client.table("purchase_order_items").delete().eq("order_id", order_id).execute()
    client.table("purchase_order_items").insert(
        [
            {
                "order_id": order_id,
                "material_id": item.get("material_id"),
                "material_name": item["material_name"],
                "unit": item.get("unit"),
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
            }
            for item in items
        ]
    ).execute()
    client.table("purchase_orders").update({"project_site_id": project_site_id, "notes": notes}).eq("id", order_id).execute()
    _invalidate_orders()


def _invalidate_orders() -> None:
    list_orders.clear()
    list_order_items.clear()
    list_movements.clear()
    stock_levels.clear()
    dashboard_totals.clear()


def receive_order_items(order_id: str, receipts: dict[str, float], actor: str | None = None) -> str:
    """Registra lo recibido por línea (id de línea -> cantidad que llegó ahora),
    genera las entradas de stock y deja la orden en 'parcial' o 'recibida'.
    Usa la función `receive_order` de la base (todo o nada); si todavía no se corrió el
    SQL del parche 036, usa un respaldo en Python que valida antes de escribir."""
    client = get_client()
    clean = {k: float(v) for k, v in receipts.items() if v and float(v) > 0}
    try:
        res = client.rpc("receive_order", {"p_order_id": order_id, "p_receipts": clean, "p_actor": actor}).execute()
        _invalidate_orders()
        return res.data if isinstance(res.data, str) else str(res.data)
    except Exception as exc:
        if not _is_missing(exc):
            raise _friendly(exc) from exc

    # --- respaldo: se valida todo antes de escribir para minimizar el riesgo de dejar algo a medias ---
    order = client.table("purchase_orders").select("code,status").eq("id", order_id).limit(1).execute().data
    if not order:
        raise ValueError("La orden no existe.")
    code = order[0]["code"]
    if order[0]["status"] == "cancelada":
        raise ValueError(f"La orden {code} está cancelada y no puede recibir material.")
    items = client.table("purchase_order_items").select("*").eq("order_id", order_id).execute().data or []
    by_id = {i["id"]: i for i in items}
    for item_id, qty in clean.items():
        item = by_id.get(item_id)
        if item is None:
            raise ValueError("La línea no pertenece a la orden.")
        if float(item.get("received_qty") or 0) + qty > float(item["quantity"]) + 1e-9:
            raise ValueError("Se intenta recibir más de lo pedido en una línea.")
    movements, pending = [], False
    for item in items:
        received = float(item.get("received_qty") or 0)
        arrived = clean.get(item["id"], 0.0)
        if arrived > 0 and item.get("material_id"):
            movements.append(
                {"material_id": item["material_id"], "kind": "entrada", "quantity": arrived, "note": f"Recepción {code}", "order_id": order_id, "actor": actor}
            )
        if received + arrived < float(item["quantity"]):
            pending = True
    if movements:  # primero el stock: si falla, ninguna línea quedó marcada como recibida
        try:
            client.table("stock_movements").insert([{**m, "movement_type": "recepcion"} for m in movements]).execute()
        except Exception as exc:
            if not _is_missing(exc):
                raise _friendly(exc) from exc
            client.table("stock_movements").insert(movements).execute()
    for item_id, qty in clean.items():
        client.table("purchase_order_items").update({"received_qty": float(by_id[item_id].get("received_qty") or 0) + qty}).eq("id", item_id).execute()
    status = "parcial" if pending else "recibida"
    client.table("purchase_orders").update({"status": status}).eq("id", order_id).execute()
    _invalidate_orders()
    return status


# ---------------------------------------------------------------------------
# Inventario (movimientos de stock) y presupuesto por obra
# ---------------------------------------------------------------------------

def add_movement(
    material_id: str, kind: str, quantity: float, project_site_id: str | None, note: str | None, actor: str | None,
    movement_type: str | None = None,
) -> None:
    """Entrada o salida suelta (ajuste, merma). Una salida nunca deja el stock en negativo."""
    if quantity is None or quantity <= 0:
        raise ValueError("La cantidad debe ser mayor que 0.")
    if kind == "salida":
        stock_levels.clear()  # el control usa el stock real, no uno cacheado
        levels = stock_levels()
        current = levels.loc[levels["material_id"] == material_id, "stock"]
        have = float(current.iloc[0]) if not current.empty else 0.0
        if have < quantity - 1e-9:
            raise ValueError("Stock insuficiente para esta salida.")
    movement_type = movement_type or ("entrada_manual" if kind == "entrada" else ("despacho" if project_site_id else "merma"))
    payload = {
        "material_id": material_id, "project_site_id": project_site_id, "kind": kind, "quantity": quantity,
        "note": note, "actor": actor,
    }
    try:
        get_client().table("stock_movements").insert({**payload, "movement_type": movement_type}).execute()
    except Exception as exc:
        if not _is_missing(exc):
            raise _friendly(exc) from exc
        get_client().table("stock_movements").insert(payload).execute()
    _invalidate_stock()


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_movements(project_site_id: str | None = None, limit: int = 500) -> pd.DataFrame:
    columns = [
        "id", "material_id", "material_name", "category", "unit", "project_site_id", "site_name",
        "kind", "quantity", "note", "order_code", "actor", "created_at", "movement_type", "voucher_code", "requested_by",
    ]

    def fetch(select: str):
        def build():
            query = get_client().table("stock_movements").select(select).order("created_at", desc=True).order("id")
            return query.eq("project_site_id", project_site_id) if project_site_id else query

        return _select_all(build, limit=limit)

    base = "*, materials(name,category,metric_label), project_sites(name), purchase_orders(code)"
    try:
        data = fetch(base + ", dispatch_vouchers(code,requested_by)")
    except Exception as exc:
        if not _is_missing(exc):
            raise
        data = fetch(base)  # el SQL del parche 036 todavía no se corrió
    rows = []
    for row in data:
        material = row.pop("materials", None) or {}
        site = row.pop("project_sites", None) or {}
        order = row.pop("purchase_orders", None) or {}
        voucher = row.pop("dispatch_vouchers", None) or {}
        rows.append(
            {
                "id": row["id"],
                "material_id": row["material_id"],
                "material_name": material.get("name"),
                "category": material.get("category"),
                "unit": material.get("metric_label"),
                "project_site_id": row.get("project_site_id"),
                "site_name": site.get("name"),
                "kind": row["kind"],
                "quantity": float(row["quantity"]),
                "note": row.get("note"),
                "order_code": order.get("code"),
                "actor": row.get("actor"),
                "created_at": row["created_at"],
                "movement_type": row.get("movement_type"),
                "voucher_code": voucher.get("code"),
                "requested_by": voucher.get("requested_by"),
            }
        )
    return _df(rows, columns=columns)


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def stock_levels() -> pd.DataFrame:
    """Stock actual de TODOS los materiales (sin límite de movimientos).
    Usa la vista `stock_levels`; si todavía no existe, lo calcula con los movimientos."""
    columns = ["material_id", "category", "material_name", "unit", "min_stock", "entradas", "salidas", "stock"]
    client = get_client()
    try:
        data = client.table("stock_levels").select("*").order("category").order("material_name").execute().data or []
        df = _df(data, columns=columns)
    except Exception as exc:
        if not _is_missing(exc):
            raise
        materials = list_materials()
        moves = _select_all(lambda: client.table("stock_movements").select("material_id,kind,quantity").order("id"))
        totals: dict[str, list[float]] = {}
        for m in moves:
            entry, exit_ = totals.setdefault(m["material_id"], [0.0, 0.0])
            if m["kind"] == "entrada":
                totals[m["material_id"]][0] = entry + float(m["quantity"])
            else:
                totals[m["material_id"]][1] = exit_ + float(m["quantity"])
        rows = [
            {
                "material_id": r["id"], "category": r["category"], "material_name": r["name"], "unit": r["metric_label"],
                "min_stock": r.get("min_stock") or 0.0, "entradas": totals.get(r["id"], [0.0, 0.0])[0],
                "salidas": totals.get(r["id"], [0.0, 0.0])[1],
            }
            for r in materials.to_dict("records")
        ]
        df = _df(rows, columns=columns)
        df["stock"] = df["entradas"].astype(float) - df["salidas"].astype(float)
    for col in ("min_stock", "entradas", "salidas", "stock"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def create_dispatch(
    project_site_id: str, worker_id: str | None, requested_by: str | None, note: str | None, lines: list[dict], actor: str | None,
) -> str:
    """Despacha material del almacén a una obra con su vale de salida (VS-0001...).
    `lines`: [{"material_id", "quantity", "note"?}]. Todo o nada: si algún material no
    alcanza, no se registra nada. Devuelve el código del vale."""
    if not lines:
        raise ValueError("El vale no tiene materiales.")
    wanted: dict[str, float] = {}
    for line in lines:
        if not line["quantity"] or line["quantity"] <= 0:
            raise ValueError("Todas las cantidades deben ser mayores que 0.")
        wanted[line["material_id"]] = wanted.get(line["material_id"], 0.0) + float(line["quantity"])
    stock_levels.clear()  # el control usa el stock real, no uno cacheado
    levels = stock_levels()
    available = levels.set_index("material_id")["stock"].to_dict()
    names = levels.set_index("material_id")["material_name"].to_dict()
    for material_id, qty in wanted.items():
        if float(available.get(material_id, 0.0)) < qty - 1e-9:
            raise ValueError(f"Stock insuficiente de «{names.get(material_id, material_id)}»: hay {float(available.get(material_id, 0.0)):g} y se piden {qty:g}.")

    client = get_client()
    params = {
        "p_site": project_site_id, "p_worker": worker_id, "p_requested_by": requested_by, "p_note": note, "p_actor": actor,
        "p_lines": [{"material_id": l["material_id"], "quantity": float(l["quantity"]), "note": l.get("note") or ""} for l in lines],
    }
    try:
        res = client.rpc("create_dispatch", params).execute()
        _invalidate_stock()
        return str(res.data)
    except Exception as exc:
        if not _is_missing(exc):
            raise _friendly(exc) from exc

    # --- respaldo (SQL del parche 036 pendiente): vale y movimientos con la API normal ---
    site = client.table("project_sites").select("name").eq("id", project_site_id).limit(1).execute().data
    if not site:
        raise ValueError("La obra no existe.")
    try:
        codes = [r["code"] for r in (client.table("dispatch_vouchers").select("code").execute().data or [])]
    except Exception as exc:
        raise ValueError("Falta correr el SQL del parche 036 en Supabase (db/migrations/036_despacho_mrp.sql).") from exc
    number = max([int(c.split("-")[1]) for c in codes if c.startswith("VS-") and c.split("-")[1].isdigit()] or [0]) + 1
    code = f"VS-{number:04d}"
    voucher = client.table("dispatch_vouchers").insert(
        {
            "code": code, "project_site_id": project_site_id, "site_name": site[0]["name"], "worker_id": worker_id,
            "requested_by": (requested_by or "").strip() or None, "note": (note or "").strip() or None, "actor": actor,
        }
    ).execute().data[0]
    client.table("stock_movements").insert(
        [
            {
                "material_id": l["material_id"], "project_site_id": project_site_id, "kind": "salida", "quantity": float(l["quantity"]),
                "note": l.get("note") or f"Despacho {code}", "actor": actor, "voucher_id": voucher["id"], "movement_type": "despacho",
            }
            for l in lines
        ]
    ).execute()
    _invalidate_stock()
    return code


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_dispatches(limit: int = 200) -> pd.DataFrame:
    columns = ["id", "code", "project_site_id", "site_name", "worker_id", "requested_by", "note", "actor", "created_at", "lines_count"]
    try:
        data = get_client().table("dispatch_vouchers").select("*, stock_movements(id)").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        if _is_missing(exc):
            return _df(columns=columns)
        raise
    rows = [{**{k: v for k, v in row.items() if k != "stock_movements"}, "lines_count": len(row.get("stock_movements") or [])} for row in data]
    return _df(rows, columns=columns)


def list_dispatch_lines(voucher_id: str) -> pd.DataFrame:
    columns = ["id", "material_id", "material_name", "category", "unit", "quantity", "note"]
    data = (
        get_client().table("stock_movements").select("id,material_id,quantity,note,materials(name,category,metric_label)").eq("voucher_id", voucher_id).execute().data or []
    )
    rows = []
    for row in data:
        material = row.pop("materials", None) or {}
        rows.append(
            {
                "id": row["id"], "material_id": row["material_id"], "material_name": material.get("name"),
                "category": material.get("category"), "unit": material.get("metric_label"),
                "quantity": float(row["quantity"]), "note": row.get("note"),
            }
        )
    df = _df(rows, columns=columns)
    return df.sort_values("material_name").reset_index(drop=True) if not df.empty else df


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_budgets(project_site_id: str | None = None) -> pd.DataFrame:
    def build():
        query = get_client().table("site_budgets").select("*, materials(category,name,metric_label)").order("id")
        return query.eq("project_site_id", project_site_id) if project_site_id else query

    rows = []
    for row in _select_all(build):
        material = row.pop("materials", None) or {}
        rows.append(
            {
                "id": row["id"],
                "project_site_id": row["project_site_id"],
                "material_id": row["material_id"],
                "category": material.get("category"),
                "material_name": material.get("name"),
                "unit": material.get("metric_label"),
                "planned_qty": float(row["planned_qty"]),
                "planned_unit_price": float(row["planned_unit_price"]),
            }
        )
    columns = ["id", "project_site_id", "material_id", "category", "material_name", "unit", "planned_qty", "planned_unit_price"]
    df = _df(rows, columns=columns)
    return df.sort_values(["category", "material_name"]).reset_index(drop=True) if not df.empty else df


def set_budget(project_site_id: str, material_id: str, planned_qty: float, planned_unit_price: float) -> None:
    get_client().table("site_budgets").upsert(
        {
            "project_site_id": project_site_id,
            "material_id": material_id,
            "planned_qty": planned_qty,
            "planned_unit_price": planned_unit_price,
        },
        on_conflict="project_site_id,material_id",
    ).execute()
    list_budgets.clear()


def delete_budget(budget_id: str) -> None:
    get_client().table("site_budgets").delete().eq("id", budget_id).execute()
    list_budgets.clear()


# ---------------------------------------------------------------------------
# Asistencia
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_attendance(start: str, end: str) -> pd.DataFrame:
    """Asistencia entre dos fechas (YYYY-MM-DD, ambas incluidas)."""
    data = _select_all(
        lambda: get_client()
        .table("attendance")
        .select("*, workers(full_name), project_sites(name)")
        .gte("work_date", start)
        .lte("work_date", end)
        .order("work_date", desc=True)
        .order("id")
    )
    rows = []
    for row in data:
        worker = row.pop("workers", None) or {}
        site = row.pop("project_sites", None) or {}
        rows.append(
            {
                "id": row["id"],
                "worker_id": row["worker_id"],
                "worker_name": worker.get("full_name"),
                "project_site_id": row.get("project_site_id"),
                "site_name": site.get("name"),
                "work_date": row["work_date"],
                "status": row["status"],
                "note": row.get("note"),
            }
        )
    columns = ["id", "worker_id", "worker_name", "project_site_id", "site_name", "work_date", "status", "note"]
    df = _df(rows, columns=columns)
    return df.sort_values(["work_date", "worker_name"], ascending=[False, True]).reset_index(drop=True) if not df.empty else df


def set_attendance(worker_id: str, project_site_id: str | None, work_date: str, status: str, note: str | None) -> None:
    get_client().table("attendance").upsert(
        {
            "worker_id": worker_id,
            "project_site_id": project_site_id,
            "work_date": work_date,
            "status": status,
            "note": note,
        },
        on_conflict="worker_id,work_date",
    ).execute()
    list_attendance.clear()


# ---------------------------------------------------------------------------
# Historial de cambios
# ---------------------------------------------------------------------------

def log_action(actor: str, summary: str) -> None:
    get_client().table("audit_log").insert({"actor": actor, "summary": summary}).execute()
    list_audit.clear()


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_audit(limit: int = 300) -> pd.DataFrame:
    res = get_client().table("audit_log").select("*").order("created_at", desc=True).limit(limit).execute()
    return _df(res.data or [], columns=["id", "actor", "summary", "created_at"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def dashboard_totals() -> dict:
    materials = list_materials()
    suppliers = list_suppliers()
    data = _select_all(lambda: get_client().table("supplier_materials").select("supplier_id,material_id,available").order("id"))
    links = _df(data, columns=["supplier_id", "material_id", "available"])

    suppliers_with_available = links.loc[links["available"] == True, "supplier_id"].nunique() if not links.empty else 0  # noqa: E712
    materials_with_supplier = set(links["material_id"]) if not links.empty else set()
    materials_without_supplier = len(materials) - len([m for m in materials["id"] if m in materials_with_supplier])

    orders = list_orders()
    orders_open = int(orders["status"].isin(["pendiente", "enviada", "parcial"]).sum()) if not orders.empty else 0

    levels = stock_levels()
    stock = levels["stock"].astype(float)
    minimum = levels["min_stock"].astype(float)
    dispatches = list_dispatches()
    month = pd.Timestamp.now().strftime("%Y-%m")
    dispatches_month = int((dispatches["created_at"].astype(str).str[:7] == month).sum()) if not dispatches.empty else 0

    return {
        "materials": len(materials),
        "suppliers": len(suppliers),
        "suppliers_with_available": int(suppliers_with_available),
        "materials_without_supplier": int(materials_without_supplier),
        "orders_open": orders_open,
        "materials_in_stock": int((stock > 0).sum()),
        "low_stock": int(((minimum > 0) & (stock <= minimum)).sum()),
        "dispatches_month": dispatches_month,
    }


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def recent_activity(limit: int = 6) -> list[dict]:
    """Últimos materiales y proveedores agregados, mezclados por fecha."""
    client = get_client()
    mat_res = client.table("materials").select("name,category,created_at").order("created_at", desc=True).limit(limit).execute()
    sup_res = client.table("suppliers").select("name,phone,created_at").order("created_at", desc=True).limit(limit).execute()

    items = [
        {"name": row["name"], "sub": row.get("category") or "Material", "kind": "Material", "created_at": row["created_at"]}
        for row in (mat_res.data or [])
    ] + [
        {"name": row["name"], "sub": row.get("phone") or "Proveedor", "kind": "Proveedor", "created_at": row["created_at"]}
        for row in (sup_res.data or [])
    ]
    items.sort(key=lambda it: it["created_at"] or "", reverse=True)
    return items[:limit]
# Tablas de la app, en orden de dependencia (para respaldos y restauración).
BACKUP_TABLES = [
    "materials", "suppliers", "supplier_materials", "users", "work_groups", "project_sites", "workers",
    "purchase_orders", "purchase_order_items", "dispatch_vouchers", "stock_movements",
    "site_budgets", "attendance", "audit_log", "price_history",
]


def set_user_password(user_id: str, password_hash: str) -> None:
    get_client().table("users").update({"password_hash": password_hash}).eq("id", user_id).execute()


def dump_tables() -> dict[str, pd.DataFrame]:
    """Todas las tablas de la app, completas (por páginas), para el respaldo."""
    client = get_client()
    out: dict[str, pd.DataFrame] = {}
    for table in BACKUP_TABLES:
        try:
            rows = _select_all(lambda t=table: client.table(t).select("*").order("id"))
        except Exception as exc:
            if _is_missing(exc):
                continue  # tabla de un parche cuyo SQL aún no se corrió
            raise
        out[table] = pd.DataFrame(rows)
    return out
