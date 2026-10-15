"""Módulo de Órdenes de compra: pedidos a un proveedor con sus líneas de
material (cantidad y precio), la obra destino y un estado que avanza de
pendiente a enviada, recibida (o parcial si llegó solo una parte) o cancelada.

Incluye comparador de cotizaciones al armar el pedido, recepción parcial por
línea (que alimenta el inventario), duplicar una orden, PDF de la orden y
mensaje listo para WhatsApp."""
import math
import re
from urllib.parse import quote

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, sugerencias, ui
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


def _clear_order_draft() -> None:
    for key in (LINES_KEY, SUPPLIER_KEY, PRESET_KEY, "new_order_supplier", "new_order_site", "new_order_notes"):
        st.session_state.pop(key, None)


def _clear_filters() -> None:
    st.session_state["ord_q"] = ""
    st.session_state["ord_status"] = ALL_STATUSES


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
        _clear_order_draft()
        _new_order_dialog()
    elif st.session_state.get(PRESET_KEY):
        _new_order_dialog()
    if st.button("Sugerencia de compra", key="open_suggestions", icon=":material/lightbulb:",
                 help="Calcula qué falta pedir según los presupuestos de las obras, el stock y lo que ya viene en camino."):
        sugerencias.suggestion_dialog()

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
        st.dataframe(table, hide_index=True, width="stretch", column_config={"Precio": st.column_config.NumberColumn(format="%.2f")})
        mine = rows[rows["supplier_id"] == current_supplier_id]
        if best["supplier_id"] != current_supplier_id and not mine.empty:
            mine_price = float(mine.iloc[0]["price"])
            saving = (1 - float(best["price"]) / mine_price) * 100
            st.caption(f"{best['supplier_name']} lo ofrece {saving:.0f}% más barato ({float(best['price']):,.2f} vs {mine_price:,.2f}). Cambia el proveedor arriba si te conviene.")


