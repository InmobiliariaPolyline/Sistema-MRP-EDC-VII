"""Misma API que supabase_repository.py, pero contra un SQLite local
(db/local.db). Se usa automáticamente cuando no hay SUPABASE_URL/SUPABASE_KEY
configurados, para poder ver y probar la interfaz sin depender de Supabase.

A diferencia de supabase_repository.py, aquí no se cachean las lecturas:
SQLite es un archivo local (sin viaje de red), así que cada consulta ya es
prácticamente instantánea y cachear solo sumaría riesgo de datos
desactualizados sin ninguna ganancia real de velocidad."""
from __future__ import annotations

import sqlite3
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from utils import consumption

DB_PATH = Path(os.environ.get("MRP_LOCAL_DB") or Path(__file__).resolve().parent / "local.db")


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
                min_stock real not null default 0,
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
                received_qty real not null default 0,
                created_at text default (datetime('now'))
            );

            create table if not exists stock_movements (
                id text primary key,
                material_id text not null references materials(id) on delete cascade,
                project_site_id text references project_sites(id) on delete set null,
                kind text not null,
                quantity real not null,
                note text,
                order_id text references purchase_orders(id) on delete set null,
                actor text,
                created_at text default (datetime('now'))
            );

            create table if not exists site_budgets (
                id text primary key,
                project_site_id text not null references project_sites(id) on delete cascade,
                material_id text not null references materials(id) on delete cascade,
                planned_qty real not null default 0,
                planned_unit_price real not null default 0,
                created_at text default (datetime('now')),
                updated_at text default (datetime('now')),
                unique (project_site_id, material_id)
            );

            create table if not exists attendance (
                id text primary key,
                worker_id text not null references workers(id) on delete cascade,
                project_site_id text references project_sites(id) on delete set null,
                work_date text not null,
                status text not null default 'presente',
                note text,
                created_at text default (datetime('now')),
                unique (worker_id, work_date)
            );

            create table if not exists price_history (
                id text primary key,
                supplier_id text not null references suppliers(id) on delete cascade,
                material_id text not null references materials(id) on delete cascade,
                price real,
                source text not null default 'manual',
                recorded_at text default (datetime('now'))
            );

            create table if not exists dispatch_vouchers (
                id text primary key,
                code text not null unique,
                project_site_id text references project_sites(id) on delete set null,
                site_name text not null,
                worker_id text references workers(id) on delete set null,
                requested_by text,
                note text,
                actor text,
                created_at text default (datetime('now'))
            );

            create table if not exists inventory_counts (
                id text primary key,
                code text not null unique,
                note text,
                actor text,
                created_at text default (datetime('now'))
            );

            create table if not exists inventory_count_lines (
                id text primary key,
                count_id text not null references inventory_counts(id) on delete cascade,
                material_id text not null references materials(id) on delete cascade,
                system_qty real not null,
                counted_qty real not null,
                difference real not null,
                reason text
            );

            create table if not exists audit_log (
                id text primary key,
                actor text not null,
                summary text not null,
                created_at text default (datetime('now'))
            );
            """
        )
        for table, column, ddl in [
            ("purchase_order_items", "received_qty", "real not null default 0"),
            ("materials", "min_stock", "real not null default 0"),
            ("supplier_materials", "price_updated_at", "text"),
            ("stock_movements", "voucher_id", "text references dispatch_vouchers(id) on delete set null"),
            ("stock_movements", "movement_type", "text"),
            ("stock_movements", "count_id", "text references inventory_counts(id) on delete set null"),
        ]:
            cols = [r[1] for r in conn.execute(f"pragma table_info({table})").fetchall()]
            if column not in cols:
                conn.execute(f"alter table {table} add column {column} {ddl}")


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
    for col in ["id", "category", "name", "density", "metric_label", "min_stock", "created_at", "updated_at"]:
        if col not in df.columns:
            df[col] = None
    return df.astype(object).where(pd.notnull(df), None)


def upsert_material(
    category: str, name: str, density: float | None, metric_label: str, material_id: str | None = None, min_stock: float = 0.0
) -> None:
    min_stock = float(min_stock or 0)
    with _connect() as conn:
        if material_id:
            conn.execute(
                "update materials set category = ?, name = ?, density = ?, metric_label = ?, min_stock = ?, updated_at = datetime('now') where id = ?",
                (category, name, density, metric_label, min_stock, material_id),
            )
            return
        existing = conn.execute("select id from materials where category = ? and name = ?", (category, name)).fetchone()
        if existing:
            conn.execute(
                "update materials set density = ?, metric_label = ?, min_stock = ?, updated_at = datetime('now') where id = ?",
                (density, metric_label, min_stock, existing[0]),
            )
        else:
            conn.execute(
                "insert into materials (id, category, name, density, metric_label, min_stock) values (?, ?, ?, ?, ?, ?)",
                (material_id or str(uuid.uuid4()), category, name, density, metric_label, min_stock),
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


def _record_price(conn, supplier_id: str, material_id: str, price: float | None, source: str = "manual") -> None:
    conn.execute(
        "insert into price_history (id, supplier_id, material_id, price, source) values (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), supplier_id, material_id, price, source),
    )


def set_supplier_material(supplier_id: str, material_id: str, offered: bool, available: bool, price: float | None) -> None:
    with _connect() as conn:
        if not offered:
            conn.execute(
                "delete from supplier_materials where supplier_id = ? and material_id = ?",
                (supplier_id, material_id),
            )
            return
        existing = conn.execute(
            "select id, price from supplier_materials where supplier_id = ? and material_id = ?",
            (supplier_id, material_id),
        ).fetchone()
        changed = price is not None and (existing is None or existing[1] != price)
        if existing:
            conn.execute("update supplier_materials set available = ?, price = ? where id = ?", (int(available), price, existing[0]))
            if changed:
                conn.execute("update supplier_materials set price_updated_at = datetime('now') where id = ?", (existing[0],))
        else:
            conn.execute(
                "insert into supplier_materials (id, supplier_id, material_id, available, price) values (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), supplier_id, material_id, int(available), price),
            )
            if price is not None:
                conn.execute(
                    "update supplier_materials set price_updated_at = datetime('now') where supplier_id = ? and material_id = ?",
                    (supplier_id, material_id),
                )
        if changed:
            _record_price(conn, supplier_id, material_id, price)


def bulk_set_supplier_prices(supplier_id: str, rows: list[dict], make_available: bool = True) -> int:
    """Carga precios de muchos materiales de un proveedor de una vez (importación de su lista).
    Cada fila: {"material_id": ..., "price": ...}. Devuelve cuántos se aplicaron."""
    applied = 0
    with _connect() as conn:
        for row in rows:
            material_id, price = row["material_id"], float(row["price"])
            existing = conn.execute(
                "select id, price from supplier_materials where supplier_id = ? and material_id = ?",
                (supplier_id, material_id),
            ).fetchone()
            if existing:
                if existing[1] != price:
                    _record_price(conn, supplier_id, material_id, price, "importacion")
                conn.execute(
                    "update supplier_materials set price = ?, price_updated_at = datetime('now') where id = ?",
                    (price, existing[0]),
                )
                if make_available:
                    conn.execute("update supplier_materials set available = 1 where id = ?", (existing[0],))
            else:
                conn.execute(
                    "insert into supplier_materials (id, supplier_id, material_id, available, price, price_updated_at) values (?, ?, ?, ?, ?, datetime('now'))",
                    (str(uuid.uuid4()), supplier_id, material_id, int(make_available), price),
                )
                _record_price(conn, supplier_id, material_id, price, "importacion")
            applied += 1
    return applied


def list_price_history(material_id: str | None = None, supplier_id: str | None = None, limit: int = 200) -> pd.DataFrame:
    query = """
        select h.id, h.supplier_id, s.name as supplier_name, h.material_id, m.name as material_name,
               h.price, h.source, h.recorded_at
        from price_history h
        join suppliers s on s.id = h.supplier_id
        join materials m on m.id = h.material_id
        where 1 = 1
    """
    params: list = []
    if material_id:
        query += " and h.material_id = ?"
        params.append(material_id)
    if supplier_id:
        query += " and h.supplier_id = ?"
        params.append(supplier_id)
    query += " order by h.recorded_at desc, h.rowid desc limit ?"
    params.append(limit)
    with _connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df.astype(object).where(pd.notnull(df), None)


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
               i.unit, i.quantity, i.unit_price, i.received_qty, (i.quantity * i.unit_price) as subtotal
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
    """Elimina una orden. Si ya recibió material no se puede (el stock quedaría descuadrado)."""
    with _connect() as conn:
        received = conn.execute(
            "select count(*) from purchase_order_items where order_id = ? and received_qty > 0", (order_id,)
        ).fetchone()[0]
        if received:
            raise ValueError("La orden ya recibió material: cancélala en lugar de eliminarla.")
        conn.execute("delete from purchase_orders where id = ?", (order_id,))


def update_order(order_id: str, project_site_id: str | None, notes: str | None, items: list[dict]) -> None:
    """Edita obra, notas y líneas de una orden que todavía no recibió material.
    `items` reemplaza las líneas actuales (material_id, material_name, unit, quantity, unit_price)."""
    with _connect() as conn:
        row = conn.execute("select status from purchase_orders where id = ?", (order_id,)).fetchone()
        if row is None:
            raise ValueError("La orden no existe.")
        if row[0] in ("recibida", "cancelada", "parcial"):
            raise ValueError("Esta orden ya no se puede editar.")
        if conn.execute(
            "select count(*) from purchase_order_items where order_id = ? and received_qty > 0", (order_id,)
        ).fetchone()[0]:
            raise ValueError("La orden ya recibió material y no se puede editar.")
        if not items:
            raise ValueError("La orden debe tener al menos una línea.")
        conn.execute("delete from purchase_order_items where order_id = ?", (order_id,))
        for item in items:
            conn.execute(
                """
                insert into purchase_order_items (id, order_id, material_id, material_name, unit, quantity, unit_price)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), order_id, item.get("material_id"), item["material_name"], item.get("unit"), item["quantity"], item["unit_price"]),
            )
        conn.execute(
            "update purchase_orders set project_site_id = ?, notes = ?, updated_at = datetime('now') where id = ?",
            (project_site_id, notes, order_id),
        )


