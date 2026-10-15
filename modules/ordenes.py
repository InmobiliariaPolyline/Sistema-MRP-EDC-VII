"""Módulo de Órdenes de compra: pedidos a un proveedor con sus líneas de
material (cantidad y precio), la obra destino y un estado que avanza de
pendiente a enviada, recibida (o parcial si llegó solo una parte) o cancelada.

Incluye comparador de cotizaciones al armar el pedido, recepción parcial por
línea (que alimenta el inventario), duplicar una orden, PDF de la orden y
mensaje listo para WhatsApp."""
import math
import re
from datetime import date
from urllib.parse import quote

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import attachments_ui, forms, sugerencias, ui
from utils import money, pricing
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


def price_max_age() -> int:
    """Vigencia de las cotizaciones en días (se ajusta en la ficha del proveedor)."""
    return int(st.session_state.get("price_max_age", pricing.DEFAULT_MAX_AGE_DAYS))


def alert_days() -> int:
    return int(st.session_state.get(ALERT_DAYS_KEY, DEFAULT_ALERT_DAYS))


def stale_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Órdenes todavía pendientes de enviar/recibir con más de X días de antigüedad."""
    if orders.empty:
        return orders
    open_orders = orders[orders["status"].isin(OPEN_STATUSES)]
    ages = open_orders["created_at"].map(lambda v: age_days(str(v)))
    return open_orders[ages > alert_days()].assign(age=ages[ages > alert_days()])


def _days_late(row) -> int:
    """Días de atraso de una orden abierta respecto de su fecha prometida (0 si no hay fecha o no se pasó)."""
    expected = row.get("expected_date")
    if not expected or str(expected) in ("None", "nan", "NaT") or row.get("status") not in OPEN_STATUSES:
        return 0
    try:
        return max((date.today() - date.fromisoformat(str(expected)[:10])).days, 0)
    except ValueError:
        return 0


def late_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Órdenes abiertas cuya fecha prometida de entrega ya pasó."""
    if orders.empty or "expected_date" not in orders.columns:
        return orders.iloc[0:0]
    days = orders.apply(_days_late, axis=1)
    return orders[days > 0].assign(days_late=days[days > 0])


