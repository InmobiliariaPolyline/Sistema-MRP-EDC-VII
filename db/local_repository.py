"""Misma API que supabase_repository.py, pero contra un SQLite local
(db/local.db). Se usa automáticamente cuando no hay SUPABASE_URL/SUPABASE_KEY
configurados, para poder ver y probar la interfaz sin depender de Supabase.

A diferencia de supabase_repository.py, aquí no se cachean las lecturas:
SQLite es un archivo local (sin viaje de red), así que cada consulta ya es
prácticamente instantánea y cachear solo sumaría riesgo de datos
desactualizados sin ninguna ganancia real de velocidad."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

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

            create table if not exists work_groups (
                id text primary key,
                name text not null unique,
                created_at text default (datetime('now'))
            );

            create table if not exists project_sites (
                id text primary key,
                name text not null,
                address text,
                latitude real,
                longitude real,
                created_at text default (datetime('now'))
            );

            create table if not exists workers (
                id text primary key,
                full_name text not null,
                document_id text,
                phone text,
                position text,
                work_group_id text references work_groups(id) on delete set null,
                project_site_id text references project_sites(id) on delete set null,
                user_id text references users(id) on delete set null,
                active integer not null default 1,
                created_at text default (datetime('now')),
                updated_at text default (datetime('now'))
            );

            create table if not exists purchase_orders (
                id text primary key,
                code text not null unique,
                supplier_id text references suppliers(id) on delete set null,
                supplier_name text not null,
                project_site_id text references project_sites(id) on delete set null,
                status text not null default 'pendiente',
                notes text,
                created_at text default (datetime('now')),
                updated_at text default (datetime('now'))
            );

            create table if not exists purchase_order_items (
                id text primary key,
                order_id text not null references purchase_orders(id) on delete cascade,
                material_id text references materials(id) on delete set null,
                material_name text not null,
                unit text,
                quantity real not null,
                unit_price real not null default 0,
                created_at text default (datetime('now'))
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
        if material_id:
            conn.execute(
                "update materials set category = ?, name = ?, density = ?, metric_label = ?, updated_at = datetime('now') where id = ?",
                (category, name, density, metric_label, material_id),
            )
            return
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
# Trabajadores: cuadrillas, obras y el propio catálogo de trabajadores
# ---------------------------------------------------------------------------

def list_work_groups() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query("select * from work_groups order by name", conn)
    return df.astype(object).where(pd.notnull(df), None)


def create_work_group(name: str) -> None:
    with _connect() as conn:
        conn.execute("insert into work_groups (id, name) values (?, ?)", (str(uuid.uuid4()), name))


def delete_work_group(group_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from work_groups where id = ?", (group_id,))


def list_project_sites() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query("select * from project_sites order by name", conn)
    return df.astype(object).where(pd.notnull(df), None)


def create_project_site(name: str, address: str | None, latitude: float | None, longitude: float | None) -> None:
    with _connect() as conn:
        conn.execute(
            "insert into project_sites (id, name, address, latitude, longitude) values (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), name, address, latitude, longitude),
        )


def delete_project_site(site_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from project_sites where id = ?", (site_id,))


def list_workers() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select
                w.id, w.full_name, w.document_id, w.phone, w.position, w.active,
                w.work_group_id, wg.name as group_name,
                w.project_site_id, ps.name as site_name, ps.address as site_address,
                ps.latitude, ps.longitude,
                w.user_id, u.username, u.role
            from workers w
            left join work_groups wg on wg.id = w.work_group_id
            left join project_sites ps on ps.id = w.project_site_id
            left join users u on u.id = w.user_id
            order by w.full_name
            """,
            conn,
        )
    return df.astype(object).where(pd.notnull(df), None)


def create_worker(
    full_name: str,
    document_id: str | None,
    phone: str | None,
    position: str | None,
    work_group_id: str | None,
    project_site_id: str | None,
) -> str:
    worker_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            """
            insert into workers (id, full_name, document_id, phone, position, work_group_id, project_site_id)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (worker_id, full_name, document_id, phone, position, work_group_id, project_site_id),
        )
    return worker_id


def update_worker(
    worker_id: str,
    full_name: str,
    document_id: str | None,
    phone: str | None,
    position: str | None,
    work_group_id: str | None,
    project_site_id: str | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            update workers set full_name = ?, document_id = ?, phone = ?, position = ?,
                work_group_id = ?, project_site_id = ?, updated_at = datetime('now')
            where id = ?
            """,
            (full_name, document_id, phone, position, work_group_id, project_site_id, worker_id),
        )