def receive_order_items(order_id: str, receipts: dict[str, float], actor: str | None = None) -> str:
    """Registra lo recibido por línea (id de línea -> cantidad que llegó ahora),
    genera las entradas de stock y deja la orden en 'parcial' o 'recibida'.
    Todo en una sola transacción. Devuelve el nuevo estado."""
    with _connect() as conn:
        order = conn.execute("select code, status from purchase_orders where id = ?", (order_id,)).fetchone()
        if order is None:
            raise ValueError("La orden no existe.")
        code, status = order
        if status == "cancelada":
            raise ValueError(f"La orden {code} está cancelada y no puede recibir material.")
        for item_id, qty in receipts.items():
            if not qty or qty <= 0:
                continue
            row = conn.execute(
                "select material_id, quantity, received_qty from purchase_order_items where id = ? and order_id = ?",
                (item_id, order_id),
            ).fetchone()
            if row is None:
                raise ValueError("La línea no pertenece a la orden.")
            if row[2] + qty > row[1] + 1e-9:
                raise ValueError("Se intenta recibir más de lo pedido en una línea.")
            conn.execute("update purchase_order_items set received_qty = received_qty + ? where id = ?", (qty, item_id))
            if row[0]:
                conn.execute(
                    "insert into stock_movements (id, material_id, kind, quantity, note, order_id, actor, movement_type) values (?, ?, 'entrada', ?, ?, ?, ?, 'recepcion')",
                    (str(uuid.uuid4()), row[0], qty, f"Recepción {code}", order_id, actor),
                )
        pending = conn.execute(
            "select count(*) from purchase_order_items where order_id = ? and received_qty < quantity", (order_id,)
        ).fetchone()[0]
        new_status = "parcial" if pending else "recibida"
        conn.execute("update purchase_orders set status = ?, updated_at = datetime('now') where id = ?", (new_status, order_id))
    return new_status