def attention_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Órdenes que piden atención: sin cerrarse tras X días desde que se crearon o pasadas de su fecha prometida."""
    if orders.empty:
        return orders
    ids = set(stale_orders(orders)["id"]) | set(late_orders(orders)["id"])
    return orders[orders["id"].isin(ids)]


def _terms_inputs(prefix: str, expected_date=None, currency: str = money.BASE, exchange_rate: float = 3.75, tax_rate: float = 0.0) -> dict:
    """Fecha prometida, moneda, tipo de cambio e IGV de una orden. Devuelve las condiciones para guardar."""
    default_date = None
    if expected_date and str(expected_date) not in ("None", "nan", "NaT"):
        try:
            default_date = date.fromisoformat(str(expected_date)[:10])
        except ValueError:
            default_date = None
    c1, c2, c3 = st.columns([2, 2, 2])
    picked = c1.date_input(
        "Fecha prometida de entrega (opcional)", value=default_date, key=f"{prefix}_date", format="DD/MM/YYYY",
        min_value=date.today() if not default_date or default_date >= date.today() else None,
        help="Cuándo prometió entregar el proveedor. Si pasa y la orden sigue abierta, se marca como atrasada.",
    )
    currencies = list(money.CURRENCIES)
    chosen = c2.selectbox(
        "Moneda", currencies, index=currencies.index(currency) if currency in currencies else 0, key=f"{prefix}_currency",
        format_func=lambda c: money.CURRENCY_NAMES[c],
        help="Los precios del catálogo del proveedor se toman tal cual en esta moneda. Elige dólares solo si ese proveedor cotiza en dólares.",
    )
    rate = 1.0
    if chosen != money.BASE:
        rate = c3.number_input(
            "Tipo de cambio (S/ por US$)", min_value=0.0, value=float(exchange_rate or 3.75), step=0.01, format="%.3f", key=f"{prefix}_rate",
            help="Sirve para sumar esta orden en soles en el dashboard y en el presupuesto de la obra.",
        )
    igv = st.checkbox(
        f"Sumar IGV ({money.IGV:.0%}) al total", value=float(tax_rate or 0) > 0, key=f"{prefix}_igv",
        help="Márcalo si los precios del proveedor NO incluyen IGV. Si ya lo incluyen, déjalo sin marcar.",
    )
    return {"expected_date": picked, "currency": chosen, "exchange_rate": rate, "tax_rate": money.IGV if igv else 0.0}


def _totals_block(subtotal: float, terms: dict) -> None:
    """Subtotal, IGV y total de una orden en su moneda (y en soles si es otra moneda)."""
    amounts = money.amounts(subtotal, terms["tax_rate"], terms["exchange_rate"])
    cur = terms["currency"]
    if terms["tax_rate"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Subtotal", money.fmt(amounts["subtotal"], cur))
        c2.metric(f"IGV ({terms['tax_rate']:.0%})", money.fmt(amounts["tax"], cur))
        c3.metric("Total", money.fmt(amounts["total"], cur))
    else:
        st.metric("Total del pedido", money.fmt(amounts["total"], cur))
    if cur != money.BASE:
        st.caption(f"Equivale a {money.fmt(amounts['total_base'], money.BASE)} al tipo de cambio {terms['exchange_rate']:g}.")


def _clear_order_draft() -> None:
    for key in (
        LINES_KEY, SUPPLIER_KEY, PRESET_KEY, "new_order_supplier", "new_order_site", "new_order_notes",
        "new_order_date", "new_order_currency", "new_order_rate", "new_order_igv",
    ):
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
        st.session_state["new_order_currency"] = preset.get("currency") or money.BASE
        st.session_state["new_order_rate"] = float(preset.get("exchange_rate") or 3.75)
        st.session_state["new_order_igv"] = float(preset.get("tax_rate") or 0) > 0
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

    forms.section("2. Entrega, moneda e IGV", "Todo opcional: la fecha prometida activa el aviso de atraso y el IGV se suma al total.")
    terms = _terms_inputs("new_order")

    forms.section("3. Agrega materiales", "La cantidad se indica en la unidad del material. El precio unitario viene fijo del catálogo del proveedor y no se cambia aquí: lo que sube con la cantidad es el total. Agregar de nuevo un material suma cantidades.")
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
            st.caption(f"Esta selección: {qty:g} {record['metric_label'] or 'unid.'} × {money.fmt(price, terms['currency'])} = **{money.fmt(qty * price, terms['currency'])}**")
        if catalog_price > 0 and pricing.is_stale(record.get("price_updated_at"), price_max_age()):
            st.warning(
                f"Este precio está vencido ({pricing.describe(record.get('price_updated_at'), price_max_age())}). "
                "Confirma la cotización con el proveedor antes de comprar.",
                icon=":material/history:",
            )
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
                            "price_updated_at": record.get("price_updated_at"),
                        }
                    )
                st.rerun(scope="fragment")

    forms.section("4. Revisa y crea", "Comprueba las cantidades, el destino y el total del pedido.")
    total = 0.0
    for index, line in enumerate(lines):
        subtotal = line["quantity"] * line["unit_price"]
        total += subtotal
        l1, l2, l3 = st.columns([6, 3, 1])
        l1.write(f"{line['material_name']}  ·  {line['quantity']:g} {line['unit'] or ''} × {line['unit_price']:,.2f}")
        l2.write(f"**{money.fmt(subtotal, terms['currency'])}**")
        if l3.button("✖", key=f"oline_del_{index}", help="Quitar línea"):
            lines.pop(index)
            st.rerun(scope="fragment")
    if lines:
        _totals_block(total, terms)
        st.caption(f"{len(lines)} material(es) · Proveedor: {supplier_name} · Destino: {site_choice}")
        if site_choice != NO_SITE:
            _budget_warning(sites.loc[sites["name"] == site_choice, "id"].iloc[0], site_choice, lines, total * terms["exchange_rate"])
        if any(line["unit_price"] == 0 for line in lines):
            st.warning("Hay materiales con precio 0. El total solo incluye los precios registrados.")
        stale_lines = [line["material_name"] for line in lines if pricing.is_stale(line.get("price_updated_at"), price_max_age())]
        if stale_lines:
            st.warning(
                f"Cotizaciones con más de {price_max_age()} días sin actualizarse: {', '.join(stale_lines)}. Conviene confirmar el precio con el proveedor.",
                icon=":material/history:",
            )
        totals = _supplier_totals(lines, offers)
        if len(totals) > 1:
            cheapest_name, cheapest_total = totals[0]
            mine = next((t for n, t in totals if n == supplier_name), None)
            with st.expander("💡 Este mismo pedido con otros proveedores", expanded=cheapest_name != supplier_name):
                st.dataframe(
                    pd.DataFrame({"Proveedor": [("⭐ " if i == 0 else "") + n for i, (n, _) in enumerate(totals)], "Total del pedido (sin IGV)": [t for _, t in totals]}),
                    hide_index=True,
                    width="stretch",
                    column_config={"Total del pedido (sin IGV)": st.column_config.NumberColumn(format="%.2f")},
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
        try:
            code = repo.create_order(supplier_id, supplier_name, site_id, notes.strip() or None, lines, terms)
        except ValueError as exc:
            st.error(f"No se pudo crear la orden: {exc}")
            return
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
    ordered = float(site_orders["subtotal_base"].astype(float).sum()) if not site_orders.empty else 0.0
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
    planned_qty = budgets.assign(planned_qty=budgets["planned_qty"].astype(float)).groupby("material_id")["planned_qty"].sum().to_dict()
    over = [
        f"{line['material_name']} ({already.get(line['material_id'], 0) + line['quantity']:g} de {planned_qty[line['material_id']]:g})"
        for line in lines
        if line.get("material_id") in planned_qty and already.get(line["material_id"], 0) + line["quantity"] > planned_qty[line["material_id"]] + 1e-9
    ]
    if over:
        st.warning("Materiales por encima de su cantidad presupuestada para esta obra: " + ", ".join(over) + ".", icon=":material/warning:")


def _edit_state_keys(order_id: str) -> list[str]:
    return [f"edit_draft_{order_id}", f"edit_ver_{order_id}", f"edit_site_{order_id}", f"edit_notes_{order_id}",
            f"edit_add_mat_{order_id}", f"edit_add_qty_{order_id}", f"edit_{order_id}_date", f"edit_{order_id}_currency",
            f"edit_{order_id}_rate", f"edit_{order_id}_igv"]


def _clear_edit_draft(order_id: str) -> None:
    for key in _edit_state_keys(order_id):
        st.session_state.pop(key, None)
    for key in [k for k in st.session_state if str(k).startswith(f"edit_lines_{order_id}")]:
        st.session_state.pop(key, None)


@st.dialog("Editar orden", width="large")
def _edit_order_dialog(order: dict, items: pd.DataFrame) -> None:
    """Corrige una orden que todavía no recibió material: obra, notas, cantidades, quitar líneas y
    agregar materiales del catálogo del proveedor (con su precio fijo)."""
    oid = order["id"]
    draft_key, ver_key = f"edit_draft_{oid}", f"edit_ver_{oid}"
    if draft_key not in st.session_state:
        st.session_state[draft_key] = [
            {
                "material_id": r.get("material_id"), "material_name": r["material_name"], "unit": r.get("unit"),
                "quantity": float(r["quantity"]), "unit_price": float(r["unit_price"]), "remove": False,
            }
            for r in items.to_dict("records")
        ]
        st.session_state[ver_key] = 0
    draft: list[dict] = st.session_state[draft_key]

    forms.header(
        f"Editar {order['code']}",
        "Solo se puede mientras la orden no haya recibido material. Puedes cambiar cantidades, quitar líneas y agregar materiales; el precio unitario siempre es el del catálogo del proveedor.",
    )
    sites = repo.list_project_sites()
    site_names = [NO_SITE] + sites["name"].tolist()
    current = order.get("site_name") if order.get("site_name") in site_names else NO_SITE
    forms.section("1. Destino y notas", "Cambia la obra destino o las notas de la orden.")
    site_choice = st.selectbox("Obra destino (opcional)", site_names, index=site_names.index(current), key=f"edit_site_{oid}")
    notes = st.text_input("Notas (opcional)", value=order.get("notes") or "", max_chars=forms.RULES["Notas (opcional)"]["max"], key=f"edit_notes_{oid}")

    forms.section("2. Entrega, moneda e IGV", "Cambia la fecha prometida, la moneda o si se suma IGV.")
    terms = _terms_inputs(
        f"edit_{oid}", order.get("expected_date"), order.get("currency") or money.BASE, order.get("exchange_rate") or 3.75, order.get("tax_rate") or 0.0
    )

    forms.section("3. Materiales de la orden", "Ajusta las cantidades. Marca «Quitar» para eliminar una línea al guardar.")
    table = pd.DataFrame(
        {
            "Quitar": [bool(l["remove"]) for l in draft],
            "Material": [l["material_name"] for l in draft],
            "Unidad": [l.get("unit") or "" for l in draft],
            "Cantidad": [float(l["quantity"]) for l in draft],
            "Precio unit.": [float(l["unit_price"]) for l in draft],
        }
    )
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key=f"edit_lines_{oid}_{st.session_state[ver_key]}",
        disabled=["Material", "Unidad", "Precio unit."],
        column_config={
            "Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Precio unit.": st.column_config.NumberColumn(format="%.2f", help="Fijo: viene del catálogo del proveedor."),
        },
    )

    def sync() -> None:
        """Pasa al borrador lo que se editó en la tabla (cantidades y «Quitar»)."""
        for i, row in edited.reset_index(drop=True).iterrows():
            draft[i]["quantity"] = float(row["Cantidad"])
            draft[i]["remove"] = bool(row["Quitar"])

    forms.section("4. Agregar material", "Elige un material del catálogo de este proveedor. Si ya está en la orden, se suma a su cantidad.")
    catalog = repo.get_supplier_catalog(order["supplier_id"]) if order.get("supplier_id") else pd.DataFrame()
    offered = catalog[catalog["offered"]] if not catalog.empty else catalog
    if offered.empty:
        st.caption("El proveedor de esta orden ya no existe o no tiene materiales en su catálogo: solo puedes editar cantidades.")
    else:
        options = {f"{r['category']} · {r['name']}": r for r in offered.to_dict("records")}
        a1, a2, a3 = st.columns([4, 2, 2])
        choice = a1.selectbox("Material", list(options), key=f"edit_add_mat_{oid}")
        record = options[choice]
        qty = a2.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, key=f"edit_add_qty_{oid}",
                              help=f"Unidad: {record['metric_label'] or 'unid.'}. Debe ser mayor que 0.")
        existing = next((l for l in draft if l["material_id"] == record["id"]), None)
        catalog_price = float(record["price"]) if pd.notna(record["price"]) else 0.0
        shown = existing["unit_price"] if existing else catalog_price
        a3.number_input("Precio unit.", value=float(shown), format="%.2f", disabled=True, key=f"edit_add_price_{oid}_{record['id']}",
                        help="Fijo: precio del catálogo del proveedor (o el que ya tiene la línea de la orden).")
        if not existing and catalog_price <= 0:
            st.warning("Este material no tiene precio en el catálogo del proveedor. Regístralo en Proveedores → Catálogo para poder agregarlo.", icon=":material/sell:")
        if st.button("＋ Agregar a la orden", width="stretch", key=f"edit_add_btn_{oid}", disabled=(not existing and catalog_price <= 0)):
            issues = forms.validate({"Cantidad": qty})
            if not forms.errors(issues):
                sync()
                if existing:
                    existing["quantity"] += qty
                    existing["remove"] = False
                else:
                    draft.append(
                        {
                            "material_id": record["id"], "material_name": record["name"], "unit": record["metric_label"] or None,
                            "quantity": float(qty), "unit_price": catalog_price, "remove": False,
                        }
                    )
                st.session_state[ver_key] += 1  # la tabla se reconstruye con el borrador actualizado
                st.rerun(scope="fragment")

    kept = edited[~edited["Quitar"]]
    total = float((kept["Cantidad"] * kept["Precio unit."]).sum())
    _totals_block(total, terms)
    st.caption(f"{len(kept)} material(es) en la orden. Al guardar, el mensaje de WhatsApp y el PDF se arman con estos datos.")

    cancel, save = st.columns([1, 2])
    if cancel.button("Cancelar", key=f"edit_cancel_{oid}", width="stretch"):
        _clear_edit_draft(oid)
        st.rerun()
    if save.button("Guardar cambios", type="primary", width="stretch", key=f"edit_save_{oid}"):
        issues = forms.validate({"Notas (opcional)": notes})
        if kept.empty:
            issues.append("Materiales: la orden debe conservar al menos un material (para quitarla por completo, elimínala).")
        for _, row in kept.iterrows():
            issues.extend(f"{row['Material']}: {i}" for i in forms.validate({"Cantidad": row["Cantidad"], "Precio unit.": row["Precio unit."]}))
        if forms.errors(issues):
            return
        sync()
        new_items = [
            {
                "material_id": l["material_id"], "material_name": l["material_name"], "unit": l.get("unit"),
                "quantity": float(l["quantity"]), "unit_price": float(l["unit_price"]),
            }
            for l in draft if not l["remove"]
        ]
        site_id = None if site_choice == NO_SITE else sites.loc[sites["name"] == site_choice, "id"].iloc[0]
        try:
            repo.update_order(oid, site_id, notes.strip() or None, new_items, terms)
        except ValueError as exc:
            st.error(str(exc))
            return
        _clear_edit_draft(oid)
        reminder = " Reenvía el pedido actualizado al proveedor." if order["status"] == "enviada" else ""
        ui.flash(f"Orden {order['code']} actualizada.{reminder}", "✏️")
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
        "currency": order.get("currency"),
        "exchange_rate": order.get("exchange_rate"),
        "tax_rate": order.get("tax_rate"),
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
    late = late_orders(df)
    if not late.empty:
        st.error(f"📅 {len(late)} orden(es) pasaron su fecha prometida de entrega: {', '.join(late['code'].tolist()[:6])}", icon=":material/event_busy:")
    late_days = dict(zip(late["id"], late["days_late"])) if not late.empty else {}

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
                if row["id"] in late_days:
                    pills += " " + ui.pill(f"📅 {int(late_days[row['id']])} d de atraso", "red")
                elif row.get("expected_date") and row["status"] in OPEN_STATUSES:
                    pills += " " + ui.pill(f"📅 entrega {str(row['expected_date'])[8:10]}/{str(row['expected_date'])[5:7]}", "gray")
                if row.get("site_name"):
                    pills += " " + ui.pill(row["site_name"], "gray")
                st.markdown(pills, unsafe_allow_html=True)
            with c3:
                st.markdown(
                    f'<div class="mrp-row-name">{money.fmt(row["total"], row.get("currency"))}</div><div class="mrp-row-sub">total{" con IGV" if float(row.get("tax_rate") or 0) else ""}</div>',
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

def _mark_sent_from_link(order_id: str, code: str, status: str) -> None:
    """Al abrir WhatsApp con el pedido, la orden pendiente pasa sola a «enviada» y anota la hora de envío."""
    if status != "pendiente":
        return
    try:
        repo.set_order_status(order_id, "enviada")
        ui.flash(f"Orden {code}: marcada como enviada al abrir WhatsApp.", "📤")
    except Exception:  # abrir WhatsApp nunca debe fallar por esto
        pass


def _sent_text(value) -> str:
    text = str(value or "")
    if not text or text in ("None", "nan", "NaT"):
        return ""
    return f"{text[8:10]}/{text[5:7]}/{text[:4]} {text[11:16]}".strip()


def _change_status(order_id: str, code: str, status: str) -> None:
    repo.set_order_status(order_id, status)
    ui.flash(f"Orden {code}: {STATUSES[status][0].lower()}.", "🔄")
    st.rerun()


def _receive(order_id: str, code: str, receipts: dict[str, float], receipt: dict | None = None) -> None:
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
    try:
        status = repo.receive_order_items(order_id, valid_receipts, ui.current_actor(), receipt)
    except ValueError as exc:
        st.error(f"No se pudo registrar la recepción: {exc}")
        return
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
        forms.section("2. Documento de la entrega", "Opcional pero recomendable: queda guardado con la recepción para poder revisarla después.")
        d1, d2 = st.columns(2)
        doc_ref = d1.text_input("N.º de guía o factura", placeholder="Ej. T001-004521", max_chars=80, key=f"recv_doc_{order['id']}")
        delivered_by = d2.text_input("Entregado por", placeholder="Ej. chofer Luis Prado", max_chars=120, key=f"recv_by_{order['id']}")
        recv_notes = st.text_input(
            "Observaciones (faltantes, daños…)", placeholder="Ej. 2 bolsas rotas; faltó 1 varilla", max_chars=500, key=f"recv_notes_{order['id']}"
        )

        forms.section("3. Revisa la entrega", "Confirma estas cantidades antes de actualizar el stock.")
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
            _receive(order["id"], order["code"], receipts, {"document_ref": doc_ref, "delivered_by": delivered_by, "notes": recv_notes})


def _render_receipts(order_id: str) -> None:
    """Recepciones ya registradas de la orden, con su documento y observaciones."""
    receipts = repo.list_receipts(order_id)
    if receipts.empty:
        return
    with st.expander(f"🧾 Recepciones registradas ({len(receipts)})"):
        for r in receipts.to_dict("records"):
            when = str(r["received_at"])[:16].replace("T", " ")
            pills = ui.pill(r["document_ref"], "blue") if r.get("document_ref") else ui.pill("sin documento", "gray")
            st.markdown(f"**{when}** · registró {r.get('actor') or 'sistema'} &nbsp; {pills}", unsafe_allow_html=True)
            detail = " · ".join(x for x in [r.get("delivered_by") and f"entregó {r['delivered_by']}", r.get("notes") and f"observaciones: {r['notes']}"] if x)
            if detail:
                st.caption(detail)


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
            ui.stat_card("💰", money.fmt(order["total"], order.get("currency")), "Total con IGV" if float(order.get("tax_rate") or 0) else "Total"),
        ]
    )
    if _sent_text(order.get("sent_at")):
        st.caption(f"📤 Enviada al proveedor el {_sent_text(order['sent_at'])}.")
    late_by = _days_late(order)
    if order.get("expected_date") and status in OPEN_STATUSES:
        when = f"{str(order['expected_date'])[8:10]}/{str(order['expected_date'])[5:7]}/{str(order['expected_date'])[:4]}"
        if late_by:
            st.error(f"Entrega prometida para el {when}: lleva {late_by} día(s) de atraso.", icon=":material/event_busy:")
        else:
            st.caption(f"📅 Entrega prometida para el {when}.")
    if float(order.get("tax_rate") or 0) or (order.get("currency") or money.BASE) != money.BASE:
        parts = [f"Subtotal {money.fmt(order['subtotal'], order.get('currency'))}"]
        if float(order.get("tax_rate") or 0):
            parts.append(f"IGV {float(order['tax_rate']):.0%} {money.fmt(order['tax'], order.get('currency'))}")
        if (order.get("currency") or money.BASE) != money.BASE:
            parts.append(f"equivale a {money.fmt(order['total_base'], money.BASE)} (tipo de cambio {float(order['exchange_rate']):g})")
        st.caption(" · ".join(parts))
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

    _render_receipts(order_id)
    attachments_ui.render("orden", order_id)

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
        if b4.button("✏️ Editar orden", width="stretch", help="Agrega, quita o cambia la cantidad de materiales, la obra o las notas mientras no haya recibido material."):
            _clear_edit_draft(order_id)  # cada vez que se abre parte de lo guardado
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
            on_click=_mark_sent_from_link,
            args=(order_id, order["code"], status),
            help="Abre WhatsApp con el pedido y, si la orden estaba pendiente, la marca como enviada con la hora." if status == "pendiente" else None,
        )
        if d3.button("⧉ Duplicar", width="stretch", help="Crea una orden nueva con estos mismos materiales"):
            _duplicate(order, items)
