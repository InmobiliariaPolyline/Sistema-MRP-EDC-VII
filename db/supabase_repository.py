"""Funciones de acceso a datos sobre Supabase (materiales, proveedores y
la relación proveedor-material). Nada de lógica de interfaz aquí.

Las lecturas se cachean con `st.cache_data` porque cada clic en el sidebar
dispara un rerun completo del script, y sin caché eso significa volver a
llamar a la API de Supabase por red en cada cambio de módulo (de ahí la
demora perceptible al navegar). Cada función que escribe limpia el caché
de las lecturas que dejó desactualizadas."""
from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd
import streamlit as st

from db.client import get_client, using_service_key
from utils import attachments as attach_rules
from utils import audit
from utils import ruc as ruc_rules
from utils import consumption, money

_CACHE_TTL = int(os.environ.get("MRP_CACHE_TTL") or 30)  # segundos: solo evita relecturas repetidas al navegar, no es "tiempo real"


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


PHASE_B_MESSAGE = "Falta correr el SQL de la Fase B en Supabase (db/migrations/041_fase_b.sql)."


def _phase_b(exc: Exception) -> ValueError:
    """Error legible cuando una función de la Fase B se usa antes de correr su SQL."""
    return ValueError(PHASE_B_MESSAGE)


def _need_sql(file: str) -> ValueError:
    """Error legible cuando algo necesita el SQL de un parche que todavía no se corrió."""
    return ValueError(f"Falta correr el SQL de esta función en Supabase (db/migrations/{file}).")


def _is_missing(exc: Exception) -> bool:
    """¿El error significa que todavía no se corrió el SQL del parche (columna, tabla,
    vista o función inexistente)? Entonces se usa el camino de respaldo."""
    text = f"{getattr(exc, 'code', '')} {exc}"
    return any(t in text for t in ("PGRST202", "PGRST200", "PGRST204", "PGRST205", "42703", "42P01", "42883", "Could not find", "does not exist"))


def _embedded_count(value) -> int:
    """Cantidad de filas de una relación pedida como `tabla(count)` (PostgREST devuelve [{"count": n}])."""
    if not value:
        return 0
    first = value[0] if isinstance(value, list) else value
    return int(first.get("count", 0)) if isinstance(first, dict) else 0


def _invalidate_stock() -> None:
    for fn in (list_movements, stock_levels, dashboard_totals, list_dispatches, list_orders, list_order_items, site_consumption):
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


def set_min_stock(material_id: str, min_stock: float) -> None:
    """Fija el stock mínimo de un material (el nivel que activa la alerta de reposición). No toca las existencias."""
    get_client().table("materials").update({"min_stock": float(min_stock or 0)}).eq("id", material_id).execute()
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
    df = _df(
        res.data or [],
        columns=["id", "name", "contact_name", "phone", "email", "notes", "created_at", "updated_at", "lead_time_days", "min_order_amount", "ruc", "logo"],
    )
    for col in ("lead_time_days", "min_order_amount", "ruc", "logo"):  # sin dato = None (nunca NaN), igual que en la base local
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


def set_supplier_logo(supplier_id: str, logo: str | None) -> None:
    """Guarda (o quita, con None) el logotipo del proveedor: una imagen ya reducida como data URL (ver utils/logo.py).
    Necesita el SQL del parche 066 (`046_logo_proveedor.sql`)."""
    try:
        get_client().table("suppliers").update({"logo": logo}).eq("id", supplier_id).execute()
    except Exception as exc:
        if _is_missing(exc):
            raise _need_sql("046_logo_proveedor.sql") from exc
        raise
    _invalidate_suppliers()


def upsert_supplier(
    name: str,
    contact_name: str | None,
    phone: str | None,
    email: str | None,
    notes: str | None,
    supplier_id: str | None = None,
    lead_time_days: int | None = None,
    min_order_amount: float | None = None,
    ruc: str | None = None,
) -> None:
    """`lead_time_days`: plazo de entrega habitual; `min_order_amount`: monto mínimo de compra; `ruc`: RUC del proveedor (None = sin dato).
    Necesitan el SQL de las Fases C y del parche 056; si aún no se corrió y no se indican, se guarda lo demás igual."""
    ruc = _valid_ruc(ruc, "RUC del proveedor")
    payload = {"name": name, "contact_name": contact_name, "phone": phone, "email": email, "notes": notes}
    client = get_client()

    def write(data: dict) -> None:
        if supplier_id:
            client.table("suppliers").update(data).eq("id", supplier_id).execute()
        else:
            client.table("suppliers").insert(data).execute()

    try:
        write({**payload, "lead_time_days": lead_time_days, "min_order_amount": min_order_amount, "ruc": ruc})
    except Exception as exc:
        if not _is_missing(exc):
            raise
        if ruc is not None:
            raise _need_sql("045_empresa_igv.sql") from exc
        try:
            write({**payload, "lead_time_days": lead_time_days, "min_order_amount": min_order_amount})
        except Exception as inner:
            if not _is_missing(inner):
                raise
            if lead_time_days is not None or min_order_amount is not None:
                raise _need_sql("042_fase_c.sql") from inner
            write(payload)
    _invalidate_suppliers()


