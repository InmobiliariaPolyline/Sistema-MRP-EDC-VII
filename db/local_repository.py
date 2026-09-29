"""Misma API que supabase_repository.py, pero contra un SQLite local
(db/local.db). Se usa automáticamente cuando no hay SUPABASE_URL/SUPABASE_KEY
configurados, para poder ver y probar la interfaz sin depender de Supabase."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "local.db"


def _init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            create table if not exists materials (
                id text primary key,
                category text not null,
                name text not null,
                density real,
                metric_label text default '',
                created_at text default (datetime('now')),
                updated_at text default (datetime('now')),
                unique (category, name)
            );

            create table if not exists suppliers (
                id text primary key,
                name text not null,
                contact_name text,
                phone text,
                email text,
                notes text,
                created_at text default (datetime('now')),
                updated_at text default (datetime('now'))
            );

            create table if not exists supplier_materials (
                id text primary key,
                supplier_id text not null references suppliers(id) on delete cascade,
                material_id text not null references materials(id) on delete cascade,
                available integer not null default 1,
                price real,
                unique (supplier_id, material_id)
            );

            create table if not exists users (
                id text primary key,
                username text not null unique,
                password_hash text not null,
                name text not null,
                role text not null default 'operador',
                active integer not null default 1,
                created_at text default (datetime('now')),
                updated_at text default (datetime('now'))
            );
            """
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("pragma foreign_keys = on")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_init_db()


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------

def list_materials() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query("select * from materials order by category, name", conn)
    for col in ["id", "category", "name", "density", "metric_label", "created_at", "updated_at"]:
        if col not in df.columns:
            df[col] = None
    return df.astype(object).where(pd.notnull(df), None)


def upsert_material(category: str, name: str, density: float | None, metric_label: str, material_id: str | None = None) -> None:
    with _connect() as conn:
        existing = conn.execute("select id from materials where category = ? and name = ?", (category, name)).fetchone()
        if existing:
            conn.execute(
                "update materials set density = ?, metric_label = ?, updated_at = datetime('now') where id = ?",
                (density, metric_label, existing[0]),
            )
        else:
            conn.execute(
                "insert into materials (id, category, name, density, metric_label) values (?, ?, ?, ?, ?)",
                (material_id or str(uuid.uuid4()), category, name, density, metric_label),
            )