# ---------------------------------------------------------------------------
# Inventario (movimientos de stock) y presupuesto por obra
# ---------------------------------------------------------------------------

def _stock_of(conn, material_id: str) -> float:
    row = conn.execute(
        "select coalesce(sum(case when kind = 'entrada' then quantity else -quantity end), 0) from stock_movements where material_id = ?",
        (material_id,),
    ).fetchone()
    return float(row[0])


def add_movement(
    material_id: str, kind: str, quantity: float, project_site_id: str | None, note: str | None, actor: str | None,
    movement_type: str | None = None,
) -> None:
    """Entrada o salida suelta (ajuste, merma). Una salida nunca deja el stock en negativo."""
    if quantity is None or quantity <= 0:
        raise ValueError("La cantidad debe ser mayor que 0.")
    with _connect() as conn:
        if kind == "salida" and _stock_of(conn, material_id) < quantity - 1e-9:
            raise ValueError("Stock insuficiente para esta salida.")
        movement_type = movement_type or ("entrada_manual" if kind == "entrada" else ("despacho" if project_site_id else "merma"))
        conn.execute(
            "insert into stock_movements (id, material_id, project_site_id, kind, quantity, note, actor, movement_type) values (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), material_id, project_site_id, kind, quantity, note, actor, movement_type),
        )