def _valid_ruc(value: str | None, label: str = "RUC") -> str | None:
    """RUC limpio (11 dígitos) o None si está vacío; lanza ValueError si no es válido."""
    cleaned = ruc_rules.clean(value)
    problems = ruc_rules.issues(cleaned, label)
    if problems:
        raise ValueError(problems[0])
    return cleaned or None


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_company() -> dict:
    """Datos de facturación de la empresa (razón social, nombre comercial, RUC, dirección fiscal). Vacíos si aún no se cargaron."""
    keys = ["legal_name", "trade_name", "ruc", "fiscal_address", "updated_by", "updated_at"]
    try:
        rows = get_client().table("company_profile").select(",".join(keys)).limit(1).execute().data
    except Exception as exc:
        if _is_missing(exc):
            return dict.fromkeys(keys)
        raise
    return {k: rows[0].get(k) for k in keys} if rows else dict.fromkeys(keys)


def set_company(legal_name: str | None, trade_name: str | None, ruc: str | None, fiscal_address: str | None, actor: str | None = None) -> None:
    """Guarda los datos de facturación de la empresa (una sola ficha). El RUC debe ser válido."""
    ruc = _valid_ruc(ruc, "RUC de la empresa")
    row = {
        "singleton": True, "legal_name": (legal_name or "").strip() or None, "trade_name": (trade_name or "").strip() or None, "ruc": ruc,
        "fiscal_address": (fiscal_address or "").strip() or None, "updated_by": actor, "updated_at": "now()",
    }
    from datetime import datetime, timezone

    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        get_client().table("company_profile").upsert(row, on_conflict="singleton").execute()
    except Exception as exc:
        if _is_missing(exc):
            raise _need_sql("045_empresa_igv.sql") from exc
        raise _friendly(exc) from exc
    get_company.clear()


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
    links = _df(res.data or [], columns=["id", "supplier_id", "material_id", "available", "price", "price_updated_at"])

    if materials.empty:
        return materials.assign(link_id=None, offered=False, available=False, price=None)

    merged = materials.merge(
        links[["material_id", "id", "available", "price", "price_updated_at"]].rename(columns={"id": "link_id"}),
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


def update_project_site(site_id: str, name: str, address: str | None, latitude: float | None, longitude: float | None) -> None:
    """Cambia nombre, dirección y ubicación de una obra; sus órdenes, presupuestos y trabajadores siguen unidos a ella."""
    try:
        get_client().table("project_sites").update({"name": name, "address": address, "latitude": latitude, "longitude": longitude}).eq("id", site_id).execute()
    except Exception as exc:
        raise _friendly(exc) from exc
    list_project_sites.clear()
    list_workers.clear()
    _invalidate_orders()


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
        .select("supplier_id,material_id,available,price,price_updated_at,suppliers(name),materials(category,name)")
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
                "price_updated_at": row.get("price_updated_at"),
            }
        )
    columns = ["supplier_id", "supplier_name", "material_id", "category", "material_name", "available", "price", "price_updated_at"]
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
                "subtotal": sum(float(i["quantity"]) * float(i["unit_price"]) for i in items),
                "items_count": len(items),
            }
        )
    columns = [
        "id", "code", "supplier_id", "supplier_name", "project_site_id", "site_name",
        "status", "notes", "created_at", "expected_date", "sent_at", "currency", "exchange_rate", "tax_rate", "prices_include_tax", "payment_terms", "batch_code",
        "subtotal", "net", "tax", "total", "subtotal_base", "total_base", "items_count",
    ]
    df = _df(rows, columns=[c for c in columns if c not in ("net", "tax", "total", "subtotal_base", "total_base")]) if rows else _df(columns=columns)
    if df.empty:
        return _df(columns=columns)
    df["currency"] = df["currency"].fillna(money.BASE)  # antes del SQL de la Fase B no existen estas columnas
    df = money.add_amounts(df)
    return _clean(df[columns])


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


