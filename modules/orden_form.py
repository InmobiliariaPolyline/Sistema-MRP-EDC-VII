"""Piezas del formulario de una orden de compra: condiciones (fecha, moneda, IGV y forma de pago), elegir un material con su ficha,
las líneas del pedido como tarjetas y el resumen con el IGV y el plan de pagos.

Todo es información: el sistema calcula el valor exacto del trato y las fechas y montos de pago, pero no compra ni paga."""
from __future__ import annotations

import html
from datetime import date

import pandas as pd
import streamlit as st

from modules import ui
from utils import clock, icons, money, pricing, units

NO_PAYMENT = "No indicada"
PAY_CASH = "Contado"
PAY_DELIVERY = "Contra entrega"
PAY_CREDIT = "Crédito a plazo único"
PAY_INSTALLMENTS = "En cuotas"
PAY_FORMS = [NO_PAYMENT, PAY_CASH, PAY_DELIVERY, PAY_CREDIT, PAY_INSTALLMENTS]
CREDIT_DAYS = [7, 15, 30, 45, 60]
INITIAL_CHOICES = [0, 10, 20, 30, 40, 50]
TAX_CHOICES = {
    "add": ("Sin IGV en el precio", "El proveedor cotiza sin IGV: el sistema suma 18 % al valor de venta."),
    "included": ("Con IGV incluido", "El precio ya trae el IGV (18 %): el sistema lo separa del total."),
    "none": ("Sin IGV (exonerada o inafecta)", "Compra sin IGV: no se suma nada."),
}


# ---------------------------------------------------------------------------------------------------------------------
# Condiciones de la orden
# ---------------------------------------------------------------------------------------------------------------------
def _split_payment(payment_terms: str | None) -> dict:
    """La condición guardada → valores iniciales de los controles."""
    plan = money.parse_plan(payment_terms)
    state = {"form": NO_PAYMENT, "days": 30, "count": 3, "every": "mensuales", "first": 30, "initial": 0}
    if plan:
        state.update(form=PAY_INSTALLMENTS, count=plan["count"], every=plan["every"], first=plan["first_days"], initial=plan["initial_pct"])
    elif payment_terms == PAY_CASH:
        state["form"] = PAY_CASH
    elif payment_terms == PAY_DELIVERY:
        state["form"] = PAY_DELIVERY
    elif money.credit_days(payment_terms) is not None:
        state.update(form=PAY_CREDIT, days=money.credit_days(payment_terms) if money.credit_days(payment_terms) in CREDIT_DAYS else 30)
    return state


def seed_payment(prefix: str, payment_terms: str | None) -> None:
    """Deja en la sesión los valores de pago de una orden (para «Duplicar»), antes de dibujar los controles."""
    state = _split_payment(payment_terms)
    for name, value in (("payform", state["form"]), ("paydays", state["days"]), ("paycount", state["count"]), ("payevery", state["every"]),
                        ("payfirst", state["first"]), ("payinitial", state["initial"])):
        st.session_state[f"{prefix}_{name}"] = value


def payment_keys(prefix: str) -> list[str]:
    return [f"{prefix}_{name}" for name in ("payform", "paydays", "paycount", "payevery", "payfirst", "payinitial")]


