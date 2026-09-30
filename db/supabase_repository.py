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
from utils.excel import (
    MATERIAL_ALIASES,
    MATERIAL_EXPORT_COLUMNS,
    MATERIAL_REQUIRED,
    SUPPLIER_ALIASES,
    SUPPLIER_REQUIRED,
    extract_columns,
)

_CACHE_TTL = 30  # segundos: solo evita relecturas repetidas al navegar, no es "tiempo real"


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_materials() -> pd.DataFrame:
    res = get_client().table("materials").select("*").order("category").order("name").execute()
    return pd.DataFrame(res.data or [], columns=["id", "category", "name", "density", "metric_label", "created_at", "updated_at"])


def upsert_material(category: str, name: str, density: float | None, metric_label: str, material_id: str | None = None) -> None:
    payload: dict[str, Any] = {"category": category, "name": name, "density": density, "metric_label": metric_label}
    client = get_client()
    if material_id:
        client.table("materials").update(payload).eq("id", material_id).execute()
    else:
        client.table("materials").upsert(payload, on_conflict="category,name").execute()
    _invalidate_materials()


def delete_material(material_id: str) -> None:
    get_client().table("materials").delete().eq("id", material_id).execute()
    _invalidate_materials()


def import_materials(df: pd.DataFrame) -> tuple[int, int]:
    """Crea o actualiza materiales a partir de un DataFrame con columnas
    category, name, density (opcional), metric_label. Devuelve
    (filas procesadas, filas con error)."""
    df = extract_columns(df, MATERIAL_ALIASES, MATERIAL_REQUIRED)
    ok, failed = 0, 0
    rows = []
    for row in df.to_dict("records"):
        category = _text(row.get("category"))
        name = _text(row.get("name"))
        if not category or not name:
            failed += 1
            continue
        density_raw = row.get("density")
        density = float(density_raw) if pd.notna(density_raw) and str(density_raw).strip() != "" else None
        metric_label = _text(row.get("metric_label"))
        rows.append({"category": category, "name": name, "density": density, "metric_label": metric_label})
        ok += 1

    if rows:
        get_client().table("materials").upsert(rows, on_conflict="category,name").execute()
        _invalidate_materials()
    return ok, failed


def export_materials_df() -> pd.DataFrame:
    df = list_materials()
    return df[["category", "name", "density", "metric_label"]].rename(columns=MATERIAL_EXPORT_COLUMNS)


def _invalidate_materials() -> None:
    list_materials.clear()
    dashboard_totals.clear()
    recent_activity.clear()
    get_supplier_catalog.clear()


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def list_suppliers() -> pd.DataFrame:
    res = get_client().table("suppliers").select("*").order("name").execute()
    return pd.DataFrame(
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


def import_suppliers(df: pd.DataFrame) -> tuple[int, int]:
    """Crea proveedores a partir de un DataFrame con columnas name,
    contact_name, phone, email, notes (todas menos name son opcionales)."""
    df = extract_columns(df, SUPPLIER_ALIASES, SUPPLIER_REQUIRED)
    ok, failed = 0, 0
    rows = []
    for row in df.to_dict("records"):
        name = _text(row.get("name"))
        if not name:
            failed += 1
            continue
        rows.append(
            {
                "name": name,
                "contact_name": _clean(row.get("contact_name")),
                "phone": _clean(row.get("phone")),
                "email": _clean(row.get("email")),
                "notes": _clean(row.get("notes")),
            }
        )
        ok += 1

    if rows:
        get_client().table("suppliers").insert(rows).execute()
        _invalidate_suppliers()
    return ok, failed


def export_suppliers_df() -> pd.DataFrame:
    df = list_suppliers()
    return df[["name", "contact_name", "phone", "email", "notes"]]


def _invalidate_suppliers() -> None:
    list_suppliers.clear()
    dashboard_totals.clear()
    recent_activity.clear()
    get_supplier_catalog.clear()


def _text(value: Any) -> str:
    """Como _clean, pero para campos obligatorios: nunca devuelve None."""
    return _clean(value) or ""


def _clean(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


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
    links = pd.DataFrame(res.data or [], columns=["id", "supplier_id", "material_id", "available", "price"])

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
    dashboard_totals.clear()


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
    df = pd.DataFrame(
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
    return pd.DataFrame(res.data or [], columns=["id", "name", "created_at"])


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
    return pd.DataFrame(res.data or [], columns=["id", "name", "address", "latitude", "longitude", "created_at"])


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
    return pd.DataFrame(rows)


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
# Dashboard
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def dashboard_totals() -> dict:
    materials = list_materials()
    suppliers = list_suppliers()
    res = get_client().table("supplier_materials").select("supplier_id,material_id,available").execute()
    links = pd.DataFrame(res.data or [], columns=["supplier_id", "material_id", "available"])

    suppliers_with_available = links.loc[links["available"] == True, "supplier_id"].nunique() if not links.empty else 0  # noqa: E712
    materials_with_supplier = set(links["material_id"]) if not links.empty else set()
    materials_without_supplier = len(materials) - len([m for m in materials["id"] if m in materials_with_supplier])

    return {
        "materials": len(materials),
        "suppliers": len(suppliers),
        "suppliers_with_available": int(suppliers_with_available),
        "materials_without_supplier": int(materials_without_supplier),
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