def _terms_payload(terms: dict) -> dict:
    """Condiciones de la orden listas para guardar. «Precios con IGV incluido» y la condición de pago solo se envían
    cuando tienen valor, para que una orden común se guarde igual antes de correr el SQL del parche 056."""
    payload = dict(terms)
    if not payload.get("prices_include_tax"):
        payload.pop("prices_include_tax", None)
    if not payload.get("payment_terms"):
        payload.pop("payment_terms", None)
    return payload


def create_order(
    supplier_id: str, supplier_name: str, project_site_id: str | None, notes: str | None, items: list[dict], terms: dict | None = None,
    batch_code: str | None = None,
) -> str:
    """Crea la orden con sus líneas y devuelve su código (OC-0001, OC-0002...).
    `terms`: fecha prometida, moneda, tipo de cambio e IGV (ver utils/money.py). `batch_code`: el pedido (PD-0001) al que pertenece."""
    terms = money.normalize_terms(terms)
    client = get_client()
    existing = client.table("purchase_orders").select("code").execute().data or []
    numbers = [int(r["code"].split("-")[1]) for r in existing if r["code"].startswith("OC-") and r["code"].split("-")[1].isdigit()]
    code = f"OC-{(max(numbers) if numbers else 0) + 1:04d}"

    payload = {"code": code, "supplier_id": supplier_id, "supplier_name": supplier_name, "project_site_id": project_site_id, "notes": notes}
    if not money.is_default(terms):  # solo se envían las columnas nuevas si hacen falta (así funciona antes del SQL)
        payload.update(_terms_payload(terms))
    if batch_code:
        payload["batch_code"] = batch_code
    try:
        res = client.table("purchase_orders").insert(payload).execute()
    except Exception as exc:
        if _is_missing(exc):
            raise (_need_sql("047_pedido_varios_proveedores.sql") if batch_code else _phase_b(exc)) from exc
        raise
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


def next_batch_code() -> str:
    """El siguiente código de pedido (PD-0001, PD-0002...). Necesita el SQL del parche 072 (`047_pedido_varios_proveedores.sql`)."""
    try:
        rows = get_client().table("purchase_orders").select("batch_code").not_.is_("batch_code", "null").execute().data or []
    except Exception as exc:
        if _is_missing(exc):
            raise _need_sql("047_pedido_varios_proveedores.sql") from exc
        raise
    numbers = [int(r["batch_code"].split("-")[1]) for r in rows if str(r["batch_code"]).startswith("PD-") and r["batch_code"].split("-")[1].isdigit()]
    return f"PD-{(max(numbers) if numbers else 0) + 1:04d}"


def set_order_status(order_id: str, status: str) -> None:
    """Cambia el estado de la orden. Al pasar a «enviada» anota cuándo se envió (`sent_at`)."""
    from datetime import datetime, timezone

    table = get_client().table("purchase_orders")
    if status == "enviada":
        try:
            current = table.select("sent_at").eq("id", order_id).limit(1).execute().data
            keep = current and current[0].get("sent_at")
            table.update({"status": status, **({} if keep else {"sent_at": datetime.now(timezone.utc).isoformat()})}).eq("id", order_id).execute()
            _invalidate_orders()
            return
        except Exception as exc:
            if not _is_missing(exc):
                raise
            # el SQL de la Fase C aún no se corrió: se cambia solo el estado
    table.update({"status": status}).eq("id", order_id).execute()
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