def list_movements(project_site_id: str | None = None, limit: int = 500) -> pd.DataFrame:
    query = """
        select sm.id, sm.material_id, m.name as material_name, m.category, m.metric_label as unit,
               sm.project_site_id, ps.name as site_name, sm.kind, sm.quantity, sm.note,
               o.code as order_code, sm.actor, sm.created_at, sm.movement_type,
               v.code as voucher_code, v.requested_by, ic.code as count_code
        from stock_movements sm
        join materials m on m.id = sm.material_id
        left join project_sites ps on ps.id = sm.project_site_id
        left join purchase_orders o on o.id = sm.order_id
        left join dispatch_vouchers v on v.id = sm.voucher_id
        left join inventory_counts ic on ic.id = sm.count_id
    """
    params: tuple = ()
    if project_site_id:
        query += " where sm.project_site_id = ?"
        params = (project_site_id,)
    query += " order by sm.created_at desc, sm.rowid desc limit ?"
    with _connect() as conn:
        df = pd.read_sql_query(query, conn, params=params + (limit,))
    return df.astype(object).where(pd.notnull(df), None)


def stock_levels() -> pd.DataFrame:
    """Stock actual de TODOS los materiales (sin límite de movimientos)."""
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select m.id as material_id, m.category, m.name as material_name, m.metric_label as unit, m.min_stock,
                   coalesce(sum(case when s.kind = 'entrada' then s.quantity end), 0) as entradas,
                   coalesce(sum(case when s.kind = 'salida' then s.quantity end), 0) as salidas,
                   coalesce(sum(case when s.kind = 'entrada' then s.quantity when s.kind = 'salida' then -s.quantity end), 0) as stock
            from materials m left join stock_movements s on s.material_id = m.id
            group by m.id order by m.category, m.name
            """,
            conn,
        )
    return df.astype(object).where(pd.notnull(df), None)


def create_dispatch(
    project_site_id: str, worker_id: str | None, requested_by: str | None, note: str | None, lines: list[dict], actor: str | None,
) -> str:
    """Despacha material del almacén a una obra con su vale de salida (VS-0001...).
    `lines`: [{"material_id", "quantity", "note"?}]. Todo o nada: si algún material no
    alcanza, no se registra nada. Devuelve el código del vale."""
    if not lines:
        raise ValueError("El vale no tiene materiales.")
    with _connect() as conn:
        site = conn.execute("select name from project_sites where id = ?", (project_site_id,)).fetchone()
        if site is None:
            raise ValueError("La obra no existe.")
        wanted: dict[str, float] = {}
        for line in lines:
            if not line["quantity"] or line["quantity"] <= 0:
                raise ValueError("Todas las cantidades deben ser mayores que 0.")
            wanted[line["material_id"]] = wanted.get(line["material_id"], 0.0) + float(line["quantity"])
        for material_id, qty in wanted.items():
            available = _stock_of(conn, material_id)
            if available < qty - 1e-9:
                name = conn.execute("select name from materials where id = ?", (material_id,)).fetchone()
                raise ValueError(f"Stock insuficiente de «{name[0] if name else material_id}»: hay {available:g} y se piden {qty:g}.")
        codes = [r[0] for r in conn.execute("select code from dispatch_vouchers").fetchall()]
        number = max([int(c.split("-")[1]) for c in codes if c.startswith("VS-") and c.split("-")[1].isdigit()] or [0]) + 1
        code = f"VS-{number:04d}"
        voucher_id = str(uuid.uuid4())
        conn.execute(
            "insert into dispatch_vouchers (id, code, project_site_id, site_name, worker_id, requested_by, note, actor) values (?, ?, ?, ?, ?, ?, ?, ?)",
            (voucher_id, code, project_site_id, site[0], worker_id, (requested_by or "").strip() or None, (note or "").strip() or None, actor),
        )
        for line in lines:
            conn.execute(
                "insert into stock_movements (id, material_id, project_site_id, kind, quantity, note, actor, voucher_id, movement_type) values (?, ?, ?, 'salida', ?, ?, ?, ?, 'despacho')",
                (str(uuid.uuid4()), line["material_id"], project_site_id, line["quantity"], line.get("note") or f"Despacho {code}", actor, voucher_id),
            )
    return code


def list_dispatches(limit: int = 200) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select v.id, v.code, v.project_site_id, v.site_name, v.worker_id, v.requested_by, v.note, v.actor, v.created_at,
                   (select count(*) from stock_movements s where s.voucher_id = v.id) as lines_count
            from dispatch_vouchers v order by v.created_at desc, v.rowid desc limit ?
            """,
            conn,
            params=(limit,),
        )
    return df.astype(object).where(pd.notnull(df), None)


