"""Módulo de Órdenes de compra: pedidos a un proveedor con sus líneas de
material (cantidad y precio), la obra destino y un estado que avanza de
pendiente a enviada y recibida (o cancelada)."""
import pandas as pd
import streamlit as st

from db import repository as repo
from modules import ui

SELECTED_KEY = "selected_order_id"
LINES_KEY = "_order_lines"
SUPPLIER_KEY = "_order_supplier"

# estado -> (etiqueta, color de pastilla)
STATUSES = {
    "pendiente": ("Pendiente", "amber"),
    "enviada": ("Enviada", "blue"),
    "recibida": ("Recibida", "green"),
    "cancelada": ("Cancelada", "red"),
}
ALL_STATUSES = "Todos los estados"
NO_SITE = "Sin obra destino"


def status_pill(status: str) -> str:
    label, color = STATUSES.get(status, (status, "gray"))
    return ui.pill(label, color)


def render() -> None:
    if st.session_state.get(SELECTED_KEY):
        _render_detail(st.session_state[SELECTED_KEY])
        return

    clicked = ui.page_header(
        "Compras",
        "Órdenes de compra",
        "Pedidos a proveedores: qué materiales, cuántos, a qué precio y para qué obra.",
        action_label="＋ Nueva orden",
        action_key="new_order_open",
    )
    if clicked:
        _new_order_dialog()

    _render_list()


# ---------------------------------------------------------------------------
# Alta de orden
# ---------------------------------------------------------------------------

@st.dialog("Nueva orden de compra", width="large")
def _new_order_dialog() -> None:
    suppliers = repo.list_suppliers()
    if suppliers.empty:
        st.info("Primero registra un proveedor en el módulo Proveedores.")
        return

    supplier_name = st.selectbox("Proveedor", suppliers["name"].tolist())
    supplier_id = suppliers.loc[suppliers["name"] == supplier_name, "id"].iloc[0]
    if st.session_state.get(SUPPLIER_KEY) != supplier_id:
        st.session_state[SUPPLIER_KEY] = supplier_id
        st.session_state[LINES_KEY] = []
    lines: list[dict] = st.session_state.setdefault(LINES_KEY, [])

    sites = repo.list_project_sites()
    site_choice = st.selectbox("Obra destino (opcional)", [NO_SITE] + sites["name"].tolist())
    notes = st.text_input("Notas (opcional)", placeholder="Ej. Entregar antes del viernes")

    st.markdown("**Materiales del pedido**")
    catalog = repo.get_supplier_catalog(supplier_id)
    offered = catalog[catalog["offered"]] if not catalog.empty else catalog
    if offered.empty:
        st.warning("Este proveedor todavía no tiene materiales asignados. Márcalos como «Lo ofrece» en su catálogo.")
    else:
        options = {f"{r['category']} · {r['name']}": r for r in offered.to_dict("records")}
        c1, c2, c3 = st.columns([4, 2, 2])
        choice = c1.selectbox("Material", list(options))
        record = options[choice]
        qty = c2.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, key=f"oqty_{record['id']}")
        catalog_price = float(record["price"]) if pd.notna(record["price"]) else 0.0
        price = c3.number_input(
            "Precio unit.", min_value=0.0, value=catalog_price, step=0.1, format="%.2f", key=f"oprice_{supplier_id}_{record['id']}"
        )
        if st.button("＋ Agregar al pedido", use_container_width=True):
            if qty <= 0:
                st.error("La cantidad debe ser mayor que 0.")
            else:
                existing = next((ln for ln in lines if ln["material_id"] == record["id"]), None)
                if existing:
                    existing["quantity"] += qty
                    existing["unit_price"] = price
                else:
                    lines.append(
                        {
                            "material_id": record["id"],
                            "material_name": record["name"],
                            "unit": record["metric_label"] or None,
                            "quantity": qty,
                            "unit_price": price,
                        }
                    )
                st.rerun(scope="fragment")

    total = 0.0
    for index, line in enumerate(lines):
        subtotal = line["quantity"] * line["unit_price"]
        total += subtotal
        l1, l2, l3 = st.columns([6, 3, 1])
        l1.write(f"{line['material_name']}  ·  {line['quantity']:g} {line['unit'] or ''} × {line['unit_price']:,.2f}")
        l2.write(f"**{subtotal:,.2f}**")
        if l3.button("✖", key=f"oline_del_{index}", help="Quitar línea"):
            lines.pop(index)
            st.rerun(scope="fragment")
    if lines:
        st.markdown(f"**Total: {total:,.2f}**")

    if st.button("Crear orden", type="primary", use_container_width=True, disabled=not lines):
        site_id = None if site_choice == NO_SITE else sites.loc[sites["name"] == site_choice, "id"].iloc[0]
        code = repo.create_order(supplier_id, supplier_name, site_id, notes.strip() or None, lines)
        st.session_state.pop(LINES_KEY, None)
        st.session_state.pop(SUPPLIER_KEY, None)
        ui.flash(f"Orden {code} creada.", "🧾")
        st.rerun()


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

def _delete_order(order_id: str, code: str) -> None:
    repo.delete_order(order_id)
    if st.session_state.get(SELECTED_KEY) == order_id:
        st.session_state[SELECTED_KEY] = None
    ui.flash(f"Orden {code} eliminada.", "🗑️")