def update_order(order_id: str, project_site_id: str | None, notes: str | None, items: list[dict], terms: dict | None = None) -> None:
    """Edita obra, notas, condiciones (si se pasan `terms`) y líneas de una orden que todavía no recibió material.
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
    changes = {"project_site_id": project_site_id, "notes": notes}
    if terms is not None:
        changes.update(money.normalize_terms(terms))
    try:
        client.table("purchase_orders").update(changes).eq("id", order_id).execute()
    except Exception as exc:
        if not _is_missing(exc):
            raise
        legacy = {k: v for k, v in changes.items() if k not in ("prices_include_tax", "payment_terms")}
        if legacy == changes or changes.get("prices_include_tax") or changes.get("payment_terms"):
            raise _phase_b(exc) from exc  # hay datos nuevos que no se pueden guardar sin el SQL
        try:  # solo traía los valores por omisión de las columnas nuevas: se guarda lo demás
            client.table("purchase_orders").update(legacy).eq("id", order_id).execute()
        except Exception as inner:
            if _is_missing(inner):
                raise _phase_b(inner) from inner
            raise
    _invalidate_orders()


def _invalidate_orders() -> None:
    list_receipts.clear()
    list_orders.clear()
    list_order_items.clear()
    list_movements.clear()
    stock_levels.clear()
    dashboard_totals.clear()


def receive_order_items(order_id: str, receipts: dict[str, float], actor: str | None = None, receipt: dict | None = None) -> str:
    """Registra lo recibido por línea (id de línea -> cantidad que llegó ahora),
    genera las entradas de stock y deja la orden en 'parcial' o 'recibida'.
    Usa la función `receive_order` de la base (todo o nada); si todavía no se corrió el
    SQL del parche 036, usa un respaldo en Python que valida antes de escribir.
    `receipt`: datos del documento ({"delivered_by", "document_ref", "notes"}); necesita el SQL de la Fase B."""
    client = get_client()
    clean = {k: float(v) for k, v in receipts.items() if v and float(v) > 0}
    receipt = {k: (v or "").strip() or None for k, v in (receipt or {}).items()}
    has_doc = any(receipt.values())
    params = {"p_order_id": order_id, "p_receipts": clean, "p_actor": actor}
    if has_doc:
        params.update({"p_delivered_by": receipt.get("delivered_by"), "p_document_ref": receipt.get("document_ref"), "p_notes": receipt.get("notes")})
    try:
        res = client.rpc("receive_order", params).execute()
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
    receipt_id = None
    if clean:
        try:
            receipt_id = client.table("order_receipts").insert(
                {"order_id": order_id, "delivered_by": receipt.get("delivered_by"), "document_ref": receipt.get("document_ref"), "notes": receipt.get("notes"), "actor": actor}
            ).execute().data[0]["id"]
        except Exception as exc:
            if not _is_missing(exc):
                raise _friendly(exc) from exc
            if has_doc:
                raise _phase_b(exc) from exc  # no se puede guardar el documento sin la tabla
    movements, pending = [], False
    doc_text = f" · {receipt['document_ref']}" if receipt.get("document_ref") else ""
    for item in items:
        received = float(item.get("received_qty") or 0)
        arrived = clean.get(item["id"], 0.0)
        if arrived > 0 and item.get("material_id"):
            movement = {"material_id": item["material_id"], "kind": "entrada", "quantity": arrived, "note": f"Recepción {code}{doc_text}", "order_id": order_id, "actor": actor}
            if receipt_id:
                movement["receipt_id"] = receipt_id
            movements.append(movement)
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

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_receipts(order_id: str | None = None) -> pd.DataFrame:
    """Recepciones registradas de una orden (o de todas si no se indica), la más reciente primero."""
    columns = ["id", "order_id", "received_at", "delivered_by", "document_ref", "notes", "actor", "lines_count"]

    def build():
        query = get_client().table("order_receipts").select("*, stock_movements(count)").order("received_at", desc=True).order("id")
        return query.eq("order_id", order_id) if order_id else query

    try:
        data = _select_all(build)
    except Exception as exc:
        if _is_missing(exc):
            return _df(columns=columns)
        raise
    rows = [{**{k: v for k, v in row.items() if k != "stock_movements"}, "lines_count": _embedded_count(row.get("stock_movements"))} for row in data]
    return _df(rows, columns=columns)


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
def list_movements(project_site_id: str | None = None, limit: int = 500, material_id: str | None = None) -> pd.DataFrame:
    """Movimientos de stock, el más reciente primero. Se pueden filtrar por obra y/o por material."""
    columns = [
        "id", "material_id", "material_name", "category", "unit", "project_site_id", "site_name",
        "kind", "quantity", "note", "order_code", "actor", "created_at", "movement_type", "voucher_code", "requested_by", "count_code", "stage",
    ]

    def fetch(select: str):
        def build():
            query = get_client().table("stock_movements").select(select).order("created_at", desc=True).order("id", desc=True)
            if project_site_id:
                query = query.eq("project_site_id", project_site_id)
            return query.eq("material_id", material_id) if material_id else query

        return _select_all(build, limit=limit)

    base = "*, materials(name,category,metric_label), project_sites(name), purchase_orders(code)"
    data = None
    for extra in (", dispatch_vouchers(code,requested_by), inventory_counts(code)", ", dispatch_vouchers(code,requested_by)", ""):
        try:
            data = fetch(base + extra)
            break
        except Exception as exc:
            if not _is_missing(exc):
                raise
    if data is None:  # ni la tabla base responde: dejar que el error real salga
        data = fetch(base)
    rows = []
    for row in data:
        material = row.pop("materials", None) or {}
        site = row.pop("project_sites", None) or {}
        order = row.pop("purchase_orders", None) or {}
        voucher = row.pop("dispatch_vouchers", None) or {}
        count = row.pop("inventory_counts", None) or {}
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
                "count_code": count.get("code"),
                "stage": row.get("stage"),
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
    stage: str | None = None,
) -> str:
    """Despacha material del almacén a una obra con su vale de salida (VS-0001...). `stage`: etapa de la obra (opcional).
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
    stage = (stage or "").strip() or None
    if stage:
        params["p_stage"] = stage
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
    voucher_row = {
        "code": code, "project_site_id": project_site_id, "site_name": site[0]["name"], "worker_id": worker_id,
        "requested_by": (requested_by or "").strip() or None, "note": (note or "").strip() or None, "actor": actor,
    }
    if stage:
        voucher_row["stage"] = stage
    try:
        voucher = client.table("dispatch_vouchers").insert(voucher_row).execute().data[0]
    except Exception as exc:
        if stage and _is_missing(exc):
            raise _phase_b(exc) from exc
        raise _friendly(exc) from exc
    try:
        client.table("stock_movements").insert(
            [
                {
                    "material_id": l["material_id"], "project_site_id": project_site_id, "kind": "salida", "quantity": float(l["quantity"]),
                    "note": l.get("note") or f"Despacho {code}", "actor": actor, "voucher_id": voucher["id"], "movement_type": "despacho",
                    **({"stage": stage} if stage else {}),
                }
                for l in lines
            ]
        ).execute()
    except Exception as exc:
        client.table("dispatch_vouchers").delete().eq("id", voucher["id"]).execute()  # no dejar un vale sin movimientos
        raise _friendly(exc) from exc
    _invalidate_stock()
    return code


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_dispatches(limit: int = 200) -> pd.DataFrame:
    columns = ["id", "code", "project_site_id", "site_name", "worker_id", "requested_by", "note", "actor", "created_at", "stage", "lines_count"]
    try:
        data = get_client().table("dispatch_vouchers").select("*, stock_movements(count)").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        if _is_missing(exc):
            return _df(columns=columns)
        raise
    rows = [{**{k: v for k, v in row.items() if k != "stock_movements"}, "lines_count": _embedded_count(row.get("stock_movements"))} for row in data]
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
def site_consumption(project_site_id: str | None = None, material_id: str | None = None) -> pd.DataFrame:
    """Consumo neto por obra, material y etapa (despachado − devuelto), ya sumado por la base (vista `site_consumption`).
    Columnas: project_site_id, material_id, stage ('' = sin etapa), material_name, category, unit, quantity.
    Solo filas con cantidad distinta de 0. Reglas en utils/consumption.py. Si la vista aún no existe
    (SQL de la Fase E pendiente), lo calcula con los movimientos."""
    columns = ["project_site_id", "material_id", "stage", "material_name", "category", "unit", "quantity"]
    client = get_client()

    def build():
        query = client.table("site_consumption").select("*").order("project_site_id").order("material_id").order("stage")
        if project_site_id:
            query = query.eq("project_site_id", project_site_id)
        return query.eq("material_id", material_id) if material_id else query

    try:
        df = _df(_select_all(build), columns=columns)
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
        return df
    except Exception as exc:
        if not _is_missing(exc):
            raise

    def build_moves():
        query = client.table("stock_movements").select("material_id,project_site_id,kind,quantity,movement_type,stage").not_.is_("project_site_id", "null").order("id")
        if project_site_id:
            query = query.eq("project_site_id", project_site_id)
        return query.eq("material_id", material_id) if material_id else query

    totals: dict[tuple, float] = {}
    for move in _select_all(build_moves):
        amount = consumption.site_quantity(move)
        if amount:
            key = (move["project_site_id"], move["material_id"], move.get("stage") or "")
            totals[key] = totals.get(key, 0.0) + amount
    info = list_materials().set_index("id").to_dict("index")
    rows = [
        {
            "project_site_id": site, "material_id": mid, "stage": stage, "material_name": info.get(mid, {}).get("name"),
            "category": info.get(mid, {}).get("category"), "unit": info.get(mid, {}).get("metric_label"), "quantity": qty,
        }
        for (site, mid, stage), qty in totals.items() if abs(qty) > 1e-12
    ]
    return _df(rows, columns=columns)


