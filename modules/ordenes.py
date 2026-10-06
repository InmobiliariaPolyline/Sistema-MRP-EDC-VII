"""Módulo de Órdenes de compra: pedidos a un proveedor con sus líneas de
material (cantidad y precio), la obra destino y un estado que avanza de
pendiente a enviada, recibida (o parcial si llegó solo una parte) o cancelada.

Incluye comparador de cotizaciones al armar el pedido, recepción parcial por
línea (que alimenta el inventario), duplicar una orden, PDF de la orden y
mensaje listo para WhatsApp."""
import re
from urllib.parse import quote

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import ui
from utils.reports import order_pdf, order_whatsapp_text
from utils.timeago import age_days

SELECTED_KEY = "selected_order_id"
LINES_KEY = "_order_lines"
SUPPLIER_KEY = "_order_supplier"
PRESET_KEY = "_order_preset"
ALERT_DAYS_KEY = "alert_days"
DEFAULT_ALERT_DAYS = 3

# estado -> (etiqueta, color de pastilla)
STATUSES = {
    "pendiente": ("Pendiente", "amber"),
    "enviada": ("Enviada", "blue"),
    "parcial": ("Recibida parcial", "purple"),
    "recibida": ("Recibida", "green"),
    "cancelada": ("Cancelada", "red"),
}
OPEN_STATUSES = ("pendiente", "enviada", "parcial")
ALL_STATUSES = "Todos los estados"
NO_SITE = "Sin obra destino"


def status_pill(status: str) -> str:
    label, color = STATUSES.get(status, (status, "gray"))
    return ui.pill(label, color)


def alert_days() -> int:
    return int(st.session_state.get(ALERT_DAYS_KEY, DEFAULT_ALERT_DAYS))