@st.dialog("Nueva orden de compra", width="large")
def _new_order_dialog() -> None:
    forms.header("Prepara tu pedido", "Elige el destino, agrega los materiales y revisa el total antes de crear la orden.")
    suppliers = repo.list_suppliers()
    if suppliers.empty:
        ui.empty_state("Falta un proveedor", "Registra uno en Proveedores para preparar tu primera orden.", icon="🏭")
        if st.button("Cancelar", key="order_cancel_empty", width="stretch"):
            _clear_order_draft()
            st.rerun()
        return
    ui.tip("Ejemplo: elige el proveedor, la obra destino, luego un material con cantidad 12 y pulsa «Agregar al pedido». Repite por cada material y al final «Crear orden».")
    sites = repo.list_project_sites()
    offers = repo.list_offers()

    preset = st.session_state.pop(PRESET_KEY, None)
    if preset:  # viene de «Duplicar»: precarga proveedor, obra, notas y líneas
        st.session_state["new_order_supplier"] = preset["supplier_name"]
        st.session_state["new_order_site"] = preset["site_name"] if preset["site_name"] in sites["name"].tolist() else NO_SITE
        st.session_state["new_order_notes"] = preset["notes"] or ""
        st.session_state[SUPPLIER_KEY] = preset["supplier_id"]
        st.session_state[LINES_KEY] = preset["lines"]

    forms.section("1. Proveedor y destino", "Toda la orden corresponde a un proveedor. La obra destino es opcional.")
    supplier_name = st.selectbox("Proveedor", suppliers["name"].tolist(), key="new_order_supplier",
                                 help="Al cambiar de proveedor se vacían los materiales del borrador para revisar sus precios.")
    supplier_id = suppliers.loc[suppliers["name"] == supplier_name, "id"].iloc[0]
    if st.session_state.get(SUPPLIER_KEY) != supplier_id:
        if st.session_state.get(LINES_KEY):
            st.warning("Cambiaste de proveedor: vuelve a agregar los materiales con sus nuevas cotizaciones.")
        st.session_state[SUPPLIER_KEY] = supplier_id
        st.session_state[LINES_KEY] = []
    lines: list[dict] = st.session_state.setdefault(LINES_KEY, [])

    site_choice = st.selectbox("Obra destino (opcional)", [NO_SITE] + sites["name"].tolist(), key="new_order_site",
                               help="Asigna una obra para incluir esta compra en su control de presupuesto.")
    notes = st.text_input("Notas (opcional)", placeholder="Ej. Entregar antes del viernes", key="new_order_notes", max_chars=500,
                          help="Condiciones de entrega o indicaciones para el proveedor. Hasta 500 caracteres.")

    forms.section("2. Agrega materiales", "La cantidad se indica en la unidad del material. El precio unitario viene fijo del catálogo del proveedor y no se cambia aquí: lo que sube con la cantidad es el total. Agregar de nuevo un material suma cantidades.")
    catalog = repo.get_supplier_catalog(supplier_id)
    offered = catalog[catalog["offered"]] if not catalog.empty else catalog
    if offered.empty:
        st.warning("Este proveedor todavía no tiene materiales asignados. Márcalos como «Lo ofrece» en su catálogo.")
    else:
        options = {f"{r['category']} · {r['name']}": r for r in offered.to_dict("records")}
        c1, c2, c3 = st.columns([4, 2, 2])
        choice = c1.selectbox("Material", list(options))
        record = options[choice]
        qty = c2.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, key=f"oqty_{record['id']}",
                               help=f"Unidad: {record['metric_label'] or 'unid.'}. Admite decimales; debe ser mayor que 0.")
        catalog_price = float(record["price"]) if pd.notna(record["price"]) else 0.0
        # El precio unitario es el del catálogo del proveedor y no se puede modificar al comprar:
        # solo informa. Para cambiarlo se edita en la ficha del proveedor.
        price = catalog_price
        c3.number_input(
            "Precio unit.", value=catalog_price, format="%.2f", disabled=True, key=f"oprice_{supplier_id}_{record['id']}",
            help="Fijo: es el precio del catálogo de este proveedor. Para cambiarlo, edítalo en su ficha (Proveedores → Catálogo).",
        )
        if catalog_price <= 0:
            st.warning(
                "Este material no tiene precio en el catálogo del proveedor, así que no se puede agregar. "
                "Regístralo en Proveedores → Catálogo (o importa su lista de precios) y vuelve.",
                icon=":material/sell:",
            )
        else:
            st.caption(f"Esta selección: {qty:g} {record['metric_label'] or 'unid.'} × {price:,.2f} = **{qty * price:,.2f}**")
        if not record.get("available", True):
            st.caption("El catálogo indica que este material no está disponible. Confirma la entrega con el proveedor.")
        _material_quotes(record["id"], supplier_id, offers)
        if st.button("＋ Agregar al pedido", width="stretch", disabled=catalog_price <= 0):
            existing = next((ln for ln in lines if ln["material_id"] == record["id"]), None)
            issues = forms.validate({"Cantidad": qty, "Precio unit.": price})
            if existing:
                issues.extend(forms.validate({"Cantidad": existing["quantity"] + qty}))
            line_qty = qty + (existing["quantity"] if existing else 0)
            if not math.isfinite(line_qty * price):
                issues.append("Subtotal: revisa la cantidad y el precio para obtener un total finito.")
            if not forms.errors(issues):
                if existing:
                    existing["quantity"] += qty
                    existing["unit_price"] = price  # siempre el precio vigente del catálogo
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

    forms.section("3. Revisa y crea", "Comprueba las cantidades, el destino y el total del pedido.")
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
        st.metric("Total del pedido", f"{total:,.2f}")
        st.caption(f"{len(lines)} material(es) · Proveedor: {supplier_name} · Destino: {site_choice}")
        if site_choice != NO_SITE:
            _budget_warning(sites.loc[sites["name"] == site_choice, "id"].iloc[0], site_choice, lines, total)
        if any(line["unit_price"] == 0 for line in lines):
            st.warning("Hay materiales con precio 0. El total solo incluye los precios registrados.")
        totals = _supplier_totals(lines, offers)
        if len(totals) > 1:
            cheapest_name, cheapest_total = totals[0]
            mine = next((t for n, t in totals if n == supplier_name), None)
            with st.expander("💡 Este mismo pedido con otros proveedores", expanded=cheapest_name != supplier_name):
                st.dataframe(
                    pd.DataFrame({"Proveedor": [("⭐ " if i == 0 else "") + n for i, (n, _) in enumerate(totals)], "Total del pedido": [t for _, t in totals]}),
                    hide_index=True,
                    width="stretch",
                    column_config={"Total del pedido": st.column_config.NumberColumn(format="%.2f")},
                )
                if mine is not None and cheapest_name != supplier_name:
                    st.caption(f"Con {cheapest_name} ahorrarías {mine - cheapest_total:,.2f} en todo el pedido.")

    else:
        ui.empty_state("Tu pedido está vacío", "Selecciona un material y pulsa «Agregar al pedido». Después podrás crear la orden.", icon="🧾")

    cancel, save = st.columns([1, 2])
    if cancel.button("Cancelar", key="order_cancel", width="stretch"):
        _clear_order_draft()
        st.rerun()
    if save.button("Crear orden", type="primary", width="stretch", disabled=not lines):
        issues = forms.validate({"Notas (opcional)": notes})
        if not lines:
            issues.append("Materiales del pedido: agrega al menos un material.")
        for line in lines:
            issues.extend(f"{line['material_name']}: {issue}" for issue in forms.validate({"Cantidad": line["quantity"], "Precio unit.": line["unit_price"]}))
        if not math.isfinite(total):
            issues.append("Total del pedido: revisa las cantidades y precios para obtener un total finito.")
        if forms.errors(issues):
            return
        site_id = None if site_choice == NO_SITE else sites.loc[sites["name"] == site_choice, "id"].iloc[0]
        code = repo.create_order(supplier_id, supplier_name, site_id, notes.strip() or None, lines)
        _clear_order_draft()
        ui.flash(f"Orden {code} creada.", "🧾")
        st.rerun()