def payment_inputs(prefix: str, payment_terms: str | None = None) -> str | None:
    """Forma de pago (informativa): contado, contra entrega, crédito a un plazo o en cuotas. Devuelve el texto que se guarda."""
    state = _split_payment(payment_terms)
    form = st.selectbox(
        "Forma de pago (informativa)", PAY_FORMS, index=PAY_FORMS.index(state["form"]), key=f"{prefix}_payform",
        help="Lo pactado con el proveedor, para saber cuánto y cuándo. El sistema no cobra ni paga: el pago se hace fuera. "
             "En cuotas, el sistema calcula el cronograma y genera el PDF de cada cuota.",
    )
    if form == PAY_CREDIT:
        days = st.selectbox("Plazo del crédito (días)", CREDIT_DAYS, index=CREDIT_DAYS.index(state["days"]), key=f"{prefix}_paydays",
                            help="Un solo pago, a tantos días de emitida la orden.")
        return f"Crédito {int(days)} días"
    if form == PAY_INSTALLMENTS:
        c1, c2 = st.columns(2)
        count = c1.number_input("Número de cuotas", min_value=2, max_value=24, value=int(state["count"]), step=1, key=f"{prefix}_paycount",
                                help="De 2 a 24 cuotas iguales (la última ajusta los céntimos).")
        keys = list(money.INSTALLMENT_EVERY)
        every = c2.selectbox("Periodicidad", keys, index=keys.index(state["every"]), key=f"{prefix}_payevery",
                             format_func=lambda k: money.INSTALLMENT_EVERY[k].capitalize())
        c3, c4 = st.columns(2)
        first = c3.selectbox("Primera cuota a los", money.FIRST_DUE_DAYS, index=money.FIRST_DUE_DAYS.index(state["first"]) if state["first"] in money.FIRST_DUE_DAYS else 3,
                             key=f"{prefix}_payfirst", format_func=lambda d: "0 días (al emitir)" if d == 0 else f"{d} días",
                             help="Cuántos días después de emitida la orden vence la primera cuota.")
        initial = c4.selectbox("Cuota inicial", INITIAL_CHOICES, index=INITIAL_CHOICES.index(state["initial"]) if state["initial"] in INITIAL_CHOICES else 0,
                               key=f"{prefix}_payinitial", format_func=lambda p: "Sin inicial" if p == 0 else f"{p} % al emitir",
                               help="Un adelanto que se paga el día de la emisión; el resto se reparte en las cuotas.")
        return money.installment_terms(int(count), every, int(first), int(initial))
    return None if form == NO_PAYMENT else form


def tax_inputs(prefix: str, tax_mode: str = "add") -> str:
    """Con o sin IGV: dos opciones claras (la tercera, compra exonerada, solo aparece si la orden ya la tiene)."""
    keys = ["add", "included"] + (["none"] if tax_mode == "none" else [])
    mode = st.radio(
        "¿El precio del proveedor lleva IGV? (18 %)", keys, index=keys.index(tax_mode) if tax_mode in keys else 0, key=f"{prefix}_taxmode",
        format_func=lambda k: TAX_CHOICES[k][0], horizontal=True,
        help="En el Perú el IGV es 18 % (16 % de IGV + 2 % del Impuesto de Promoción Municipal). Casi todos los proveedores cotizan SIN IGV y se le suma; "
             "si el precio que te dieron ya lo incluye, elige «Con IGV incluido» y el sistema lo separa del total.",
    )
    st.caption(TAX_CHOICES[mode][1])
    return mode