def _net_dispatched(project_site_id: str) -> dict[str, float]:
    """{material_id: despachado a la obra − devuelto por la obra}, leído directo de la base (sin caché)."""
    rows = _select_all(
        lambda: get_client().table("stock_movements").select("material_id,kind,quantity,movement_type,project_site_id").eq("project_site_id", project_site_id).order("id")
    )
    return consumption.net_by_material(rows)


def create_return(
    project_site_id: str, returned_by: str | None, note: str | None, lines: list[dict], actor: str | None, stage: str | None = None,
) -> int:
    """Devuelve material de una obra al almacén (suma al stock). No se puede devolver más de lo
    que la obra tiene (despachado − ya devuelto). `lines`: [{"material_id", "quantity", "note"?}].
    Todo o nada (un solo insert). Devuelve cuántos materiales se devolvieron."""
    if not lines:
        raise ValueError("La devolución no tiene materiales.")
    client = get_client()
    if not client.table("project_sites").select("id").eq("id", project_site_id).limit(1).execute().data:
        raise ValueError("La obra no existe.")
    wanted: dict[str, float] = {}
    for line in lines:
        if not line["quantity"] or line["quantity"] <= 0:
            raise ValueError("Todas las cantidades deben ser mayores que 0.")
        wanted[line["material_id"]] = wanted.get(line["material_id"], 0.0) + float(line["quantity"])
    held = _net_dispatched(project_site_id)
    names = list_materials().set_index("id")["name"].to_dict()
    for material_id, qty in wanted.items():
        if qty > held.get(material_id, 0.0) + 1e-9:
            raise ValueError(
                f"De «{names.get(material_id, material_id)}» la obra solo tiene {max(held.get(material_id, 0.0), 0):g} "
                f"(despachado menos devuelto) y se intentan devolver {qty:g}."
            )
    who = (returned_by or "").strip()
    base = (note or "").strip()
    rows = [
        {
            "material_id": line["material_id"], "project_site_id": project_site_id, "kind": "entrada", "quantity": float(line["quantity"]),
            "note": " · ".join(x for x in [f"Devuelve {who}" if who else "Devolución de obra", base, line.get("note")] if x),
            "actor": actor, "movement_type": "devolucion", **({"stage": stage.strip()} if (stage or "").strip() else {}),
        }
        for line in lines
    ]
    try:
        client.table("stock_movements").insert(rows).execute()
    except Exception as exc:
        raise _friendly(exc) from exc
    _invalidate_stock()
    return len(lines)