def list_dispatch_lines(voucher_id: str) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select s.id, s.material_id, m.name as material_name, m.category, m.metric_label as unit, s.quantity, s.note
            from stock_movements s join materials m on m.id = s.material_id
            where s.voucher_id = ? order by m.name
            """,
            conn,
            params=(voucher_id,),
        )
    return df.astype(object).where(pd.notnull(df), None)


def _net_dispatched(conn, project_site_id: str) -> dict[str, float]:
    """{material_id: despachado a la obra − devuelto por la obra}."""
    rows = conn.execute(
        "select material_id, kind, quantity, movement_type, project_site_id from stock_movements where project_site_id = ?", (project_site_id,)
    ).fetchall()
    return consumption.net_by_material(
        [{"material_id": r[0], "kind": r[1], "quantity": r[2], "movement_type": r[3], "project_site_id": r[4]} for r in rows]
    )


def create_return(project_site_id: str, returned_by: str | None, note: str | None, lines: list[dict], actor: str | None) -> int:
    """Devuelve material de una obra al almacén (suma al stock). No se puede devolver más de lo
    que la obra tiene (despachado − ya devuelto). `lines`: [{"material_id", "quantity", "note"?}].
    Todo o nada. Devuelve cuántos materiales se devolvieron."""
    if not lines:
        raise ValueError("La devolución no tiene materiales.")
    with _connect() as conn:
        if conn.execute("select 1 from project_sites where id = ?", (project_site_id,)).fetchone() is None:
            raise ValueError("La obra no existe.")
        wanted: dict[str, float] = {}
        for line in lines:
            if not line["quantity"] or line["quantity"] <= 0:
                raise ValueError("Todas las cantidades deben ser mayores que 0.")
            wanted[line["material_id"]] = wanted.get(line["material_id"], 0.0) + float(line["quantity"])
        held = _net_dispatched(conn, project_site_id)
        for material_id, qty in wanted.items():
            if qty > held.get(material_id, 0.0) + 1e-9:
                name = conn.execute("select name from materials where id = ?", (material_id,)).fetchone()
                raise ValueError(
                    f"De «{name[0] if name else material_id}» la obra solo tiene {max(held.get(material_id, 0.0), 0):g} "
                    f"(despachado menos devuelto) y se intentan devolver {qty:g}."
                )
        who = (returned_by or "").strip()
        base = (note or "").strip()
        for line in lines:
            text = " · ".join(x for x in [f"Devuelve {who}" if who else "Devolución de obra", base, line.get("note")] if x)
            conn.execute(
                "insert into stock_movements (id, material_id, project_site_id, kind, quantity, note, actor, movement_type) "
                "values (?, ?, ?, 'entrada', ?, ?, ?, 'devolucion')",
                (str(uuid.uuid4()), line["material_id"], project_site_id, line["quantity"], text, actor),
            )
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
    with _connect() as conn:
        codes = [r[0] for r in conn.execute("select code from inventory_counts").fetchall()]
        number = max([int(c.split("-")[1]) for c in codes if c.startswith("CT-") and c.split("-")[1].isdigit()] or [0]) + 1
        code = f"CT-{number:04d}"
        count_id = str(uuid.uuid4())
        conn.execute("insert into inventory_counts (id, code, note, actor) values (?, ?, ?, ?)", (count_id, code, (note or "").strip() or None, actor))
        for line in lines:
            counted = float(line["counted_qty"])
            system = _stock_of(conn, line["material_id"])
            diff = round(counted - system, 6)
            reason = (line.get("reason") or "").strip()
            conn.execute(
                "insert into inventory_count_lines (id, count_id, material_id, system_qty, counted_qty, difference, reason) values (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), count_id, line["material_id"], system, counted, diff, reason or None),
            )
            if abs(diff) > 1e-9:
                text = f"Conteo {code}: sistema {system:g}, contado {counted:g}" + (f" · {reason}" if reason else "")
                conn.execute(
                    "insert into stock_movements (id, material_id, kind, quantity, note, actor, movement_type, count_id) values (?, ?, ?, ?, ?, ?, 'conteo', ?)",
                    (str(uuid.uuid4()), line["material_id"], "entrada" if diff > 0 else "salida", abs(diff), text, actor, count_id),
                )
    return code


def list_inventory_counts(limit: int = 100) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select c.id, c.code, c.note, c.actor, c.created_at,
                   (select count(*) from inventory_count_lines l where l.count_id = c.id) as lines_count,
                   (select count(*) from inventory_count_lines l where l.count_id = c.id and l.difference != 0) as adjusted_count
            from inventory_counts c order by c.created_at desc, c.rowid desc limit ?
            """,
            conn,
            params=(limit,),
        )
    return df.astype(object).where(pd.notnull(df), None)