def terms_inputs(
    prefix: str, expected_date=None, currency: str = money.BASE, exchange_rate: float = 3.75, tax_mode: str = "add", payment_terms: str | None = None,
) -> dict:
    """Fecha prometida, moneda, IGV y forma de pago de una orden. Devuelve las condiciones para guardar."""
    default_date = None
    if expected_date and str(expected_date) not in ("None", "nan", "NaT"):
        try:
            default_date = date.fromisoformat(str(expected_date)[:10])
        except ValueError:
            default_date = None
    c1, c2, c3 = st.columns([2, 2, 2])
    picked = c1.date_input(
        "Fecha prometida de entrega (opcional)", value=default_date, key=f"{prefix}_date", format="DD/MM/YYYY",
        min_value=clock.today() if not default_date or default_date >= clock.today() else None,
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
    mode = tax_inputs(prefix, tax_mode)
    payment = payment_inputs(prefix, payment_terms)
    tax_rate, include = money.tax_from_mode(mode)
    return {
        "expected_date": picked, "currency": chosen, "exchange_rate": rate, "tax_rate": tax_rate, "prices_include_tax": include, "payment_terms": payment,
    }


# ---------------------------------------------------------------------------------------------------------------------
# Elegir un material
# ---------------------------------------------------------------------------------------------------------------------
def _tile(label: str, value: str, sub: str = "", tone: str = "") -> str:
    sub_html = f"<small>{html.escape(sub)}</small>" if sub else ""
    return f'<div class="mrp-tile {tone}"><span class="k">{html.escape(label)}</span><b>{html.escape(value)}</b>{sub_html}</div>'


def material_card_html(record: dict, catalog_price: float, max_age: int) -> str:
    """Ficha breve del material elegido: nombre, categoría, en qué unidad se pide y si está disponible o con precio vencido."""
    unit = units.primary(record.get("metric_label"))
    pills = [ui.pill(f"Se pide en {unit}", "purple")]
    pills.append(ui.pill("Disponible", "green") if record.get("available", True) else ui.pill("No disponible", "red"))
    if catalog_price > 0 and pricing.is_stale(record.get("price_updated_at"), max_age):
        pills.append(ui.pill(pricing.describe(record.get("price_updated_at"), max_age), "amber"))
    extra = units.primary_label(record.get("metric_label"))
    density = f" · densidad {float(record['density']):g} kg/m³" if record.get("density") else ""
    return (
        f'<div class="mrp-matcard"><div class="mrp-matcard-ico">{icons.svg("layers", 20, 1.9)}</div>'
        f'<div class="mrp-matcard-body"><div class="mrp-matcard-name">{html.escape(str(record["name"]))}</div>'
        f'<div class="mrp-matcard-meta">{html.escape(str(record["category"]))} · {html.escape(extra)}{html.escape(density)}</div></div>'
        f'<div class="mrp-matcard-pills">{"".join(pills)}</div></div>'
    )


def material_picker(prefix: str, offered: pd.DataFrame, currency: str, max_age: int, locked_price: float | None = None) -> tuple[dict, float, float]:
    """Material del catálogo del proveedor + cantidad. El precio unitario es el del catálogo y se muestra en una tarjeta (no se edita aquí).
    Devuelve (material, cantidad, precio unitario)."""
    options = {f"{r['category']} · {r['name']}": r for r in offered.to_dict("records")}
    choice = st.selectbox("Material", list(options), key=f"{prefix}_material", help="Escribe para buscar un material de este proveedor.")
    record = options[choice]
    catalog_price = float(record["price"]) if pd.notna(record["price"]) else 0.0
    price = locked_price if locked_price is not None else catalog_price
    unit = units.primary(record.get("metric_label"))
    st.markdown(material_card_html(record, catalog_price, max_age), unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    qty = c1.number_input(
        f"Cantidad ({unit})", min_value=0.0, max_value=1_000_000.0, value=1.0, step=1.0, key=f"{prefix}_qty_{record['id']}",
        help=f"Se pide en {unit}. Admite decimales; debe ser mayor que 0.",
    )
    c2.markdown(_tile("Precio unitario", money.fmt(price, currency) if price > 0 else "Sin precio", f"por {unit} · del catálogo", "muted" if price <= 0 else ""), unsafe_allow_html=True)
    c3.markdown(_tile("Subtotal", money.fmt(qty * price, currency) if price > 0 else "—", f"{qty:g} {unit} × {money.fmt(price, currency)}" if price > 0 else "", "accent"), unsafe_allow_html=True)
    return record, float(qty), float(price)


# ---------------------------------------------------------------------------------------------------------------------
# Líneas y resumen
# ---------------------------------------------------------------------------------------------------------------------
def line_card_html(index: int, line: dict, currency: str) -> str:
    """Una línea del pedido: material, cuánto se pide en total, su detalle y el cálculo cantidad × precio."""
    unit = line.get("unit") or "unid."
    subtotal = line["quantity"] * line["unit_price"]
    detail = " · ".join(x for x in (line.get("category"), f"se pide en {unit}") if x)
    return (
        f'<div class="mrp-line"><div class="mrp-line-no">{index + 1}</div>'
        f'<div class="mrp-line-body"><div class="mrp-line-name">{html.escape(str(line["material_name"]))}</div>'
        f'<div class="mrp-line-meta">{html.escape(detail)}</div>'
        f'<div class="mrp-line-calc"><span class="qty">{line["quantity"]:g} {html.escape(unit)}</span><i>×</i><span>{html.escape(money.fmt(line["unit_price"], currency))} por {html.escape(unit)}</span></div></div>'
        f'<div class="mrp-line-total"><small>Subtotal</small><b>{html.escape(money.fmt(subtotal, currency))}</b></div></div>'
    )


def schedule_html(schedule: list[dict], currency: str) -> str:
    if not schedule:
        return ""
    rows = "".join(
        f'<div class="mrp-plan-row"><span class="no">{item["n"]}</span><span class="lbl">{html.escape(item["label"])}</span>'
        f'<span class="due">{item["due"]:%d/%m/%Y}</span><b>{html.escape(money.fmt(item["amount"], currency))}</b></div>'
        for item in schedule
    )
    return f'<div class="mrp-plan">{rows}</div>'


def summary_html(subtotal: float, terms: dict, issued=None) -> str:
    """Resumen de la orden como una factura: valor de venta, IGV e importe total, con una etiqueta que dice si hay IGV y cómo se trató."""
    amounts = money.amounts(subtotal, terms["tax_rate"], terms["exchange_rate"], terms.get("prices_include_tax", False))
    cur = terms["currency"]
    if terms["tax_rate"]:
        badge = ("Precios con IGV incluido: el IGV se separa del total" if terms.get("prices_include_tax") else f"IGV {terms['tax_rate']:.0%} se suma al valor de venta")
        tone = "included" if terms.get("prices_include_tax") else "added"
        tiles = _tile("Valor de venta", money.fmt(amounts["net"], cur), "sin IGV") + _tile(f"IGV ({terms['tax_rate']:.0%})", money.fmt(amounts["tax"], cur), "impuesto") \
            + _tile("Importe total", money.fmt(amounts["total"], cur), "con IGV", "accent")
    else:
        badge, tone = "Sin IGV: compra exonerada o inafecta", "none"
        tiles = _tile("Importe total", money.fmt(amounts["total"], cur), "sin IGV", "accent")
    note = ""
    if cur != money.BASE:
        note = f'<div class="mrp-ordsum-note">Equivale a {html.escape(money.fmt(amounts["total_base"], money.BASE))} al tipo de cambio {terms["exchange_rate"]:g}.</div>'
    return f'<div class="mrp-ordsum"><div class="mrp-igv-badge {tone}">{icons.svg("receipt", 14, 2)}<span>{html.escape(badge)}</span></div><div class="mrp-ordsum-tiles">{tiles}</div>{note}</div>'


def totals_block(subtotal: float, terms: dict) -> None:
    """Resumen con el IGV y, si hay forma de pago, el plan de pagos calculado como si la orden se emitiera hoy."""
    st.markdown(summary_html(subtotal, terms), unsafe_allow_html=True)
    payment = terms.get("payment_terms")
    if not payment:
        return
    amounts = money.amounts(subtotal, terms["tax_rate"], terms["exchange_rate"], terms.get("prices_include_tax", False))
    schedule = money.payment_schedule(clock.today(), amounts["total"], payment)
    if len(schedule) > 1:
        st.markdown(f'<div class="mrp-plan-title">{icons.svg("calendar", 14, 2)}Plan de pagos · {html.escape(payment)} · si se emite hoy</div>' + schedule_html(schedule, terms["currency"]), unsafe_allow_html=True)
        st.caption("Es solo información para tesorería: el sistema no cobra ni paga. Cada cuota tendrá su PDF en el detalle de la orden.")
    elif schedule:
        item = schedule[0]
        st.caption(f"{payment} · pago por {money.fmt(item['amount'], terms['currency'])} el {item['due']:%d/%m/%Y} si se emite hoy.")


def group_head_html(supplier: str, count: int, total: str, current: bool = False) -> str:
    """Encabezado de la tarjeta de un proveedor dentro del pedido: quién, cuántos materiales y cuánto suma su orden."""
    badge = ui.pill("Eligiendo ahora", "purple") if current else ""
    return (
        f'<div class="mrp-grouphead"><div class="mrp-grouphead-ico">{icons.svg("building", 18, 1.9)}</div>'
        f'<div class="mrp-grouphead-body"><b>{html.escape(supplier)}</b><small>{count} material(es) · una orden</small></div>'
        f'{badge}<div class="mrp-grouphead-total"><small>Total</small><b>{html.escape(total)}</b></div></div>'
    )


def grand_total_html(count: int, total: str) -> str:
    """Lo que suman todas las órdenes del pedido (en soles)."""
    return f'<div class="mrp-grand"><span>Total de las {count} órdenes</span><b>{html.escape(total)}</b></div>'