def create_inventory_count(lines: list[dict], note: str | None, actor: str | None) -> str:
    """Toma de inventario físico. `lines`: [{"material_id", "counted_qty", "reason"?}] con lo contado en
    estantería. Compara con el stock del sistema, guarda el conteo y genera un movimiento de ajuste por
    cada diferencia (entrada si sobra, salida si falta). Devuelve el código (CT-0001)."""
    if not lines:
        raise ValueError("No hay materiales contados.")
    for line in lines:
        if float(line["counted_qty"]) < 0:
            raise ValueError("Lo contado no puede ser negativo.")
    client = get_client()
    stock_levels.clear()
    system_stock = stock_levels().set_index("material_id")["stock"].astype(float).to_dict()
    try:
        codes = [r["code"] for r in (client.table("inventory_counts").select("code").execute().data or [])]
    except Exception as exc:
        if _is_missing(exc):
            raise ValueError("Falta correr el SQL de la Fase B en Supabase (db/migrations/041_fase_b.sql).") from exc
        raise
    number = max([int(c.split("-")[1]) for c in codes if c.startswith("CT-") and c.split("-")[1].isdigit()] or [0]) + 1
    code = f"CT-{number:04d}"
    count = client.table("inventory_counts").insert({"code": code, "note": (note or "").strip() or None, "actor": actor}).execute().data[0]
    try:
        detail, moves = [], []
        for line in lines:
            counted = float(line["counted_qty"])
            system = float(system_stock.get(line["material_id"], 0.0))
            diff = round(counted - system, 6)
            reason = (line.get("reason") or "").strip()
            detail.append(
                {"count_id": count["id"], "material_id": line["material_id"], "system_qty": system, "counted_qty": counted, "difference": diff, "reason": reason or None}
            )
            if abs(diff) > 1e-9:
                moves.append(
                    {
                        "material_id": line["material_id"], "kind": "entrada" if diff > 0 else "salida", "quantity": abs(diff),
                        "note": f"Conteo {code}: sistema {system:g}, contado {counted:g}" + (f" · {reason}" if reason else ""),
                        "actor": actor, "movement_type": "conteo", "count_id": count["id"],
                    }
                )
        client.table("inventory_count_lines").insert(detail).execute()
        if moves:
            client.table("stock_movements").insert(moves).execute()
    except Exception as exc:
        client.table("inventory_counts").delete().eq("id", count["id"]).execute()  # nada a medias
        raise _friendly(exc) from exc
    _invalidate_stock()
    list_inventory_counts.clear()
    return code


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_inventory_counts(limit: int = 100) -> pd.DataFrame:
    columns = ["id", "code", "note", "actor", "created_at", "lines_count", "adjusted_count"]
    try:
        data = get_client().table("inventory_counts").select("*, inventory_count_lines(difference)").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        if _is_missing(exc):
            return _df(columns=columns)
        raise
    rows = []
    for row in data:
        detail = row.pop("inventory_count_lines", None) or []
        rows.append({**row, "lines_count": len(detail), "adjusted_count": sum(1 for d in detail if abs(float(d["difference"])) > 1e-9)})
    return _df(rows, columns=columns)