def _budget_warning(site_id: str, site_name: str, lines: list[dict], total: float) -> None:
    """Avisa si esta orden hace que la obra supere lo presupuestado (en costo total o por material)."""
    budgets = repo.list_budgets(site_id)
    if budgets.empty:
        return
    planned = float((budgets["planned_qty"].astype(float) * budgets["planned_unit_price"].astype(float)).sum())
    orders = repo.list_orders()
    site_orders = orders[(orders["project_site_id"] == site_id) & (orders["status"] != "cancelada")] if not orders.empty else orders
    ordered = float(site_orders["total"].astype(float).sum()) if not site_orders.empty else 0.0
    if planned > 0 and ordered + total > planned + 1e-9:
        st.warning(
            f"Con esta orden, «{site_name}» pasaría lo presupuestado: previsto {planned:,.2f}, ya pedido {ordered:,.2f} + esta orden {total:,.2f} "
            f"= {ordered + total:,.2f} ({(ordered + total) / planned * 100:.0f} %).",
            icon=":material/warning:",
        )
    items = repo.list_order_items()
    ids = set(site_orders["id"]) if not site_orders.empty else set()
    already: dict[str, float] = {}
    if not items.empty:
        for row in items[items["order_id"].isin(ids)].to_dict("records"):
            if row.get("material_id"):
                already[row["material_id"]] = already.get(row["material_id"], 0.0) + float(row["quantity"])
    planned_qty = budgets.set_index("material_id")["planned_qty"].astype(float).to_dict()
    over = [
        f"{line['material_name']} ({already.get(line['material_id'], 0) + line['quantity']:g} de {planned_qty[line['material_id']]:g})"
        for line in lines
        if line.get("material_id") in planned_qty and already.get(line["material_id"], 0) + line["quantity"] > planned_qty[line["material_id"]] + 1e-9
    ]
    if over:
        st.warning("Materiales por encima de su cantidad presupuestada para esta obra: " + ", ".join(over) + ".", icon=":material/warning:")


