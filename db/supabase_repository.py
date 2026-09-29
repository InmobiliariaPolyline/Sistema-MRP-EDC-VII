"""Funciones de acceso a datos sobre Supabase (materiales, proveedores y
la relación proveedor-material). Nada de lógica de interfaz aquí."""
from __future__ import annotations

from typing import Any

import pandas as pd

from db.client import get_client


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------

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


def delete_material(material_id: str) -> None:
    get_client().table("materials").delete().eq("id", material_id).execute()


def import_materials(df: pd.DataFrame) -> tuple[int, int]:
    """Crea o actualiza materiales a partir de un DataFrame con columnas
    category, name, density (opcional), metric_label. Devuelve
    (filas procesadas, filas con error)."""
    required = {"category", "name"}
    missing = required - set(c.lower() for c in df.columns)
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en el Excel: {', '.join(sorted(missing))}")

    df = df.rename(columns={c: c.lower() for c in df.columns})
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
    return ok, failed


def export_materials_df() -> pd.DataFrame:
    df = list_materials()
    return df[["category", "name", "density", "metric_label"]].rename(
        columns={"category": "category", "name": "name", "density": "density", "metric_label": "metric_label"}
    )


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

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


def delete_supplier(supplier_id: str) -> None:
    get_client().table("suppliers").delete().eq("id", supplier_id).execute()


def import_suppliers(df: pd.DataFrame) -> tuple[int, int]:
    """Crea proveedores a partir de un DataFrame con columnas name,
    contact_name, phone, email, notes (todas menos name son opcionales)."""
    df = df.rename(columns={c: c.lower() for c in df.columns})
    if "name" not in df.columns:
        raise ValueError("Falta la columna obligatoria 'name' en el Excel")

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
    return ok, failed


def export_suppliers_df() -> pd.DataFrame:
    df = list_suppliers()
    return df[["name", "contact_name", "phone", "email", "notes"]]


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
        return
    client.table("supplier_materials").upsert(
        {"supplier_id": supplier_id, "material_id": material_id, "available": available, "price": price},
        on_conflict="supplier_id,material_id",
    ).execute()