def delete_worker(worker_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from workers where id = ?", (worker_id,))


def grant_worker_access(worker_id: str, username: str, password_hash: str, name: str, role: str) -> None:
    user_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "insert into users (id, username, password_hash, name, role) values (?, ?, ?, ?, ?)",
            (user_id, username, password_hash, name, role),
        )
        conn.execute("update workers set user_id = ?, updated_at = datetime('now') where id = ?", (user_id, worker_id))


def revoke_worker_access(worker_id: str, user_id: str) -> None:
    with _connect() as conn:
        conn.execute("update workers set user_id = null, updated_at = datetime('now') where id = ?", (worker_id,))
        conn.execute("delete from users where id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Ofertas (qué ofrece cada proveedor y a qué precio) — para comparar precios
# y para los reportes
# ---------------------------------------------------------------------------

def list_offers() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select sm.supplier_id, s.name as supplier_name, sm.material_id,
                   m.category, m.name as material_name, sm.available, sm.price
            from supplier_materials sm
            join suppliers s on s.id = sm.supplier_id
            join materials m on m.id = sm.material_id
            order by m.category, m.name, s.name
            """,
            conn,
        )
    df["available"] = df["available"].astype(bool)
    return df.astype(object).where(pd.notnull(df), None)


# ---------------------------------------------------------------------------
# Órdenes de compra
# ---------------------------------------------------------------------------

def list_orders() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select o.id, o.code, o.supplier_id, o.supplier_name, o.project_site_id,
                   ps.name as site_name, o.status, o.notes, o.created_at,
                   coalesce((select sum(i.quantity * i.unit_price) from purchase_order_items i where i.order_id = o.id), 0) as total,
                   (select count(*) from purchase_order_items i where i.order_id = o.id) as items_count
            from purchase_orders o
            left join project_sites ps on ps.id = o.project_site_id
            order by o.created_at desc, o.code desc
            """,
            conn,
        )
    return df.astype(object).where(pd.notnull(df), None)


def list_order_items(order_id: str | None = None) -> pd.DataFrame:
    """Líneas de una orden, o de todas (con el código de su orden) si no se pasa id."""
    query = """
        select i.id, i.order_id, o.code as order_code, i.material_id, i.material_name,
               i.unit, i.quantity, i.unit_price, (i.quantity * i.unit_price) as subtotal
        from purchase_order_items i join purchase_orders o on o.id = i.order_id
    """
    params: tuple = ()
    if order_id:
        query += " where i.order_id = ?"
        params = (order_id,)
    query += " order by o.code, i.created_at, i.material_name"
    with _connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df.astype(object).where(pd.notnull(df), None)


def create_order(supplier_id: str, supplier_name: str, project_site_id: str | None, notes: str | None, items: list[dict]) -> str:
    """Crea la orden con sus líneas y devuelve su código (OC-0001, OC-0002...)."""
    order_id = str(uuid.uuid4())
    with _connect() as conn:
        codes = [row[0] for row in conn.execute("select code from purchase_orders").fetchall()]
        number = max([int(c.split("-")[1]) for c in codes if c.startswith("OC-") and c.split("-")[1].isdigit()] or [0]) + 1
        code = f"OC-{number:04d}"
        conn.execute(
            "insert into purchase_orders (id, code, supplier_id, supplier_name, project_site_id, notes) values (?, ?, ?, ?, ?, ?)",
            (order_id, code, supplier_id, supplier_name, project_site_id, notes),
        )
        for item in items:
            conn.execute(
                """
                insert into purchase_order_items (id, order_id, material_id, material_name, unit, quantity, unit_price)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), order_id, item["material_id"], item["material_name"], item.get("unit"), item["quantity"], item["unit_price"]),
            )
    return code


def set_order_status(order_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute("update purchase_orders set status = ?, updated_at = datetime('now') where id = ?", (status, order_id))


def delete_order(order_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from purchase_orders where id = ?", (order_id,))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard_totals() -> dict:
    with _connect() as conn:
        orders_open = conn.execute(
            "select count(*) from purchase_orders where status in ('pendiente', 'enviada')"
        ).fetchone()[0]
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
        "orders_open": orders_open,
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