@st.dialog("Editar orden", width="large")
def _edit_order_dialog(order: dict, items: pd.DataFrame) -> None:
    """Corrige obra, notas, cantidades y precios de una orden que todavía no recibió material."""
    forms.header(f"Editar {order['code']}", "Solo se puede mientras la orden no haya recibido material. Puedes cambiar las cantidades o quitar líneas; el precio unitario es el del catálogo y no se modifica.")
    sites = repo.list_project_sites()
    site_names = [NO_SITE] + sites["name"].tolist()
    current = order.get("site_name") if order.get("site_name") in site_names else NO_SITE
    forms.section("1. Destino y notas", "Cambia la obra destino o las notas de la orden.")
    site_choice = st.selectbox("Obra destino (opcional)", site_names, index=site_names.index(current), key=f"edit_site_{order['id']}")
    notes = st.text_input("Notas (opcional)", value=order.get("notes") or "", max_chars=forms.RULES["Notas (opcional)"]["max"], key=f"edit_notes_{order['id']}")

    forms.section("2. Líneas", "Ajusta las cantidades. Las líneas marcadas con «Quitar» se eliminan al guardar. El precio unitario queda como estaba al hacer la orden.")
    records = items.to_dict("records")
    table = pd.DataFrame(
        {
            "Quitar": False,
            "Material": [r["material_name"] for r in records],
            "Unidad": [r.get("unit") or "" for r in records],
            "Cantidad": [float(r["quantity"]) for r in records],
            "Precio unit.": [float(r["unit_price"]) for r in records],
        }
    )
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key=f"edit_lines_{order['id']}", disabled=["Material", "Unidad", "Precio unit."],
        column_config={
            "Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Precio unit.": st.column_config.NumberColumn(format="%.2f", help="Fijo: viene del catálogo del proveedor."),
        },
    )
    kept = edited[~edited["Quitar"]]
    total = float((kept["Cantidad"] * kept["Precio unit."]).sum())
    st.metric("Total de la orden", f"{total:,.2f}")

    cancel, save = st.columns([1, 2])
    if cancel.button("Cancelar", key=f"edit_cancel_{order['id']}", width="stretch"):
        st.rerun()
    if save.button("Guardar cambios", type="primary", width="stretch", key=f"edit_save_{order['id']}"):
        issues = forms.validate({"Notas (opcional)": notes})
        if kept.empty:
            issues.append("Líneas: la orden debe conservar al menos un material (para quitarla por completo, elimínala).")
        for _, row in kept.iterrows():
            issues.extend(f"{row['Material']}: {i}" for i in forms.validate({"Cantidad": row["Cantidad"], "Precio unit.": row["Precio unit."]}))
        if forms.errors(issues):
            return
        new_items = [
            {
                "material_id": records[i].get("material_id"), "material_name": records[i]["material_name"], "unit": records[i].get("unit"),
                "quantity": float(row["Cantidad"]), "unit_price": float(row["Precio unit."]),
            }
            for i, row in kept.iterrows()
        ]
        site_id = None if site_choice == NO_SITE else sites.loc[sites["name"] == site_choice, "id"].iloc[0]
        try:
            repo.update_order(order["id"], site_id, notes.strip() or None, new_items)
        except ValueError as exc:
            st.error(str(exc))
            return
        ui.flash(f"Orden {order['code']} actualizada.", "✏️")
        st.rerun()


def _duplicate(order: dict, items: pd.DataFrame) -> None:
    """Prepara el diálogo de nueva orden con los datos de otra ya hecha."""
    suppliers = repo.list_suppliers()
    match = suppliers[suppliers["id"] == order["supplier_id"]]
    if match.empty:
        st.toast("El proveedor de esta orden ya no existe; no se puede duplicar.", icon="⚠️")
        return
    catalog = repo.get_supplier_catalog(order["supplier_id"])
    current = {}
    if not catalog.empty:
        for r in catalog[catalog["offered"]].to_dict("records"):
            if pd.notna(r["price"]) and float(r["price"]) > 0:
                current[r["id"]] = float(r["price"])
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
                "unit_price": current.get(r["material_id"], float(r["unit_price"])),  # precio vigente del catálogo
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
    try:
        repo.delete_order(order_id)
    except ValueError as exc:  # p. ej. ya recibió material: el stock quedaría descuadrado
        ui.flash(f"No se pudo eliminar {code}: {exc}", "⚠️", log=False)
        return
    if st.session_state.get(SELECTED_KEY) == order_id:
        st.session_state[SELECTED_KEY] = None
    ui.flash(f"Orden {code} eliminada.", "🗑️")