def delete_material(material_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from materials where id = ?", (material_id,))


def import_materials(df: pd.DataFrame) -> tuple[int, int]:
    required = {"category", "name"}
    missing = required - set(c.lower() for c in df.columns)
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en el Excel: {', '.join(sorted(missing))}")

    df = df.rename(columns={c: c.lower() for c in df.columns})
    ok, failed = 0, 0
    for row in df.to_dict("records"):
        category = _text(row.get("category"))
        name = _text(row.get("name"))
        if not category or not name:
            failed += 1
            continue
        density_raw = row.get("density")
        density = float(density_raw) if pd.notna(density_raw) and str(density_raw).strip() != "" else None
        metric_label = _text(row.get("metric_label"))
        upsert_material(category, name, density, metric_label)
        ok += 1
    return ok, failed


def export_materials_df() -> pd.DataFrame:
    df = list_materials()
    return df[["category", "name", "density", "metric_label"]]


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

def list_suppliers() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query("select * from suppliers order by name", conn)
    for col in ["id", "name", "contact_name", "phone", "email", "notes", "created_at", "updated_at"]:
        if col not in df.columns:
            df[col] = None
    return df.astype(object).where(pd.notnull(df), None)


def upsert_supplier(
    name: str,
    contact_name: str | None,
    phone: str | None,
    email: str | None,
    notes: str | None,
    supplier_id: str | None = None,
) -> None:
    with _connect() as conn:
        if supplier_id:
            conn.execute(
                "update suppliers set name = ?, contact_name = ?, phone = ?, email = ?, notes = ?, updated_at = datetime('now') where id = ?",
                (name, contact_name, phone, email, notes, supplier_id),
            )
        else:
            conn.execute(
                "insert into suppliers (id, name, contact_name, phone, email, notes) values (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), name, contact_name, phone, email, notes),
            )


def delete_supplier(supplier_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from suppliers where id = ?", (supplier_id,))


def import_suppliers(df: pd.DataFrame) -> tuple[int, int]:
    df = df.rename(columns={c: c.lower() for c in df.columns})
    if "name" not in df.columns:
        raise ValueError("Falta la columna obligatoria 'name' en el Excel")

    ok, failed = 0, 0
    for row in df.to_dict("records"):
        name = _text(row.get("name"))
        if not name:
            failed += 1
            continue
        upsert_supplier(
            name,
            _clean(row.get("contact_name")),
            _clean(row.get("phone")),
            _clean(row.get("email")),
            _clean(row.get("notes")),
        )
        ok += 1
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
    materials = list_materials()
    with _connect() as conn:
        links = pd.read_sql_query(
            "select id as link_id, material_id, available, price from supplier_materials where supplier_id = ?",
            conn,
            params=(supplier_id,),
        )

    if materials.empty:
        return materials.assign(link_id=None, offered=False, available=False, price=None)

    merged = materials.merge(links, left_on="id", right_on="material_id", how="left")
    merged["offered"] = merged["link_id"].notna()
    merged["available"] = merged["available"].fillna(0).astype(bool)
    return merged.drop(columns=["material_id"])


def set_supplier_material(supplier_id: str, material_id: str, offered: bool, available: bool, price: float | None) -> None:
    with _connect() as conn:
        if not offered:
            conn.execute(
                "delete from supplier_materials where supplier_id = ? and material_id = ?",
                (supplier_id, material_id),
            )
            return
        existing = conn.execute(
            "select id from supplier_materials where supplier_id = ? and material_id = ?",
            (supplier_id, material_id),
        ).fetchone()
        if existing:
            conn.execute(
                "update supplier_materials set available = ?, price = ? where id = ?",
                (int(available), price, existing[0]),
            )
        else:
            conn.execute(
                "insert into supplier_materials (id, supplier_id, material_id, available, price) values (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), supplier_id, material_id, int(available), price),
            )


# ---------------------------------------------------------------------------
# Usuarios (login)
# ---------------------------------------------------------------------------

def count_users() -> int:
    with _connect() as conn:
        return conn.execute("select count(*) from users").fetchone()[0]


def list_users() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query("select * from users order by name", conn)
    for col in ["id", "username", "password_hash", "name", "role", "active", "created_at", "updated_at"]:
        if col not in df.columns:
            df[col] = None
    df = df.astype(object).where(pd.notnull(df), None)
    df["active"] = df["active"].apply(lambda v: bool(v) if v is not None else True)
    return df


def get_user_by_username(username: str) -> dict | None:
    with _connect() as conn:
        df = pd.read_sql_query("select * from users where username = ?", conn, params=(username,))
    if df.empty:
        return None
    row = df.astype(object).where(pd.notnull(df), None).to_dict("records")[0]
    row["active"] = bool(row["active"]) if row["active"] is not None else True
    return row


def create_user(username: str, password_hash: str, name: str, role: str) -> None:
    with _connect() as conn:
        conn.execute(
            "insert into users (id, username, password_hash, name, role) values (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), username, password_hash, name, role),
        )


def set_user_active(user_id: str, active: bool) -> None:
    with _connect() as conn:
        conn.execute("update users set active = ?, updated_at = datetime('now') where id = ?", (int(active), user_id))


def delete_user(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from users where id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard_totals() -> dict:
    with _connect() as conn:
        materials = conn.execute("select count(*) from materials").fetchone()[0]
        suppliers = conn.execute("select count(*) from suppliers").fetchone()[0]
        suppliers_with_available = conn.execute(
            "select count(distinct supplier_id) from supplier_materials where available = 1"
        ).fetchone()[0]
        materials_without_supplier = conn.execute(
            """
            select count(*) from materials m
            where not exists (
                select 1 from supplier_materials sm where sm.material_id = m.id
            )
            """
        ).fetchone()[0]
    return {
        "materials": materials,
        "suppliers": suppliers,
        "suppliers_with_available": suppliers_with_available,
        "materials_without_supplier": materials_without_supplier,
    }


def recent_activity(limit: int = 6) -> list[dict]:
    """Últimos materiales y proveedores agregados, mezclados por fecha."""
    with _connect() as conn:
        materials = conn.execute(
            "select name, category, created_at from materials order by created_at desc limit ?", (limit,)
        ).fetchall()
        suppliers = conn.execute(
            "select name, phone, created_at from suppliers order by created_at desc limit ?", (limit,)
        ).fetchall()

    items = [
        {"name": name, "sub": category or "Material", "kind": "Material", "created_at": created_at}
        for name, category, created_at in materials
    ] + [
        {"name": name, "sub": phone or "Proveedor", "kind": "Proveedor", "created_at": created_at}
        for name, phone, created_at in suppliers
    ]
    items.sort(key=lambda it: it["created_at"] or "", reverse=True)
    return items[:limit]