def list_count_lines(count_id: str) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select l.id, l.material_id, m.name as material_name, m.category, m.metric_label as unit,
                   l.system_qty, l.counted_qty, l.difference, l.reason
            from inventory_count_lines l join materials m on m.id = l.material_id
            where l.count_id = ? order by m.name
            """,
            conn,
            params=(count_id,),
        )
    return df.astype(object).where(pd.notnull(df), None)


def list_budgets(project_site_id: str | None = None) -> pd.DataFrame:
    query = """
        select b.id, b.project_site_id, b.material_id, m.category, m.name as material_name,
               m.metric_label as unit, b.planned_qty, b.planned_unit_price
        from site_budgets b join materials m on m.id = b.material_id
    """
    params: tuple = ()
    if project_site_id:
        query += " where b.project_site_id = ?"
        params = (project_site_id,)
    query += " order by m.category, m.name"
    with _connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df.astype(object).where(pd.notnull(df), None)


def set_budget(project_site_id: str, material_id: str, planned_qty: float, planned_unit_price: float) -> None:
    with _connect() as conn:
        existing = conn.execute(
            "select id from site_budgets where project_site_id = ? and material_id = ?", (project_site_id, material_id)
        ).fetchone()
        if existing:
            conn.execute(
                "update site_budgets set planned_qty = ?, planned_unit_price = ?, updated_at = datetime('now') where id = ?",
                (planned_qty, planned_unit_price, existing[0]),
            )
        else:
            conn.execute(
                "insert into site_budgets (id, project_site_id, material_id, planned_qty, planned_unit_price) values (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), project_site_id, material_id, planned_qty, planned_unit_price),
            )


def delete_budget(budget_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from site_budgets where id = ?", (budget_id,))


# ---------------------------------------------------------------------------
# Asistencia
# ---------------------------------------------------------------------------

def list_attendance(start: str, end: str) -> pd.DataFrame:
    """Asistencia entre dos fechas (YYYY-MM-DD, ambas incluidas)."""
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            select a.id, a.worker_id, w.full_name as worker_name, a.project_site_id, ps.name as site_name,
                   a.work_date, a.status, a.note
            from attendance a
            join workers w on w.id = a.worker_id
            left join project_sites ps on ps.id = a.project_site_id
            where a.work_date >= ? and a.work_date <= ?
            order by a.work_date desc, w.full_name
            """,
            conn,
            params=(start, end),
        )
    return df.astype(object).where(pd.notnull(df), None)