def _render_list() -> None:
    st.markdown('<div class="mrp-eyebrow">Historial</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Órdenes registradas</div>', unsafe_allow_html=True)

    df = repo.list_orders()
    if df.empty:
        st.info("Todavía no hay órdenes. Usa «＋ Nueva orden» arriba para crear la primera.")
        return

    f1, f2 = st.columns([3, 2])
    query = f1.text_input("Buscar", placeholder="🔍 Buscar por código, proveedor u obra…", label_visibility="collapsed", key="ord_q")
    labels = {value[0]: key for key, value in STATUSES.items()}
    status_label = f2.selectbox("Estado", [ALL_STATUSES] + list(labels), label_visibility="collapsed", key="ord_status")

    if status_label != ALL_STATUSES:
        df = df[df["status"] == labels[status_label]]
    df = ui.filter_df(df, query, ["code", "supplier_name", "site_name"])
    if df.empty:
        st.info("Ninguna orden coincide con los filtros.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([4, 3, 2, 1.6, 1])
            with c1:
                date = str(row["created_at"])[:10]
                n = int(row["items_count"])
                sub = f"{row['code']} · {date} · {n} línea{'s' if n != 1 else ''}"
                st.markdown(ui.row_name_sub(ui.avatar(row["supplier_name"]), row["supplier_name"], sub), unsafe_allow_html=True)
            with c2:
                pills = status_pill(row["status"])
                if row.get("site_name"):
                    pills += " " + ui.pill(row["site_name"], "gray")
                st.markdown(pills, unsafe_allow_html=True)
            with c3:
                st.markdown(
                    f'<div class="mrp-row-name">{float(row["total"]):,.2f}</div><div class="mrp-row-sub">total</div>',
                    unsafe_allow_html=True,
                )
            with c4:
                if st.button("Ver", key=f"open_order_{row['id']}", use_container_width=True):
                    st.session_state[SELECTED_KEY] = row["id"]
                    st.rerun()
            with c5:
                if st.button("🗑", key=f"del_order_{row['id']}", help="Eliminar orden"):
                    ui.confirm_delete(
                        f"¿Eliminar la orden {row['code']}? Se borran también sus líneas.",
                        lambda oid=row["id"], code=row["code"]: _delete_order(oid, code),
                    )


# ---------------------------------------------------------------------------
# Detalle
# ---------------------------------------------------------------------------

def _change_status(order_id: str, code: str, status: str) -> None:
    repo.set_order_status(order_id, status)
    ui.flash(f"Orden {code}: {STATUSES[status][0].lower()}.", "🔄")
    st.rerun()


def _render_detail(order_id: str) -> None:
    orders = repo.list_orders()
    match = orders[orders["id"] == order_id]
    if match.empty:
        st.session_state[SELECTED_KEY] = None
        st.rerun()
        return
    order = match.to_dict("records")[0]
    status = order["status"]

    if st.button("← Volver"):
        st.session_state[SELECTED_KEY] = None
        st.rerun()

    ui.page_header("Orden de compra", order["code"])
    st.markdown(status_pill(status), unsafe_allow_html=True)

    ui.stat_grid(
        [
            ui.stat_card("🏭", order["supplier_name"], "Proveedor"),
            ui.stat_card("🏗️", order["site_name"] or "—", "Obra destino"),
            ui.stat_card("📅", str(order["created_at"])[:10], "Fecha"),
            ui.stat_card("💰", f"{float(order['total']):,.2f}", "Total"),
        ]
    )
    if order.get("notes"):
        st.caption(f"📝 {order['notes']}")

    suppliers = repo.list_suppliers()
    supplier = suppliers[suppliers["id"] == order["supplier_id"]]
    if not supplier.empty:
        s = supplier.to_dict("records")[0]
        st.markdown(ui.contact_links(s["phone"], s["email"]), unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Detalle</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Materiales del pedido</div>', unsafe_allow_html=True)
    items = repo.list_order_items(order_id)
    if items.empty:
        st.info("Esta orden no tiene líneas.")
    else:
        table = items[["material_name", "unit", "quantity", "unit_price", "subtotal"]].rename(
            columns={
                "material_name": "Material",
                "unit": "Unidad",
                "quantity": "Cantidad",
                "unit_price": "Precio unit.",
                "subtotal": "Subtotal",
            }
        )
        for col in ["Cantidad", "Precio unit.", "Subtotal"]:
            table[col] = table[col].astype(float)
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Cantidad": st.column_config.NumberColumn(format="%.2f"),
                "Precio unit.": st.column_config.NumberColumn(format="%.2f"),
                "Subtotal": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.write("")
    b1, b2, b3, _ = st.columns([3, 2.2, 2, 1])
    if status == "pendiente" and b1.button("📤 Marcar como enviada", use_container_width=True):
        _change_status(order_id, order["code"], "enviada")
    if status == "enviada" and b1.button("📦 Marcar como recibida", use_container_width=True):
        _change_status(order_id, order["code"], "recibida")
    if status in ("pendiente", "enviada") and b2.button("Cancelar orden", use_container_width=True):
        _change_status(order_id, order["code"], "cancelada")
    if b3.button("🗑 Eliminar", use_container_width=True):
        ui.confirm_delete(
            f"¿Eliminar la orden {order['code']}? Se borran también sus líneas.",
            lambda oid=order_id, code=order["code"]: _delete_order(oid, code),
        )