def _render_list() -> None:
    st.markdown('<div class="mrp-eyebrow">Historial</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Órdenes registradas</div>', unsafe_allow_html=True)

    df = repo.list_orders()
    if df.empty:
        ui.empty_state("Aún no tienes órdenes", "Usa «Nueva orden» para preparar un pedido y seguir su recepción.", icon="🧾")
        return

    total = len(df)
    f1, f2, f3 = st.columns([3, 2, 1.6])
    query = f1.text_input("Buscar", placeholder="Código, proveedor u obra…", key="ord_q")
    labels = {value[0]: key for key, value in STATUSES.items()}
    status_label = f2.selectbox("Estado", [ALL_STATUSES] + list(labels), key="ord_status")
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
    ui.result_count(len(df), total, noun="órdenes")
    if query or status_label != ALL_STATUSES:
        st.button("Limpiar filtros", key="ord_clear", on_click=_clear_filters)
    if df.empty:
        ui.empty_state("Sin coincidencias", "Prueba otro código o proveedor, o limpia los filtros para ver todas las órdenes.", icon="🔎")
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
                if st.button("Ver", key=f"open_order_{row['id']}", width="stretch"):
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
    # Las listas de Supabase usan caché: volver a leer antes de validar el saldo.
    for reader in (repo.list_orders, repo.list_order_items):
        clear = getattr(reader, "clear", None)
        if callable(clear):
            clear()
    orders = repo.list_orders()
    match = orders[orders["id"] == order_id]
    current = {r["id"]: r for r in repo.list_order_items(order_id).to_dict("records")}
    issues = []
    if match.empty or match.iloc[0]["status"] not in OPEN_STATUSES:
        issues.append("La orden ya no está abierta para recepción. Actualiza su detalle.")
    valid_receipts = {}
    for item_id, qty in receipts.items():
        row = current.get(item_id)
        label = row["material_name"] if row else "Línea del pedido"
        quantity_issues = forms.validate({"Recibido ahora": qty})
        issues.extend(f"{label}: {issue}" for issue in quantity_issues)
        if quantity_issues:
            continue
        qty = float(qty)
        if qty == 0:
            continue
        if row is None:
            issues.append(f"{label}: ya no pertenece a esta orden. Actualiza el detalle.")
            continue
        remaining = max(float(row["quantity"]) - float(row["received_qty"]), 0.0)
        if qty > remaining:
            issues.append(f"{label}: quedan {remaining:g} {row.get('unit') or 'unid.'}; no puedes recibir {qty:g}.")
        else:
            valid_receipts[item_id] = qty
    if not valid_receipts and not issues:
        issues.append("Recibido ahora: indica al menos una cantidad mayor que 0.")
    if forms.errors(issues):
        return
    status = repo.receive_order_items(order_id, valid_receipts, ui.current_actor())
    ui.flash(f"Orden {code}: recepción registrada ({STATUSES[status][0].lower()}). El stock se actualizó.", "📦")
    st.rerun()