def list_count_lines(count_id: str) -> pd.DataFrame:
    columns = ["id", "material_id", "material_name", "category", "unit", "system_qty", "counted_qty", "difference", "reason"]
    data = (
        get_client().table("inventory_count_lines").select("*, materials(name,category,metric_label)").eq("count_id", count_id).execute().data or []
    )
    rows = []
    for row in data:
        material = row.pop("materials", None) or {}
        rows.append(
            {
                "id": row["id"], "material_id": row["material_id"], "material_name": material.get("name"),
                "category": material.get("category"), "unit": material.get("metric_label"),
                "system_qty": float(row["system_qty"]), "counted_qty": float(row["counted_qty"]),
                "difference": float(row["difference"]), "reason": row.get("reason"),
            }
        )
    df = _df(rows, columns=columns)
    return df.sort_values("material_name").reset_index(drop=True) if not df.empty else df


def _storage():
    """Depósito privado de adjuntos. Solo la clave de servicio puede usarlo (la pública no tiene permisos)."""
    if not using_service_key():
        raise ValueError(
            "Los adjuntos necesitan la clave de servicio de Supabase (SUPABASE_SERVICE_KEY). Configúrala en los secrets de la app."
        )
    return get_client().storage


def add_attachment(entity_type: str, entity_id: str, filename: str, data: bytes, uploaded_by: str | None = None) -> str:
    """Guarda un documento adjunto (PDF o imagen, hasta 10 MB) de una orden, vale o conteo. Devuelve su id."""
    safe_name, content_type = attach_rules.validate(filename, len(data))
    path = attach_rules.storage_path(entity_type, entity_id, safe_name)
    storage = _storage()
    options = {"content-type": content_type, "upsert": "false"}
    try:
        storage.from_(attach_rules.BUCKET).upload(path, data, options)
    except Exception as exc:
        if "not found" not in str(exc).lower() and "404" not in str(exc):
            raise _friendly(exc) from exc
        try:  # el depósito aún no existe (SQL de la Fase B pendiente): la clave de servicio puede crearlo
            storage.create_bucket(attach_rules.BUCKET, options={"public": False})
            storage.from_(attach_rules.BUCKET).upload(path, data, options)
        except Exception as inner:
            raise _friendly(inner) from inner
    try:
        row = get_client().table("attachments").insert(
            {
                "entity_type": entity_type, "entity_id": entity_id, "filename": safe_name, "content_type": content_type,
                "size_bytes": len(data), "storage_path": path, "uploaded_by": uploaded_by,
            }
        ).execute().data[0]
    except Exception as exc:
        try:
            storage.from_(attach_rules.BUCKET).remove([path])  # no dejar el archivo huérfano
        except Exception:
            pass
        if _is_missing(exc):
            raise _phase_b(exc) from exc
        raise _friendly(exc) from exc
    list_attachments.clear()
    return row["id"]


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_attachments(entity_type: str, entity_id: str) -> pd.DataFrame:
    columns = ["id", "entity_type", "entity_id", "filename", "content_type", "size_bytes", "uploaded_by", "created_at"]
    try:
        data = (
            get_client().table("attachments").select(",".join(columns)).eq("entity_type", entity_type).eq("entity_id", entity_id)
            .order("created_at", desc=True).execute().data or []
        )
    except Exception as exc:
        if _is_missing(exc):
            return _df(columns=columns)
        raise
    return _df(data, columns=columns)