def set_attendance(worker_id: str, project_site_id: str | None, work_date: str, status: str, note: str | None) -> None:
    with _connect() as conn:
        existing = conn.execute(
            "select id from attendance where worker_id = ? and work_date = ?", (worker_id, work_date)
        ).fetchone()
        if existing:
            conn.execute(
                "update attendance set project_site_id = ?, status = ?, note = ? where id = ?",
                (project_site_id, status, note, existing[0]),
            )
        else:
            conn.execute(
                "insert into attendance (id, worker_id, project_site_id, work_date, status, note) values (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), worker_id, project_site_id, work_date, status, note),
            )


# ---------------------------------------------------------------------------
# Historial de cambios
# ---------------------------------------------------------------------------

def log_action(actor: str, summary: str) -> None:
    with _connect() as conn:
        conn.execute("insert into audit_log (id, actor, summary) values (?, ?, ?)", (str(uuid.uuid4()), actor, summary))


def list_audit(limit: int = 300) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            "select id, actor, summary, created_at from audit_log order by created_at desc, rowid desc limit ?",
            conn,
            params=(limit,),
        )
    return df.astype(object).where(pd.notnull(df), None)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard_totals() -> dict:
    with _connect() as conn:
        orders_open = conn.execute(
            "select count(*) from purchase_orders where status in ('pendiente', 'enviada', 'parcial')"
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
        dispatches_month = conn.execute(
            "select count(*) from dispatch_vouchers where strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')"
        ).fetchone()[0]
    levels = stock_levels()
    stock = levels["stock"].astype(float) if not levels.empty else pd.Series(dtype=float)
    minimum = levels["min_stock"].astype(float) if not levels.empty else pd.Series(dtype=float)
    return {
        "materials": materials,
        "suppliers": suppliers,
        "suppliers_with_available": suppliers_with_available,
        "materials_without_supplier": materials_without_supplier,
        "orders_open": orders_open,
        "materials_in_stock": int((stock > 0).sum()),
        "low_stock": int(((minimum > 0) & (stock <= minimum)).sum()),
        "dispatches_month": dispatches_month,
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
# Tablas de la app, en orden de dependencia (para respaldos y restauración).
BACKUP_TABLES = [
    "materials", "suppliers", "supplier_materials", "users", "work_groups", "project_sites", "workers",
    "purchase_orders", "purchase_order_items", "dispatch_vouchers", "inventory_counts", "inventory_count_lines", "stock_movements",
    "site_budgets", "attendance", "audit_log", "price_history",
]


def set_user_password(user_id: str, password_hash: str) -> None:
    with _connect() as conn:
        conn.execute("update users set password_hash = ?, updated_at = datetime('now') where id = ?", (password_hash, user_id))


def dump_tables() -> dict[str, pd.DataFrame]:
    """Todas las tablas de la app, completas, para el respaldo."""
    out: dict[str, pd.DataFrame] = {}
    with _connect() as conn:
        existing = {r[0] for r in conn.execute("select name from sqlite_master where type = 'table'").fetchall()}
        for table in BACKUP_TABLES:
            if table in existing:
                out[table] = pd.read_sql_query(f"select * from {table}", conn)
    return out