def stale_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Órdenes todavía pendientes de enviar/recibir con más de X días de antigüedad."""
    if orders.empty:
        return orders
    open_orders = orders[orders["status"].isin(OPEN_STATUSES)]
    ages = open_orders["created_at"].map(lambda v: age_days(str(v)))
    return open_orders[ages > alert_days()].assign(age=ages[ages > alert_days()])


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
        st.session_state.pop(LINES_KEY, None)
        st.session_state.pop(SUPPLIER_KEY, None)
        _new_order_dialog()
    elif st.session_state.get(PRESET_KEY):
        _new_order_dialog()

    _render_list()


# ---------------------------------------------------------------------------
# Alta de orden
# ---------------------------------------------------------------------------

def _supplier_totals(lines: list[dict], offers: pd.DataFrame) -> list[tuple[str, float]]:
    """Cuánto costaría el pedido completo con cada proveedor que ofrece TODOS
    los materiales (con precio), de menor a mayor."""
    wanted = {ln["material_id"]: ln["quantity"] for ln in lines}
    if offers.empty or not wanted:
        return []
    priced = offers[offers["material_id"].isin(wanted) & offers["price"].notna()]
    priced = priced[priced["price"].astype(float) > 0]
    results = []
    for supplier_name, group in priced.groupby("supplier_name"):
        if set(group["material_id"]) >= set(wanted):
            total = sum(float(r["price"]) * wanted[r["material_id"]] for r in group.to_dict("records") if r["material_id"] in wanted)
            results.append((supplier_name, total))
    return sorted(results, key=lambda r: r[1])


def _material_quotes(material_id: str, current_supplier_id: str, offers: pd.DataFrame) -> None:
    """Precio de este material en cada proveedor, lado a lado, sugiriendo el más barato."""
    if offers.empty:
        return
    rows = offers[offers["material_id"] == material_id]
    rows = rows[rows["price"].notna()]
    rows = rows[rows["price"].astype(float) > 0]
    if len(rows) < 2:
        return
    rows = rows.assign(price=rows["price"].astype(float)).sort_values("price")
    best = rows.iloc[0]
    table = pd.DataFrame(
        {
            "Proveedor": [("⭐ " if i == 0 else "") + r["supplier_name"] + (" (este pedido)" if r["supplier_id"] == current_supplier_id else "") for i, r in enumerate(rows.to_dict("records"))],
            "Precio": rows["price"].tolist(),
            "Disponible": ["Sí" if r["available"] else "No" for r in rows.to_dict("records")],
        }
    )
    with st.expander(f"💡 Comparar cotizaciones ({len(rows)} proveedores)", expanded=best["supplier_id"] != current_supplier_id):
        st.dataframe(table, hide_index=True, use_container_width=True, column_config={"Precio": st.column_config.NumberColumn(format="%.2f")})
        mine = rows[rows["supplier_id"] == current_supplier_id]
        if best["supplier_id"] != current_supplier_id and not mine.empty:
            mine_price = float(mine.iloc[0]["price"])
            saving = (1 - float(best["price"]) / mine_price) * 100
            st.caption(f"{best['supplier_name']} lo ofrece {saving:.0f}% más barato ({float(best['price']):,.2f} vs {mine_price:,.2f}). Cambia el proveedor arriba si te conviene.")


@st.dialog("Nueva orden de compra", width="large")
def _new_order_dialog() -> None:
    suppliers = repo.list_suppliers()
    if suppliers.empty:
        st.info("Primero registra un proveedor en el módulo Proveedores.")
        return
    sites = repo.list_project_sites()
    offers = repo.list_offers()

    preset = st.session_state.pop(PRESET_KEY, None)
    if preset:  # viene de «Duplicar»: precarga proveedor, obra, notas y líneas
        st.session_state["new_order_supplier"] = preset["supplier_name"]
        st.session_state["new_order_site"] = preset["site_name"] or NO_SITE
        st.session_state["new_order_notes"] = preset["notes"] or ""
        st.session_state[SUPPLIER_KEY] = preset["supplier_id"]
        st.session_state[LINES_KEY] = preset["lines"]

    supplier_name = st.selectbox("Proveedor", suppliers["name"].tolist(), key="new_order_supplier")
    supplier_id = suppliers.loc[suppliers["name"] == supplier_name, "id"].iloc[0]
    if st.session_state.get(SUPPLIER_KEY) != supplier_id:
        st.session_state[SUPPLIER_KEY] = supplier_id
        st.session_state[LINES_KEY] = []
    lines: list[dict] = st.session_state.setdefault(LINES_KEY, [])

    site_choice = st.selectbox("Obra destino (opcional)", [NO_SITE] + sites["name"].tolist(), key="new_order_site")
    notes = st.text_input("Notas (opcional)", placeholder="Ej. Entregar antes del viernes", key="new_order_notes")

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
        _material_quotes(record["id"], supplier_id, offers)
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
        totals = _supplier_totals(lines, offers)
        if len(totals) > 1:
            cheapest_name, cheapest_total = totals[0]
            mine = next((t for n, t in totals if n == supplier_name), None)
            with st.expander("💡 Este mismo pedido con otros proveedores", expanded=cheapest_name != supplier_name):
                st.dataframe(
                    pd.DataFrame({"Proveedor": [("⭐ " if i == 0 else "") + n for i, (n, _) in enumerate(totals)], "Total del pedido": [t for _, t in totals]}),
                    hide_index=True,
                    use_container_width=True,
                    column_config={"Total del pedido": st.column_config.NumberColumn(format="%.2f")},
                )
                if mine is not None and cheapest_name != supplier_name:
                    st.caption(f"Con {cheapest_name} ahorrarías {mine - cheapest_total:,.2f} en todo el pedido.")

    if st.button("Crear orden", type="primary", use_container_width=True, disabled=not lines):
        site_id = None if site_choice == NO_SITE else sites.loc[sites["name"] == site_choice, "id"].iloc[0]
        code = repo.create_order(supplier_id, supplier_name, site_id, notes.strip() or None, lines)
        for key in (LINES_KEY, SUPPLIER_KEY, "new_order_supplier", "new_order_site", "new_order_notes"):
            st.session_state.pop(key, None)
        ui.flash(f"Orden {code} creada.", "🧾")
        st.rerun()


def _duplicate(order: dict, items: pd.DataFrame) -> None:
    """Prepara el diálogo de nueva orden con los datos de otra ya hecha."""
    suppliers = repo.list_suppliers()
    match = suppliers[suppliers["id"] == order["supplier_id"]]
    if match.empty:
        st.toast("El proveedor de esta orden ya no existe; no se puede duplicar.", icon="⚠️")
        return
    st.session_state[SELECTED_KEY] = None
    st.session_state[PRESET_KEY] = {
        "supplier_id": order["supplier_id"],
        "supplier_name": order["supplier_name"],
        "site_name": order.get("site_name"),
        "notes": order.get("notes"),
        "lines": [
            {
                "material_id": r["material_id"],
                "material_name": r["material_name"],
                "unit": r.get("unit"),
                "quantity": float(r["quantity"]),
                "unit_price": float(r["unit_price"]),
            }
            for r in items.to_dict("records")
            if r.get("material_id")
        ],
    }
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

    f1, f2, f3 = st.columns([3, 2, 1.6])
    query = f1.text_input("Buscar", placeholder="🔍 Buscar por código, proveedor u obra…", label_visibility="collapsed", key="ord_q")
    labels = {value[0]: key for key, value in STATUSES.items()}
    status_label = f2.selectbox("Estado", [ALL_STATUSES] + list(labels), label_visibility="collapsed", key="ord_status")
    st.session_state[ALERT_DAYS_KEY] = f3.number_input(
        "Avisar tras (días)",
        min_value=1,
        max_value=60,
        value=alert_days(),
        key="alert_days_input",
        help="Las órdenes abiertas con más días que esto se marcan con ⏰ aquí y en el dashboard.",
    )

    stale = stale_orders(df)
    if not stale.empty:
        st.warning(f"⏰ {len(stale)} orden(es) abierta(s) con más de {alert_days()} días sin cerrarse: {', '.join(stale['code'].tolist()[:6])}")

    if status_label != ALL_STATUSES:
        df = df[df["status"] == labels[status_label]]
    df = ui.filter_df(df, query, ["code", "supplier_name", "site_name"])
    if df.empty:
        st.info("Ninguna orden coincide con los filtros.")
        return

    stale_ids = set(stale["id"]) if not stale.empty else set()
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
                if row["id"] in stale_ids:
                    pills += " " + ui.pill("⏰ " + f"{age_days(str(row['created_at']))} días", "red")
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


def _receive(order_id: str, code: str, receipts: dict[str, float]) -> None:
    if not any(q > 0 for q in receipts.values()):
        st.toast("Indica al menos una cantidad recibida.", icon="⚠️")
        return
    status = repo.receive_order_items(order_id, receipts, ui.current_actor())
    ui.flash(f"Orden {code}: recepción registrada ({STATUSES[status][0].lower()}). El stock se actualizó.", "📦")
    st.rerun()


def _render_reception(order: dict, items: pd.DataFrame) -> None:
    """Cuánto llegó de cada línea; suma al stock y deja la orden en parcial o recibida."""
    pending = items[items["quantity"].astype(float) - items["received_qty"].astype(float) > 1e-9]
    if pending.empty:
        return
    with st.expander("📦 Registrar recepción", expanded=order["status"] in ("enviada", "parcial")):
        st.caption("Escribe lo que llegó ahora de cada línea (puede ser solo una parte). Se suma al inventario.")
        receipts: dict[str, float] = {}
        for r in pending.to_dict("records"):
            remaining = float(r["quantity"]) - float(r["received_qty"])
            c1, c2 = st.columns([4, 2])
            c1.markdown(
                f'<div class="mrp-row-name">{r["material_name"]}</div>'
                f'<div class="mrp-row-sub">pendiente: {remaining:g} {r.get("unit") or ""}</div>',
                unsafe_allow_html=True,
            )
            receipts[r["id"]] = c2.number_input(
                "Recibido ahora",
                min_value=0.0,
                max_value=remaining,
                value=0.0,
                step=1.0,
                key=f"recv_{r['id']}_{float(r['received_qty']):g}",
                label_visibility="collapsed",
            )
        b1, b2 = st.columns(2)
        if b1.button("Registrar lo indicado", use_container_width=True, key=f"recv_go_{order['id']}"):
            _receive(order["id"], order["code"], receipts)
        if b2.button("Recibir todo lo pendiente", type="primary", use_container_width=True, key=f"recv_all_{order['id']}"):
            _receive(
                order["id"],
                order["code"],
                {r["id"]: float(r["quantity"]) - float(r["received_qty"]) for r in pending.to_dict("records")},
            )


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
    supplier_rows = suppliers[suppliers["id"] == order["supplier_id"]]
    supplier = supplier_rows.to_dict("records")[0] if not supplier_rows.empty else None
    if supplier:
        st.markdown(ui.contact_links(supplier["phone"], supplier["email"]), unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Detalle</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Materiales del pedido</div>', unsafe_allow_html=True)
    items = repo.list_order_items(order_id)
    if items.empty:
        st.info("Esta orden no tiene líneas.")
    else:
        table = items[["material_name", "unit", "quantity", "received_qty", "unit_price", "subtotal"]].rename(
            columns={
                "material_name": "Material",
                "unit": "Unidad",
                "quantity": "Pedido",
                "received_qty": "Recibido",
                "unit_price": "Precio unit.",
                "subtotal": "Subtotal",
            }
        )
        for col in ["Pedido", "Recibido", "Precio unit.", "Subtotal"]:
            table[col] = table[col].astype(float)
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Pedido": st.column_config.NumberColumn(format="%.2f"),
                "Recibido": st.column_config.NumberColumn(format="%.2f"),
                "Precio unit.": st.column_config.NumberColumn(format="%.2f"),
                "Subtotal": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        if status in ("pendiente", "enviada", "parcial"):
            _render_reception(order, items)

    st.write("")
    b1, b2, b3, _ = st.columns([3, 2.2, 2, 1])
    if status == "pendiente" and b1.button("📤 Marcar como enviada", use_container_width=True):
        _change_status(order_id, order["code"], "enviada")
    if status in ("pendiente", "enviada", "parcial") and b2.button("Cancelar orden", use_container_width=True):
        _change_status(order_id, order["code"], "cancelada")
    if b3.button("🗑 Eliminar", use_container_width=True):
        ui.confirm_delete(
            f"¿Eliminar la orden {order['code']}? Se borran también sus líneas.",
            lambda oid=order_id, code=order["code"]: _delete_order(oid, code),
        )

    if not items.empty:
        d1, d2, d3, _ = st.columns([2, 2.6, 2.2, 1])
        d1.download_button(
            "📄 PDF",
            data=order_pdf(order, items, supplier),
            file_name=f"{order['code']}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        phone = re.sub(r"\D", "", (supplier or {}).get("phone") or "")
        d2.link_button(
            "💬 Enviar por WhatsApp",
            f"https://wa.me/{phone}?text={quote(order_whatsapp_text(order, items))}",
            use_container_width=True,
        )
        if d3.button("⧉ Duplicar", use_container_width=True, help="Crea una orden nueva con estos mismos materiales"):
            _duplicate(order, items)