def read_attachment(attachment_id: str) -> tuple[dict, bytes]:
    """(datos del adjunto, contenido del archivo)."""
    rows = get_client().table("attachments").select("id,filename,content_type,size_bytes,storage_path").eq("id", attachment_id).limit(1).execute().data
    if not rows:
        raise ValueError("El documento ya no existe.")
    try:
        content = _storage().from_(attach_rules.BUCKET).download(rows[0]["storage_path"])
    except ValueError:
        raise
    except Exception as exc:
        raise _friendly(exc) from exc
    return rows[0], content


def delete_attachment(attachment_id: str) -> None:
    rows = get_client().table("attachments").select("storage_path").eq("id", attachment_id).limit(1).execute().data
    if rows:
        try:
            _storage().from_(attach_rules.BUCKET).remove([rows[0]["storage_path"]])
        except ValueError:
            raise
        except Exception:
            pass  # si el archivo ya no estaba, igual se quita el registro
    get_client().table("attachments").delete().eq("id", attachment_id).execute()
    list_attachments.clear()


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
                "stage": row.get("stage") or "",
            }
        )
    columns = ["id", "project_site_id", "material_id", "category", "material_name", "unit", "planned_qty", "planned_unit_price", "stage"]
    df = _df(rows, columns=columns)
    return df.sort_values(["stage", "category", "material_name"]).reset_index(drop=True) if not df.empty else df


def set_budget(project_site_id: str, material_id: str, planned_qty: float, planned_unit_price: float, stage: str = "") -> None:
    """Cantidad y precio previstos de un material en una obra. `stage`: etapa de la obra (vacío = sin etapa);
    el mismo material puede presupuestarse en varias etapas."""
    stage = (stage or "").strip()
    row = {"project_site_id": project_site_id, "material_id": material_id, "planned_qty": planned_qty, "planned_unit_price": planned_unit_price}
    table = get_client().table("site_budgets")
    try:
        table.upsert({**row, "stage": stage}, on_conflict="project_site_id,material_id,stage").execute()
    except Exception as exc:
        if not _is_missing(exc) and "42P10" not in f"{getattr(exc, 'code', '')} {exc}":
            raise _friendly(exc) from exc
        if stage:  # sin el SQL de la Fase B no existe la columna de etapa
            raise _phase_b(exc) from exc
        table.upsert(row, on_conflict="project_site_id,material_id").execute()
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

def log_action(
    actor: str, summary: str, entity_type: str | None = None, entity_id: str | None = None, changes: list[dict] | None = None,
) -> None:
    """Anota una acción en el historial. `changes`: [{"field", "before", "after"}] (ver utils/audit.py).
    Sin el SQL de la Fase F el detalle estructurado no se puede guardar, pero el resumen ya lo incluye en texto."""
    table = get_client().table("audit_log")
    payload = {"actor": actor, "summary": summary}
    if entity_type or entity_id or changes:
        try:
            table.insert({**payload, "entity_type": entity_type, "entity_id": entity_id, "changes": changes or None}).execute()
            list_audit.clear()
            return
        except Exception as exc:
            if not _is_missing(exc):
                raise
    table.insert(payload).execute()
    list_audit.clear()


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_audit(limit: int = 300) -> pd.DataFrame:
    res = get_client().table("audit_log").select("*").order("created_at", desc=True).limit(limit).execute()
    df = _df(res.data or [], columns=["id", "actor", "summary", "created_at", "entity_type", "entity_id", "changes"])
    df["changes"] = df["changes"].map(audit.from_json).astype(object)
    return df


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def dashboard_totals() -> dict:
    """Contadores del dashboard. Usa la vista `dashboard_stats` (una sola fila); si aún no existe
    (SQL de la Fase E pendiente), los calcula leyendo las tablas."""
    try:
        rows = get_client().table("dashboard_stats").select("*").limit(1).execute().data
        if rows:
            return {k: int(v or 0) for k, v in rows[0].items()}
    except Exception as exc:
        if not _is_missing(exc):
            raise
    return _dashboard_totals_slow()


def _dashboard_totals_slow() -> dict:
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
    from utils import clock

    month = clock.now().strftime("%Y-%m")
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
    "materials", "suppliers", "supplier_materials", "users", "company_profile", "work_groups", "project_sites", "workers",
    "purchase_orders", "purchase_order_items", "order_receipts", "dispatch_vouchers", "inventory_counts", "inventory_count_lines", "stock_movements",
    "site_budgets", "attendance", "audit_log", "price_history", "attachments",
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
        frame = pd.DataFrame(rows)
        for col in frame.columns:  # columnas jsonb: JSON válido en el CSV, para poder restaurarlas
            if frame[col].map(lambda v: isinstance(v, (dict, list))).any():
                frame[col] = frame[col].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        out[table] = frame
    return out
