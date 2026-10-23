"""Módulo de Órdenes de compra: pedidos a un proveedor con sus líneas de
material (cantidad y precio), la obra destino y un estado que avanza de
pendiente a enviada, recibida (o parcial si llegó solo una parte) o cancelada.

Un pedido puede juntar materiales de varios proveedores (carrito): al crearlo se genera una orden por proveedor.
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
from modules import attachments_ui, forms, orden_form, sugerencias, ui
from utils import audit, money, pricing, units
from utils.mail import mailto_url
from utils.reports import batch_pdf, order_pdf, order_whatsapp_text, payment_pdf, payment_schedule_pdf
from utils.timeago import age_days
from utils import clock

SELECTED_KEY = "selected_order_id"
BATCH_KEY = "selected_batch_code"
CART_KEY = "_order_cart"      # {id del proveedor: {"name", "lines", "terms"}}: el pedido en curso, agrupado por proveedor
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
NO_PAYMENT = orden_form.NO_PAYMENT


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
        return max((clock.today() - date.fromisoformat(str(expected)[:10])).days, 0)
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


def _terms_inputs(*args, **kwargs) -> dict:
    """Fecha prometida, moneda, IGV y forma de pago de una orden (ver `orden_form.terms_inputs`)."""
    return orden_form.terms_inputs(*args, **kwargs)


def _totals_block(subtotal: float, terms: dict) -> None:
    """Valor de venta, IGV e importe total de una orden, con su plan de pagos si lo tiene (ver `orden_form.totals_block`)."""
    orden_form.totals_block(subtotal, terms)


def _clear_order_draft() -> None:
    for key in [k for k in st.session_state if str(k).startswith("new_order_") and k != "new_order_open"]:
        st.session_state.pop(key, None)
    for key in (CART_KEY, PRESET_KEY):
        st.session_state.pop(key, None)


def _clear_filters() -> None:
    st.session_state["ord_q"] = ""
    st.session_state["ord_status"] = ALL_STATUSES


def render() -> None:
    if st.session_state.get(SELECTED_KEY):
        _render_detail(st.session_state[SELECTED_KEY])
        return
    if st.session_state.get(BATCH_KEY):
        _render_batch(st.session_state[BATCH_KEY])
        return

    clicked = ui.page_header(
        "Compras",
        "Órdenes de compra",
        "Pedidos a proveedores: qué materiales, cuántos, a qué precio y para qué obra.",
        action_label=":material/add: Nueva orden",
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

def _default_terms() -> dict:
    """Condiciones iniciales de un proveedor al que se le agrega un material sin haber pasado por su formulario."""
    rate, include = money.tax_from_mode("add")
    return {"expected_date": None, "currency": money.BASE, "exchange_rate": 1.0, "tax_rate": rate, "prices_include_tax": include, "payment_terms": None}


def _terms_defaults(terms: dict) -> dict:
    """Las condiciones guardadas de un proveedor → valores iniciales de sus controles."""
    return {
        "expected_date": terms.get("expected_date"), "currency": terms.get("currency") or money.BASE, "exchange_rate": terms.get("exchange_rate") or 3.75,
        "tax_mode": money.tax_mode(terms.get("tax_rate"), terms.get("prices_include_tax")), "payment_terms": terms.get("payment_terms"),
    }


def _jump_to_supplier(supplier_name: str, material_label: str | None = None) -> None:
    """Cambia el proveedor del que se agregan materiales (y, si se indica, deja elegido ese material). Lo ya agregado se conserva."""
    st.session_state["new_order_supplier"] = supplier_name
    if material_label:
        st.session_state["new_order_material"] = material_label


def _move_line(from_id: str, material_id: str, to_id: str, to_name: str, price: float, updated=None) -> None:
    """Pasa una línea del pedido a otro proveedor, con el precio de ese proveedor (suma la cantidad si ya tenía ese material)."""
    cart = st.session_state.get(CART_KEY, {})
    source = cart.get(from_id)
    line = next((ln for ln in source["lines"] if ln["material_id"] == material_id), None) if source else None
    if line is None:
        return
    source["lines"].remove(line)
    target = cart.setdefault(to_id, {"name": to_name, "lines": [], "terms": _default_terms()})
    same = next((ln for ln in target["lines"] if ln["material_id"] == material_id), None)
    if same:
        same["quantity"] += line["quantity"]
        same["unit_price"], same["price_updated_at"] = price, updated
    else:
        target["lines"].append({**line, "unit_price": price, "price_updated_at": updated})
    if not source["lines"]:
        cart.pop(from_id, None)


def _alternatives(offers: pd.DataFrame, material_id: str, current_supplier_id: str) -> list[dict]:
    """Otros proveedores que ofrecen este material con precio, del más barato al más caro."""
    if offers.empty:
        return []
    rows = offers[(offers["material_id"] == material_id) & (offers["supplier_id"] != current_supplier_id) & offers["price"].notna()]
    rows = rows[rows["price"].astype(float) > 0]
    return rows.assign(price=rows["price"].astype(float)).sort_values("price").to_dict("records")


def _material_quotes(record: dict, current_supplier_id: str, offers: pd.DataFrame, label: str) -> None:
    """Precio de este material en cada proveedor, con un botón para agregarlo desde el más barato sin perder lo ya elegido."""
    if offers.empty:
        return
    rows = offers[(offers["material_id"] == record["id"]) & offers["price"].notna()]
    rows = rows[rows["price"].astype(float) > 0]
    if len(rows) < 2:
        return
    rows = rows.assign(price=rows["price"].astype(float)).sort_values("price")
    best = rows.iloc[0]
    mine = rows[rows["supplier_id"] == current_supplier_id]
    mine_price = float(mine.iloc[0]["price"]) if not mine.empty else None
    cheaper = best["supplier_id"] != current_supplier_id and mine_price is not None
    with st.expander(f":material/lightbulb: Comparar cotizaciones ({len(rows)} proveedores)", expanded=cheaper):
        for index, row in enumerate(rows.to_dict("records")):
            is_mine = row["supplier_id"] == current_supplier_id
            c1, c2, c3, c4 = st.columns([3.2, 1.4, 2.4, 2.6], vertical_alignment="center")
            c1.markdown(f"**{row['supplier_name']}**" + (" · este proveedor" if is_mine else ""))
            c2.markdown(f"{float(row['price']):,.2f}")
            note = ui.pill("Más barato", "green") if index == 0 else ""
            if mine_price and not is_mine:
                delta = (float(row["price"]) / mine_price - 1) * 100
                note += ui.pill(f"{abs(delta):.0f} % {'menos' if delta < 0 else 'más'} que aquí", "green" if delta < 0 else "gray")
            if not row["available"]:
                note += ui.pill("No disponible", "red")
            c3.markdown(note, unsafe_allow_html=True)
            if not is_mine:
                c4.button(":material/swap_horiz: Agregar desde aquí", key=f"jump_{row['supplier_id']}", width="stretch", on_click=_jump_to_supplier,
                          args=(row["supplier_name"], label), help="Cambia de proveedor con este material elegido. Lo que ya agregaste se conserva.")
        if cheaper:
            saving = (1 - float(best["price"]) / mine_price) * 100
            st.caption(f"{best['supplier_name']} lo ofrece {saving:.0f} % más barato. Si lo agregas desde ahí, se crea una orden aparte para ese proveedor.")


@st.dialog("Nueva orden de compra", width="large")
def _new_order_dialog() -> None:
    forms.header("Prepara tu pedido", "Elige proveedor y destino, agrega los materiales (puedes cambiar de proveedor) y revisa el total antes de crear.")
    suppliers = repo.list_suppliers()
    if suppliers.empty:
        ui.empty_state("Falta un proveedor", "Registra uno en Proveedores para preparar tu primera orden.", icon="🏭")
        if st.button(":material/close: Cancelar", key="order_cancel_empty", width="stretch"):
            _clear_order_draft()
            st.rerun()
        return
    ui.tip("Ejemplo: elige el proveedor, agrega un material con cantidad 12 y pulsa «Agregar al pedido». Si otro proveedor tiene otro material más barato, cambia de proveedor y agrégalo: "
           "lo anterior se conserva y al final se crea una orden por proveedor.")
    sites = repo.list_project_sites()
    offers = repo.list_offers()
    cart: dict = st.session_state.setdefault(CART_KEY, {})

    preset = st.session_state.pop(PRESET_KEY, None)
    if preset:  # viene de «Duplicar»: precarga proveedor, obra, notas, condiciones y líneas
        cart.clear()
        st.session_state["new_order_supplier"] = preset["supplier_name"]
        st.session_state["new_order_site"] = preset["site_name"] if preset["site_name"] in sites["name"].tolist() else NO_SITE
        st.session_state["new_order_notes"] = preset["notes"] or ""
        cart[preset["supplier_id"]] = {
            "name": preset["supplier_name"], "lines": preset["lines"],
            "terms": {**_default_terms(), "currency": preset.get("currency") or money.BASE, "exchange_rate": float(preset.get("exchange_rate") or 1.0),
                      "tax_rate": float(preset.get("tax_rate") or 0), "prices_include_tax": bool(preset.get("prices_include_tax")), "payment_terms": preset.get("payment_terms")},
        }

    forms.section("1. Proveedor y destino", "Elige el proveedor del que vas a agregar materiales. Puedes cambiarlo cuando quieras: lo ya agregado se conserva y se crea una orden por proveedor. La obra destino es opcional.")
    counts = {entry["name"]: len(entry["lines"]) for entry in cart.values() if entry["lines"]}
    supplier_name = st.selectbox("Proveedor", suppliers["name"].tolist(), key="new_order_supplier",
                                 format_func=lambda n: f"{n} · {counts[n]} en el pedido" if counts.get(n) else n,
                                 help="Cada proveedor tiene su catálogo, sus precios y sus condiciones. Al cambiar de proveedor no pierdes lo que ya agregaste.")
    supplier_id = suppliers.loc[suppliers["name"] == supplier_name, "id"].iloc[0]
    site_choice = st.selectbox("Obra destino (opcional)", [NO_SITE] + sites["name"].tolist(), key="new_order_site",
                               help="Asigna una obra para incluir estas compras en su control de presupuesto. Vale para todas las órdenes del pedido.")
    notes = st.text_input("Notas (opcional)", placeholder="Ej. Entregar antes del viernes", key="new_order_notes", max_chars=500,
                          help="Condiciones de entrega o indicaciones para los proveedores. Hasta 500 caracteres.")

    forms.section(f"2. Condiciones con {supplier_name}", "Cada proveedor tiene las suyas: fecha prometida, moneda, IGV y forma de pago (informativa). El IGV (18 %) se suma o se separa según cómo cotiza.")
    entry = cart.get(supplier_id)
    terms = orden_form.terms_inputs(f"new_order_{supplier_id}", **(_terms_defaults(entry["terms"]) if entry else {}))
    if entry:
        entry["terms"] = terms

    forms.section("3. Agrega materiales", f"Del catálogo de {supplier_name}. El precio unitario viene del catálogo; lo que sube con la cantidad es el subtotal. Agregar de nuevo un material suma cantidades.")
    catalog = repo.get_supplier_catalog(supplier_id)
    offered = catalog[catalog["offered"]] if not catalog.empty else catalog
    if offered.empty:
        st.warning("Este proveedor todavía no tiene materiales asignados. Márcalos como «Lo ofrece» en su catálogo.")
    else:
        labels = [f"{r['category']} · {r['name']}" for r in offered.to_dict("records")]
        if st.session_state.get("new_order_material") not in labels:
            st.session_state.pop("new_order_material", None)      # otro proveedor: la elección anterior ya no existe
        record, qty, price = orden_form.material_picker("new_order", offered, terms["currency"], price_max_age())
        if price <= 0:
            st.warning(
                "Este material no tiene precio en el catálogo del proveedor, así que no se puede agregar. "
                "Regístralo en Proveedores → Catálogo (o importa su lista de precios) y vuelve.",
                icon=":material/sell:",
            )
        if price > 0 and pricing.is_stale(record.get("price_updated_at"), price_max_age()):
            st.warning(
                f"Este precio está vencido ({pricing.describe(record.get('price_updated_at'), price_max_age())}). "
                "Confirma la cotización con el proveedor antes de comprar.",
                icon=":material/history:",
            )
        if not record.get("available", True):
            st.caption("El catálogo indica que este material no está disponible. Confirma la entrega con el proveedor.")
        _material_quotes(record, supplier_id, offers, f"{record['category']} · {record['name']}")
        if st.button(":material/add: Agregar al pedido", width="stretch", disabled=price <= 0, key="order_add_line"):
            lines = cart[supplier_id]["lines"] if supplier_id in cart else []
            existing = next((ln for ln in lines if ln["material_id"] == record["id"]), None)
            issues = forms.validate({"Cantidad": qty, "Precio unit.": price})
            if existing:
                issues.extend(forms.validate({"Cantidad": existing["quantity"] + qty}))
            line_qty = qty + (existing["quantity"] if existing else 0)
            if not math.isfinite(line_qty * price):
                issues.append("Subtotal: revisa la cantidad y el precio para obtener un total finito.")
            if not forms.errors(issues):
                lines = cart.setdefault(supplier_id, {"name": supplier_name, "lines": [], "terms": terms})["lines"]
                if existing:
                    existing["quantity"] += qty
                    existing["unit_price"] = price  # siempre el precio vigente del catálogo
                else:
                    lines.append(
                        {
                            "material_id": record["id"],
                            "material_name": record["name"],
                            "category": record["category"],
                            "unit": units.primary(record["metric_label"]),
                            "quantity": qty,
                            "unit_price": price,
                            "price_updated_at": record.get("price_updated_at"),
                        }
                    )
                st.rerun(scope="fragment")

    for empty_id in [sid for sid, e in cart.items() if not e["lines"]]:
        cart.pop(empty_id)
    forms.section("4. Revisa y crea", "Una tarjeta por proveedor: cada material con su cantidad y subtotal, el IGV y el total. Cada proveedor genera su propia orden.")
    grand_base, spent_base, every_line = 0.0, 0.0, []
    for group_id, group in list(cart.items()):
        g_terms, g_lines = group["terms"], group["lines"]
        subtotal = sum(ln["quantity"] * ln["unit_price"] for ln in g_lines)
        amounts = money.amounts(subtotal, g_terms["tax_rate"], g_terms["exchange_rate"], g_terms.get("prices_include_tax", False))
        grand_base += amounts["total_base"]
        spent_base += subtotal * g_terms["exchange_rate"]
        every_line += g_lines
        head, edit = st.columns([5, 2], vertical_alignment="center")
        head.markdown(orden_form.group_head_html(group["name"], len(g_lines), money.fmt(amounts["total"], g_terms["currency"]), group_id == supplier_id), unsafe_allow_html=True)
        if group_id != supplier_id:
            edit.button(":material/tune: Ver este proveedor", key=f"cond_{group_id}", width="stretch", on_click=_jump_to_supplier, args=(group["name"],),
                        help="Cambia a este proveedor para agregar más materiales o ajustar sus condiciones.")
        for index, line in enumerate(g_lines):
            card, move, remove = st.columns([11, 1, 1], vertical_alignment="center")
            card.markdown(orden_form.line_card_html(index, line, g_terms["currency"]), unsafe_allow_html=True)
            alternatives = _alternatives(offers, line["material_id"], group_id)
            if alternatives:
                with move.popover(":material/swap_horiz:", help="Mover este material a otro proveedor"):
                    st.caption("Mover a otro proveedor (con su precio):")
                    for alt in alternatives:
                        delta = (alt["price"] / line["unit_price"] - 1) * 100 if line["unit_price"] else 0
                        tag = f" · {abs(delta):.0f} % {'menos' if delta < 0 else 'más'}" if abs(delta) >= 0.5 else ""
                        st.button(f"{'★ ' if alt is alternatives[0] else ''}{alt['supplier_name']} · {alt['price']:,.2f}{tag}", key=f"mv_{group_id}_{line['material_id']}_{alt['supplier_id']}",
                                  width="stretch", on_click=_move_line, args=(group_id, line["material_id"], alt["supplier_id"], alt["supplier_name"], alt["price"], alt.get("price_updated_at")))
            if remove.button(":material/close:", key=f"oline_del_{group_id}_{index}", help="Quitar del pedido"):
                g_lines.pop(index)
                st.rerun(scope="fragment")
        orden_form.totals_block(subtotal, g_terms)
    if cart:
        if len(cart) > 1:
            st.markdown(orden_form.grand_total_html(len(cart), money.fmt(grand_base, money.BASE)), unsafe_allow_html=True)
        st.caption(f"{len(every_line)} material(es) en {len(cart)} orden(es) · Destino: {site_choice}")
        if site_choice != NO_SITE:
            by_material: dict[str, dict] = {}
            for ln in every_line:
                merged = by_material.setdefault(ln["material_id"], {**ln, "quantity": 0.0})
                merged["quantity"] += ln["quantity"]
            _budget_warning(sites.loc[sites["name"] == site_choice, "id"].iloc[0], site_choice, list(by_material.values()), spent_base)
        if any(ln["unit_price"] == 0 for ln in every_line):
            st.warning("Hay materiales con precio 0. El total solo incluye los precios registrados.")
        stale_lines = [ln["material_name"] for ln in every_line if pricing.is_stale(ln.get("price_updated_at"), price_max_age())]
        if stale_lines:
            st.warning(
                f"Cotizaciones con más de {price_max_age()} días sin actualizarse: {', '.join(stale_lines)}. Conviene confirmar el precio con el proveedor.",
                icon=":material/history:",
            )
    else:
        ui.empty_state("Tu pedido está vacío", "Selecciona un material y pulsa «Agregar al pedido». Después podrás crear la orden.", icon="🧾")

    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key="order_cancel", width="stretch"):
        _clear_order_draft()
        st.rerun()
    if save.button(":material/add_circle: Crear orden" if len(cart) <= 1 else f":material/add_circle: Crear pedido ({len(cart)} proveedores)", type="primary", width="stretch", disabled=not cart):
        issues = forms.validate({"Notas (opcional)": notes})
        if not cart:
            issues.append("Materiales del pedido: agrega al menos un material.")
        for group in cart.values():
            for line in group["lines"]:
                issues.extend(f"{line['material_name']}: {issue}" for issue in forms.validate({"Cantidad": line["quantity"], "Precio unit.": line["unit_price"]}))
        if not math.isfinite(grand_base):
            issues.append("Total del pedido: revisa las cantidades y precios para obtener un total finito.")
        if forms.errors(issues):
            return
        site_id = None if site_choice == NO_SITE else sites.loc[sites["name"] == site_choice, "id"].iloc[0]
        codes: list[str] = []
        batch = None
        if len(cart) > 1:
            try:
                batch = repo.next_batch_code()
            except ValueError as exc:
                st.error(f"No se pudo crear el pedido: {exc}")
                return
        for group_id, group in list(cart.items()):
            try:
                codes.append(repo.create_order(group_id, group["name"], site_id, notes.strip() or None, group["lines"], group["terms"], batch))
            except ValueError as exc:
                st.error(f"No se pudo crear la orden de {group['name']}: {exc}" + (f" Ya se crearon: {', '.join(codes)}." if codes else ""))
                return
            cart.pop(group_id)
        _clear_order_draft()
        ui.flash(f"Orden {codes[0]} creada." if len(codes) == 1 else f"Pedido {batch} creado con {len(codes)} órdenes ({', '.join(codes)}).", ":material/receipt_long:")
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
            f"edit_add_{order_id}_material", f"edit_{order_id}_date", f"edit_{order_id}_currency",
            f"edit_{order_id}_rate", f"edit_{order_id}_taxmode", f"edit_{order_id}_pay"]


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

    forms.section("2. Entrega, moneda, IGV y pago", "Cambia la fecha prometida, la moneda, el tratamiento del IGV o la condición de pago.")
    terms = _terms_inputs(
        f"edit_{oid}", order.get("expected_date"), order.get("currency") or money.BASE, order.get("exchange_rate") or 3.75,
        money.tax_mode(order.get("tax_rate"), order.get("prices_include_tax")), order.get("payment_terms"),
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
        record, qty, _ = orden_form.material_picker(f"edit_add_{oid}", offered, terms["currency"], price_max_age())
        existing = next((l for l in draft if l["material_id"] == record["id"]), None)
        catalog_price = float(record["price"]) if pd.notna(record["price"]) else 0.0
        if not existing and catalog_price <= 0:
            st.warning("Este material no tiene precio en el catálogo del proveedor. Regístralo en Proveedores → Catálogo para poder agregarlo.", icon=":material/sell:")
        if st.button(":material/add: Agregar a la orden", width="stretch", key=f"edit_add_btn_{oid}", disabled=(not existing and catalog_price <= 0)):
            issues = forms.validate({"Cantidad": qty})
            if not forms.errors(issues):
                sync()
                if existing:
                    existing["quantity"] += qty
                    existing["remove"] = False
                else:
                    draft.append(
                        {
                            "material_id": record["id"], "material_name": record["name"], "unit": units.primary(record["metric_label"]),
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
    if cancel.button(":material/close: Cancelar", key=f"edit_cancel_{oid}", width="stretch"):
        _clear_edit_draft(oid)
        st.rerun()
    if save.button(":material/save: Guardar cambios", type="primary", width="stretch", key=f"edit_save_{oid}"):
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
        changes = audit.diff(
            {"site": order.get("site_name"), "notes": order.get("notes"), "expected": order.get("expected_date"),
             "currency": order.get("currency") or money.BASE, "igv": money.TAX_MODES[money.tax_mode(order.get("tax_rate"), order.get("prices_include_tax"))][0],
             "pay": order.get("payment_terms")},
            {"site": None if site_choice == NO_SITE else site_choice, "notes": notes.strip() or None, "expected": terms["expected_date"],
             "currency": terms["currency"], "igv": money.TAX_MODES[money.tax_mode(terms["tax_rate"], terms["prices_include_tax"])][0], "pay": terms["payment_terms"]},
            {"site": "Obra destino", "notes": "Notas", "expected": "Fecha prometida", "currency": "Moneda", "igv": "Tratamiento del IGV", "pay": "Condición de pago"},
        ) + audit.diff_lines(items.to_dict("records"), new_items)
        reminder = " Reenvía el pedido actualizado al proveedor." if order["status"] == "enviada" else ""
        if changes:
            ui.log_change(f"Orden {order['code']} editada", "orden", oid, changes, icon=":material/edit:")
            st.session_state["_flash"] = (f"Orden {order['code']} actualizada.{reminder}", ":material/edit:")
        else:
            ui.flash(f"Orden {order['code']}: sin cambios.{reminder}", ":material/edit:", log=False)
        st.rerun()


def _duplicate(order: dict, items: pd.DataFrame) -> None:
    """Prepara el diálogo de nueva orden con los datos de otra ya hecha."""
    suppliers = repo.list_suppliers()
    match = suppliers[suppliers["id"] == order["supplier_id"]]
    if match.empty:
        st.toast("El proveedor de esta orden ya no existe; no se puede duplicar.", icon=":material/warning:")
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
        "prices_include_tax": order.get("prices_include_tax"),
        "payment_terms": order.get("payment_terms"),
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
        ui.flash(f"No se pudo eliminar {code}: {exc}", ":material/warning:", log=False)
        return
    if st.session_state.get(SELECTED_KEY) == order_id:
        st.session_state[SELECTED_KEY] = None
    ui.flash(f"Orden {code} eliminada.", ":material/delete:")


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
        help="Las órdenes abiertas con más días que esto se marcan en rojo aquí y en el dashboard.",
    )

    stale = stale_orders(df)
    if not stale.empty:
        st.warning(f"{len(stale)} orden(es) abierta(s) con más de {alert_days()} días sin cerrarse: {', '.join(stale['code'].tolist()[:6])}", icon=":material/alarm:")
    late = late_orders(df)
    if not late.empty:
        st.error(f"{len(late)} orden(es) pasaron su fecha prometida de entrega: {', '.join(late['code'].tolist()[:6])}", icon=":material/event_busy:")
    late_days = dict(zip(late["id"], late["days_late"])) if not late.empty else {}

    if status_label != ALL_STATUSES:
        df = df[df["status"] == labels[status_label]]
    df = ui.filter_df(df, query, ["code", "supplier_name", "site_name"])
    ui.result_count(len(df), total, noun="órdenes")
    if query or status_label != ALL_STATUSES:
        st.button(":material/filter_alt_off: Limpiar filtros", key="ord_clear", on_click=_clear_filters)
    if df.empty:
        ui.empty_state("Sin coincidencias", "Prueba otro código o proveedor, o limpia los filtros para ver todas las órdenes.", icon="🔎")
        return

    stale_ids = set(stale["id"]) if not stale.empty else set()
    rows = df.to_dict("records")
    shown: set[str] = set()
    for row in rows:
        batch_code = row.get("batch_code")
        if not batch_code:
            _render_order_row(row, stale_ids, late_days)
        elif batch_code not in shown:
            shown.add(batch_code)
            _render_batch_card(batch_code, [r for r in rows if r.get("batch_code") == batch_code], stale_ids, late_days)


def _batch_totals(members: list[dict]) -> tuple[float, int]:
    """Total de un pedido en soles y número de líneas, sumando sus órdenes."""
    return sum(float(r["total_base"]) for r in members), sum(int(r["items_count"]) for r in members)


def _render_batch_card(code: str, members: list[dict], stale_ids: set, late_days: dict) -> None:
    """Un pedido con varias órdenes (una por proveedor) en una sola tarjeta, con su total general."""
    total, lines = _batch_totals(members)
    label, color = batch_status(members)
    with st.container(border=True):
        head, view = st.columns([8, 1.6], vertical_alignment="center")
        head.markdown(orden_form.batch_head_html(code, len(members), lines, money.fmt(total, money.BASE), ui.pill(label, color)), unsafe_allow_html=True)
        if view.button(":material/visibility: Ver pedido", key=f"open_batch_{code}", width="stretch"):
            st.session_state[BATCH_KEY] = code
            st.rerun()
        for row in members:
            _render_order_row(row, stale_ids, late_days)


def _render_order_row(row: dict, stale_ids: set, late_days: dict) -> None:
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([4, 3, 2, 1.6, 1])
        with c1:
            date = clock.local(row["created_at"], False)
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
            if st.button(":material/visibility: Ver", key=f"open_order_{row['id']}", width="stretch"):
                st.session_state[SELECTED_KEY] = row["id"]
                st.rerun()
        with c5:
            if st.button(":material/delete:", key=f"del_order_{row['id']}", help="Eliminar orden"):
                ui.confirm_delete(
                    f"¿Eliminar la orden {row['code']}? Se borran también sus líneas.",
                    lambda oid=row["id"], code=row["code"]: _delete_order(oid, code),
                )


# ---------------------------------------------------------------------------
# Detalle
# ---------------------------------------------------------------------------

def batch_status(members: list[dict]) -> tuple[str, str]:
    """Estado resumen de un pedido: el de sus órdenes si todas coinciden; si no, «En curso» (o «Recibido» si solo quedan recibidas y canceladas)."""
    states = {m["status"] for m in members}
    if len(states) == 1:
        label, color = STATUSES.get(next(iter(states)), ("—", "gray"))
        return label, color
    live = states - {"cancelada"}
    if live == {"recibida"}:
        return "Recibido", "green"
    return "En curso", "blue"


def batch_targets(members: list[dict], status: str) -> list[dict]:
    """Órdenes del pedido a las que se puede aplicar el cambio: «enviada» solo a las pendientes; «cancelada» a las pendientes y enviadas
    (las que ya recibieron material no se cancelan juntas: se revisan una por una)."""
    allowed = {"enviada": ("pendiente",), "cancelada": ("pendiente", "enviada")}[status]
    return [m for m in members if m["status"] in allowed]


def batch_can_delete(members: list[dict], items_by_order: dict) -> bool:
    """Un pedido se elimina entero solo si ninguna de sus órdenes recibió material (el stock quedaría descuadrado)."""
    for member in members:
        items = items_by_order.get(member["id"])
        if member["status"] in ("parcial", "recibida") or (items is not None and not items.empty and (items["received_qty"].astype(float) > 0).any()):
            return False
    return True


def _apply_batch_status(code: str, members: list[dict], status: str) -> None:
    """Cambia el estado de todas las órdenes elegibles del pedido y lo anota en el Historial (una línea por orden)."""
    done = []
    for member in batch_targets(members, status):
        repo.set_order_status(member["id"], status)
        ui.log_change(
            f"Orden {member['code']} ({code}): {STATUSES[status][0].lower()}", "orden", member["id"],
            [{"field": "Estado", "before": STATUSES.get(member["status"], (member["status"],))[0], "after": STATUSES[status][0]}],
        )
        done.append(member["code"])
    skipped = len(members) - len(done)
    text = f"Pedido {code}: {len(done)} orden(es) {STATUSES[status][0].lower()}s" if done else f"Pedido {code}: ninguna orden cambió"
    ui.flash(text + (f" ({skipped} sin cambio)." if skipped and done else "."), ":material/sync:")


def _delete_batch(code: str, members: list[dict]) -> None:
    for member in members:
        try:
            repo.delete_order(member["id"])
        except ValueError as exc:
            ui.flash(f"No se pudo eliminar {member['code']}: {exc}", ":material/warning:", log=False)
            return
    st.session_state[BATCH_KEY] = None
    ui.flash(f"Pedido {code} eliminado con sus {len(members)} órdenes.", ":material/delete:")


@st.dialog("Cancelar el pedido")
def _cancel_batch_dialog(code: str, members: list[dict]) -> None:
    targets = batch_targets(members, "cancelada")
    st.write(f"Se cancelarán {len(targets)} orden(es) del pedido {code}: {', '.join(m['code'] for m in targets)}. Las órdenes ya recibidas no se tocan.")
    c1, c2 = st.columns(2)
    if c1.button(":material/close: Volver", width="stretch"):
        st.rerun()
    if c2.button(":material/cancel: Sí, cancelar el pedido", type="primary", width="stretch"):
        _apply_batch_status(code, members, "cancelada")
        st.rerun()


def _render_batch(code: str) -> None:
    """Un pedido con varios proveedores como una sola ficha: sus materiales agrupados por proveedor, el total general, acciones sobre todo el pedido y su PDF."""
    orders = repo.list_orders()
    members = orders[orders["batch_code"] == code].to_dict("records") if not orders.empty and "batch_code" in orders.columns else []
    if not members:
        st.session_state[BATCH_KEY] = None
        st.rerun()
        return
    if st.button(":material/arrow_back: Volver", key="batch_back"):
        st.session_state[BATCH_KEY] = None
        st.rerun()
    ui.page_header("Pedido", code)
    label, color = batch_status(members)
    st.markdown(ui.pill(label, color), unsafe_allow_html=True)
    total, lines = _batch_totals(members)
    ui.stat_grid(
        [
            ui.stat_card("🏭", str(len(members)), "Proveedores"),
            ui.stat_card("🏗️", members[0]["site_name"] or "—", "Obra destino"),
            ui.stat_card("📅", clock.local(members[0]["created_at"], False), "Fecha"),
            ui.stat_card("💰", money.fmt(total, money.BASE), "Total del pedido (con IGV)"),
        ]
    )
    st.caption(f"{lines} línea(s) en {len(members)} órdenes, una por proveedor: cada una tiene su propio PDF, IGV, forma de pago y recepción.")

    items_by_order = {m["id"]: repo.list_order_items(m["id"]) for m in sorted(members, key=lambda r: r["code"])}
    pending, cancellable = batch_targets(members, "enviada"), batch_targets(members, "cancelada")
    a1, a2, a3 = st.columns(3)
    if a1.button(f":material/send: Marcar {len(pending)} como enviada(s)", key=f"batch_sent_{code}", width="stretch", disabled=not pending,
                 help="Pasa a «enviada» todas las órdenes pendientes del pedido (anota la hora de envío de cada una)."):
        _apply_batch_status(code, members, "enviada")
        st.rerun()
    if a2.button(":material/cancel: Cancelar el pedido", key=f"batch_cancel_{code}", width="stretch", disabled=not cancellable,
                 help="Cancela las órdenes pendientes y enviadas. Las que ya recibieron material se revisan una por una."):
        _cancel_batch_dialog(code, members)
    can_delete = batch_can_delete(members, items_by_order)
    if a3.button(":material/delete: Eliminar el pedido", key=f"batch_delete_{code}", width="stretch", disabled=not can_delete,
                 help="Elimina el pedido y todas sus órdenes." if can_delete else "Alguna orden ya recibió material: cancélala en lugar de eliminarla."):
        ui.confirm_delete(f"¿Eliminar el pedido {code}? Se borran sus {len(members)} órdenes y sus líneas.", lambda: _delete_batch(code, members))

    company = repo.get_company()
    suppliers = repo.list_suppliers()
    with_items = []
    for row in sorted(members, key=lambda r: r["code"]):
        items = items_by_order[row["id"]]
        with_items.append({"order": row, "items": items})
        head, open_btn = st.columns([8, 2], vertical_alignment="center")
        head.markdown(orden_form.group_head_html(f"{row['supplier_name']} · {row['code']}", len(items), money.fmt(row["total"], row.get("currency")), False), unsafe_allow_html=True)
        if open_btn.button(":material/open_in_new: Abrir orden", key=f"batch_open_{row['id']}", width="stretch"):
            st.session_state[BATCH_KEY] = None
            st.session_state[SELECTED_KEY] = row["id"]
            st.rerun()
        st.markdown(status_pill(row["status"]), unsafe_allow_html=True)
        for index, line in enumerate(items.to_dict("records")):
            st.markdown(orden_form.line_card_html(index, {**line, "quantity": float(line["quantity"]), "unit_price": float(line["unit_price"]), "category": None}, row.get("currency")), unsafe_allow_html=True)
        if not items.empty and row["status"] != "cancelada":
            match = suppliers[suppliers["id"] == row["supplier_id"]]
            supplier = match.to_dict("records")[0] if not match.empty else None
            p1, p2, _ = st.columns([2, 2.6, 3])
            p1.download_button(":material/description: PDF de esta orden", data=order_pdf(row, items, supplier, company), file_name=f"{row['code']}.pdf", mime="application/pdf",
                               key=f"batch_order_pdf_{row['id']}", width="stretch")
            phone = re.sub(r"\D", "", (supplier or {}).get("phone") or "")
            p2.link_button(":material/chat: Enviar esta orden por WhatsApp", f"https://wa.me/{phone}?text={quote(order_whatsapp_text(row, items, company))}", width="stretch",
                           on_click=_mark_sent_from_link, args=(row["id"], row["code"], row["status"]),
                           help="Abre WhatsApp con la orden escrita y, si estaba pendiente, la marca como enviada.")
    st.markdown(orden_form.grand_total_html(len(members), money.fmt(total, money.BASE)), unsafe_allow_html=True)
    st.download_button(":material/description: PDF del pedido", data=batch_pdf(code, with_items, company), file_name=f"{code}.pdf", mime="application/pdf", key=f"batch_pdf_{code}")


def _mark_sent_from_link(order_id: str, code: str, status: str) -> None:
    """Al abrir WhatsApp con el pedido, la orden pendiente pasa sola a «enviada» y anota la hora de envío."""
    if status != "pendiente":
        return
    try:
        repo.set_order_status(order_id, "enviada")
        ui.flash(f"Orden {code}: marcada como enviada al abrir WhatsApp.", ":material/send:")
    except Exception:  # abrir WhatsApp nunca debe fallar por esto
        pass


def _sent_text(value) -> str:
    text = str(value or "")
    if not text or text in ("None", "nan", "NaT"):
        return ""
    local = clock.local(text)
    return f"{local[8:10]}/{local[5:7]}/{local[:4]} {local[11:16]}".strip()


def _change_status(order_id: str, code: str, status: str) -> None:
    before = repo.list_orders()
    before = before[before["id"] == order_id]
    old = before.iloc[0]["status"] if not before.empty else None
    repo.set_order_status(order_id, status)
    ui.log_change(
        f"Orden {code}: {STATUSES[status][0].lower()}", "orden", order_id,
        [{"field": "Estado", "before": STATUSES.get(old, (old,))[0] if old else None, "after": STATUSES[status][0]}], icon=":material/sync:",
    )
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
    ui.flash(f"Orden {code}: recepción registrada ({STATUSES[status][0].lower()}). El stock se actualizó.", ":material/inventory_2:")
    st.rerun()


def _render_reception(order: dict, items: pd.DataFrame) -> None:
    """Cuánto llegó de cada línea; suma al stock y deja la orden en parcial o recibida."""
    pending = items[items["quantity"].astype(float) - items["received_qty"].astype(float) > 1e-9]
    if pending.empty:
        return
    with st.expander(":material/inventory_2: Registrar recepción", expanded=order["status"] in ("enviada", "parcial")):
        forms.section("1. Indica lo que llegó", "Registra solo esta entrega. Las cantidades se sumarán al inventario al guardar.")
        records = pending.to_dict("records")
        keys = {r["id"]: f"recv_{r['id']}_{float(r['received_qty']):g}" for r in records}
        if st.button(":material/inventory: Recibir todo lo pendiente", key=f"recv_all_{order['id']}",
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
        if b1.button(":material/close: Cancelar", width="stretch", key=f"recv_cancel_{order['id']}"):
            for key in keys.values():
                st.session_state.pop(key, None)
            st.rerun()
        if b2.button(":material/task_alt: Registrar lo indicado", type="primary", width="stretch", key=f"recv_go_{order['id']}"):
            _receive(order["id"], order["code"], receipts, {"document_ref": doc_ref, "delivered_by": delivered_by, "notes": recv_notes})


def _render_receipts(order_id: str) -> None:
    """Recepciones ya registradas de la orden, con su documento y observaciones."""
    receipts = repo.list_receipts(order_id)
    if receipts.empty:
        return
    with st.expander(f":material/receipt_long: Recepciones registradas ({len(receipts)})"):
        for r in receipts.to_dict("records"):
            when = clock.local(r["received_at"])
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

    if st.button(":material/arrow_back: Volver"):
        st.session_state[SELECTED_KEY] = None
        st.rerun()

    ui.page_header("Orden de compra", order["code"])
    st.markdown(status_pill(status), unsafe_allow_html=True)
    if order.get("batch_code"):
        st.info(f"Esta orden es parte del pedido {order['batch_code']}, que junta materiales de varios proveedores.", icon=":material/layers:")
        if st.button(":material/layers: Ver el pedido completo", key=f"to_batch_{order_id}"):
            st.session_state[SELECTED_KEY] = None
            st.session_state[BATCH_KEY] = order["batch_code"]
            st.rerun()

    ui.stat_grid(
        [
            ui.stat_card("🏭", order["supplier_name"], "Proveedor"),
            ui.stat_card("🏗️", order["site_name"] or "—", "Obra destino"),
            ui.stat_card("📅", clock.local(order["created_at"], False), "Fecha"),
            ui.stat_card("💰", money.fmt(order["total"], order.get("currency")), "Importe total (con IGV)" if float(order.get("tax_rate") or 0) else "Importe total"),
        ]
    )
    if _sent_text(order.get("sent_at")):
        st.caption(f":material/send: Enviada al proveedor el {_sent_text(order['sent_at'])}.")
    late_by = _days_late(order)
    if order.get("expected_date") and status in OPEN_STATUSES:
        when = f"{str(order['expected_date'])[8:10]}/{str(order['expected_date'])[5:7]}/{str(order['expected_date'])[:4]}"
        if late_by:
            st.error(f"Entrega prometida para el {when}: lleva {late_by} día(s) de atraso.", icon=":material/event_busy:")
        else:
            st.caption(f":material/calendar_month: Entrega prometida para el {when}.")
    parts = [f"Valor de venta {money.fmt(order['net'], order.get('currency'))}"]
    if float(order.get("tax_rate") or 0):
        parts.append(f"IGV {float(order['tax_rate']):.0%} {money.fmt(order['tax'], order.get('currency'))}")
        parts.append("precios con IGV incluido" if order.get("prices_include_tax") else "IGV sumado a los precios")
    else:
        parts.append("sin IGV")
    if (order.get("currency") or money.BASE) != money.BASE:
        parts.append(f"equivale a {money.fmt(order['total_base'], money.BASE)} (tipo de cambio {float(order['exchange_rate']):g})")
    st.caption(" · ".join(parts))
    if order.get("payment_terms"):
        due = money.due_date(order["created_at"], order["payment_terms"])
        st.caption(f":material/credit_card: Condición de pago: {order['payment_terms']}" + (f" · pago pactado hasta el {due:%d/%m/%Y}" if due else "") + " (informativo: la compra y el pago se hacen fuera del sistema).")
    if order.get("notes"):
        st.caption(f":material/edit_note: {order['notes']}")
    schedule = money.payment_schedule(order["created_at"], order["total"], order.get("payment_terms")) if order.get("payment_terms") else []
    if len(schedule) > 1:
        st.markdown(orden_form.schedule_html(schedule, order.get("currency")), unsafe_allow_html=True)

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
    if status == "pendiente" and b1.button(":material/send: Marcar como enviada", width="stretch"):
        _change_status(order_id, order["code"], "enviada")
    if status in ("pendiente", "enviada", "parcial") and b2.button(":material/cancel: Cancelar orden", width="stretch"):
        _change_status(order_id, order["code"], "cancelada")
    if b3.button(":material/delete: Eliminar", width="stretch", disabled=received_any,
                 help="Ya recibió material: no se puede eliminar. Cancélala si el pedido no continúa." if received_any else None):
        ui.confirm_delete(
            f"¿Eliminar la orden {order['code']}? Se borran también sus líneas.",
            lambda oid=order_id, code=order["code"]: _delete_order(oid, code),
        )
    if status in ("pendiente", "enviada") and not received_any and not items.empty:
        if b4.button(":material/edit: Editar orden", width="stretch", help="Agrega, quita o cambia la cantidad de materiales, la obra o las notas mientras no haya recibido material."):
            _clear_edit_draft(order_id)  # cada vez que se abre parte de lo guardado
            _edit_order_dialog(order, items)

    if not items.empty:
        company = repo.get_company()
        d1, d2, d4, d3, _ = st.columns([1.7, 2.4, 1.9, 1.9, 0.6])
        d1.download_button(
            ":material/description: PDF",
            data=order_pdf(order, items, supplier, company),
            file_name=f"{order['code']}.pdf",
            mime="application/pdf",
            width="stretch",
        )
        phone = re.sub(r"\D", "", (supplier or {}).get("phone") or "")
        d2.link_button(
            ":material/chat: Enviar por WhatsApp",
            f"https://wa.me/{phone}?text={quote(order_whatsapp_text(order, items, company))}",
            width="stretch",
            on_click=_mark_sent_from_link,
            args=(order_id, order["code"], status),
            help="Abre WhatsApp con el pedido y, si la orden estaba pendiente, la marca como enviada con la hora." if status == "pendiente" else None,
        )
        d4.link_button(
            ":material/mail: Correo",
            mailto_url((supplier or {}).get("email"), f"Pedido {order['code']}", order_whatsapp_text(order, items, company)),
            width="stretch",
            on_click=_mark_sent_from_link,
            args=(order_id, order["code"], status),
            help="Abre tu programa de correo con el pedido escrito (adjunta el PDF descargado). Si la orden estaba pendiente, la marca como enviada.",
        )
        if d3.button("⧉ Duplicar", width="stretch", help="Crea una orden nueva con estos mismos materiales"):
            _duplicate(order, items)
        if len(schedule) > 1:
            st.markdown('<div class="mrp-eyebrow">PDF de los pagos</div>', unsafe_allow_html=True)
            cols = st.columns(min(len(schedule) + 1, 4))
            cols[0].download_button(":material/event_note: Cronograma", data=payment_schedule_pdf(order, items, supplier, company), file_name=f"{order['code']}-cronograma.pdf",
                                    mime="application/pdf", width="stretch", key=f"sched_pdf_{order_id}")
            for k, pay in enumerate(schedule):
                cols[(k + 1) % len(cols)].download_button(f":material/receipt: {pay['label']}", data=payment_pdf(order, items, pay["n"], supplier, company),
                                                         file_name=f"{order['code']}-P{pay['n']}.pdf", mime="application/pdf", width="stretch", key=f"pay_pdf_{order_id}_{pay['n']}")