def _render_reception(order: dict, items: pd.DataFrame) -> None:
    """Cuánto llegó de cada línea; suma al stock y deja la orden en parcial o recibida."""
    pending = items[items["quantity"].astype(float) - items["received_qty"].astype(float) > 1e-9]
    if pending.empty:
        return
    with st.expander("📦 Registrar recepción", expanded=order["status"] in ("enviada", "parcial")):
        forms.section("1. Indica lo que llegó", "Registra solo esta entrega. Las cantidades se sumarán al inventario al guardar.")
        records = pending.to_dict("records")
        keys = {r["id"]: f"recv_{r['id']}_{float(r['received_qty']):g}" for r in records}
        if st.button("Recibir todo lo pendiente", key=f"recv_all_{order['id']}",
                     help="Completa las cantidades del borrador. Revisa y pulsa «Registrar lo indicado» para guardar."):
            for r in records:
                st.session_state[keys[r["id"]]] = float(r["quantity"]) - float(r["received_qty"])
        receipts: dict[str, float] = {}
        for r in records:
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
                key=keys[r["id"]],
                help=f"Máximo pendiente: {remaining:g} {r.get('unit') or 'unid.'}. Usa 0 si este material no llegó.",
            )
        forms.section("2. Revisa la entrega", "Confirma estas cantidades antes de actualizar el stock.")
        arriving = [r for r in records if receipts[r["id"]] > 0]
        if arriving:
            st.dataframe(pd.DataFrame([{"Material": r["material_name"], "Unidad": r.get("unit") or "unid.",
                                       "Recibido ahora": receipts[r["id"]],
                                       "Pendiente después": max(float(r["quantity"]) - float(r["received_qty"]) - receipts[r["id"]], 0.0)}
                                      for r in arriving]), hide_index=True, width="stretch")
            st.caption(f"Se registrará la recepción de {len(arriving)} material(es).")
        else:
            st.caption("Indica las cantidades de esta entrega; 0 deja el material pendiente.")
        b1, b2 = st.columns(2)
        if b1.button("Cancelar", width="stretch", key=f"recv_cancel_{order['id']}"):
            for key in keys.values():
                st.session_state.pop(key, None)
            st.rerun()
        if b2.button("Registrar lo indicado", type="primary", width="stretch", key=f"recv_go_{order['id']}"):
            _receive(order["id"], order["code"], receipts)


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
            width="stretch",
            column_config={
                "Pedido": st.column_config.NumberColumn(format="%.2f"),
                "Recibido": st.column_config.NumberColumn(format="%.2f"),
                "Precio unit.": st.column_config.NumberColumn(format="%.2f"),
                "Subtotal": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        if status in ("pendiente", "enviada", "parcial"):
            _render_reception(order, items)

    received_any = bool(not items.empty and (items["received_qty"].astype(float) > 0).any())
    b1, b2, b3, b4 = st.columns([3, 2.2, 2, 1.8])
    if status == "pendiente" and b1.button("📤 Marcar como enviada", width="stretch"):
        _change_status(order_id, order["code"], "enviada")
    if status in ("pendiente", "enviada", "parcial") and b2.button("Cancelar orden", width="stretch"):
        _change_status(order_id, order["code"], "cancelada")
    if b3.button("🗑 Eliminar", width="stretch", disabled=received_any,
                 help="Ya recibió material: no se puede eliminar. Cancélala si el pedido no continúa." if received_any else None):
        ui.confirm_delete(
            f"¿Eliminar la orden {order['code']}? Se borran también sus líneas.",
            lambda oid=order_id, code=order["code"]: _delete_order(oid, code),
        )
    if status in ("pendiente", "enviada") and not received_any and not items.empty:
        if b4.button("✏️ Editar orden", width="stretch", help="Cambia cantidades, precios, obra o notas mientras no haya recibido material."):
            _edit_order_dialog(order, items)

    if not items.empty:
        d1, d2, d3, _ = st.columns([2, 2.6, 2.2, 1])
        d1.download_button(
            "📄 PDF",
            data=order_pdf(order, items, supplier),
            file_name=f"{order['code']}.pdf",
            mime="application/pdf",
            width="stretch",
        )
        phone = re.sub(r"\D", "", (supplier or {}).get("phone") or "")
        d2.link_button(
            "💬 Enviar por WhatsApp",
            f"https://wa.me/{phone}?text={quote(order_whatsapp_text(order, items))}",
            width="stretch",
        )
        if d3.button("⧉ Duplicar", width="stretch", help="Crea una orden nueva con estos mismos materiales"):
            _duplicate(order, items)
