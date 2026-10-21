"""Sugerencia de compra: qué falta pedir para cubrir los presupuestos de las obras.

Para cada material:

    demanda  = suma, por obra, de lo presupuestado que todavía no se despachó
    oferta   = stock en el almacén + lo que ya viene en órdenes abiertas (pedido − recibido)
    faltante = demanda + stock mínimo − oferta          (si es positivo, hay que comprar)

Cada faltante se asigna al proveedor más barato (entre los que tienen precio, con
preferencia por los que marcaron el material como disponible) y se pueden crear las
órdenes ya agrupadas por proveedor."""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, ui
from utils import money, pricing

OPEN_STATUSES = ("pendiente", "enviada", "parcial")
COLUMNS = [
    "material_id", "category", "material_name", "unit", "demand", "stock", "incoming", "min_stock", "deficit",
    "supplier_id", "supplier_name", "unit_price", "price_updated_at",
]


def _num(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if number != number else number


def best_offers(offers: pd.DataFrame) -> dict[str, dict]:
    """Por material: el proveedor más barato. Prefiere ofertas disponibles con precio; si no hay,
    usa cualquiera con precio; si tampoco, el material queda sin proveedor."""
    best: dict[str, dict] = {}
    if offers.empty:
        return best
    priced = offers[offers["price"].notna()].copy()
    priced["price"] = priced["price"].astype(float)
    priced = priced[priced["price"] > 0]
    for available_first in (True, False):
        pool = priced[priced["available"].astype(bool)] if available_first else priced
        for row in pool.sort_values("price").to_dict("records"):
            best.setdefault(row["material_id"], row)
    return best


def incoming_by_material(orders: pd.DataFrame, items: pd.DataFrame) -> dict[str, float]:
    """Lo que ya viene en camino por material: pedido − recibido en las órdenes abiertas."""
    incoming: dict[str, float] = {}
    if not items.empty and not orders.empty:
        open_ids = set(orders.loc[orders["status"].isin(OPEN_STATUSES), "id"])
        for row in items[items["order_id"].isin(open_ids)].to_dict("records"):
            if row.get("material_id"):
                pending = _num(row["quantity"]) - _num(row.get("received_qty"))
                if pending > 0:
                    incoming[row["material_id"]] = incoming.get(row["material_id"], 0.0) + pending
    return incoming


def supplier_summary(chosen: list[dict], suppliers: pd.DataFrame, today: date | None = None) -> list[dict]:
    """Por proveedor: líneas elegidas, total estimado, monto mínimo de compra, cuánto falta para llegar a él
    y la fecha aproximada de llegada (hoy + su plazo habitual). `chosen`: dicts con supplier_id, quantity, unit_price."""
    today = today or date.today()
    info = {r["id"]: r for r in suppliers.to_dict("records")} if not suppliers.empty else {}
    totals: dict[str, dict] = {}
    for line in chosen:
        entry = totals.setdefault(line["supplier_id"], {"lines": 0, "total": 0.0})
        entry["lines"] += 1
        entry["total"] += _num(line["quantity"]) * _num(line["unit_price"])
    rows = []
    for supplier_id, entry in totals.items():
        data = info.get(supplier_id, {})
        minimum = _num(data.get("min_order_amount")) or None
        lead = data.get("lead_time_days")
        lead = int(_num(lead)) if lead is not None and _num(lead) > 0 else None
        rows.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": data.get("name"),
                "lines": entry["lines"],
                "total": entry["total"],
                "min_order_amount": minimum,
                "missing": max(minimum - entry["total"], 0.0) if minimum else 0.0,
                "lead_time_days": lead,
                "arrival": (today + timedelta(days=lead)) if lead else None,
            }
        )
    return sorted(rows, key=lambda r: str(r["supplier_name"]))


def top_up_candidates(
    supplier_id: str, offers: pd.DataFrame, levels: pd.DataFrame, incoming: dict[str, float], exclude: set[str], limit: int = 12,
) -> pd.DataFrame:
    """Materiales que un proveedor también ofrece y conviene reponer, para completar su monto mínimo de compra:
    con stock mínimo definido y stock + lo que viene en camino por debajo del doble de ese mínimo.
    Propone llegar justo al doble. Mayor subtotal primero."""
    columns = ["material_id", "material_name", "unit", "stock", "min_stock", "quantity", "unit_price", "subtotal"]
    if offers.empty or levels.empty:
        return pd.DataFrame(columns=columns)
    mine = offers[(offers["supplier_id"] == supplier_id) & offers["price"].notna()]
    mine = mine[mine["price"].astype(float) > 0]
    by_material = levels.set_index("material_id").to_dict("index")
    rows = []
    for offer in mine.to_dict("records"):
        mid = offer["material_id"]
        level = by_material.get(mid)
        if level is None or mid in exclude or not offer.get("available", True):
            continue
        minimum = _num(level.get("min_stock"))
        have = _num(level.get("stock")) + incoming.get(mid, 0.0)
        if minimum <= 0 or have >= 2 * minimum - 1e-9:
            continue
        quantity = math.ceil((2 * minimum - have) * 100) / 100
        price = float(offer["price"])
        rows.append(
            {
                "material_id": mid, "material_name": level["material_name"], "unit": level.get("unit"),
                "stock": _num(level.get("stock")), "min_stock": minimum, "quantity": quantity, "unit_price": price, "subtotal": quantity * price,
            }
        )
    df = pd.DataFrame(rows, columns=columns)
    return df.sort_values("subtotal", ascending=False).head(limit).reset_index(drop=True) if not df.empty else df


def compute_suggestions(
    budgets: pd.DataFrame,
    orders: pd.DataFrame,
    items: pd.DataFrame,
    levels: pd.DataFrame,
    consumed: pd.DataFrame,
    offers: pd.DataFrame,
) -> pd.DataFrame:
    """Materiales con faltante > 0, con el proveedor más barato asignado (ver el docstring del módulo)."""
    if levels.empty:
        return pd.DataFrame(columns=COLUMNS)

    dispatched: dict[tuple[str, str], float] = {}  # `consumed`: consumo neto por obra, material y etapa (repo.site_consumption)
    if not consumed.empty:
        for row in consumed.to_dict("records"):
            key = (row["project_site_id"], row["material_id"])
            dispatched[key] = dispatched.get(key, 0.0) + _num(row["quantity"])

    demand: dict[str, float] = {}
    if not budgets.empty:
        planned: dict[tuple[str, str], float] = {}  # un material puede estar presupuestado en varias etapas de la misma obra
        for row in budgets.to_dict("records"):
            key = (row["project_site_id"], row["material_id"])
            planned[key] = planned.get(key, 0.0) + _num(row["planned_qty"])
        for key, qty in planned.items():
            left = qty - dispatched.get(key, 0.0)
            if left > 0:
                demand[key[1]] = demand.get(key[1], 0.0) + left

    incoming = incoming_by_material(orders, items)

    offers_by_material = best_offers(offers)
    rows = []
    for level in levels.to_dict("records"):
        mid = level["material_id"]
        minimum = _num(level.get("min_stock"))
        if mid not in demand and minimum <= 0:
            continue
        stock = _num(level.get("stock"))
        deficit = demand.get(mid, 0.0) + minimum - (stock + incoming.get(mid, 0.0))
        if deficit <= 1e-9:
            continue
        offer = offers_by_material.get(mid)
        rows.append(
            {
                "material_id": mid,
                "category": level["category"],
                "material_name": level["material_name"],
                "unit": level.get("unit"),
                "demand": demand.get(mid, 0.0),
                "stock": stock,
                "incoming": incoming.get(mid, 0.0),
                "min_stock": minimum,
                "deficit": math.ceil(deficit * 100) / 100,
                "supplier_id": offer["supplier_id"] if offer else None,
                "supplier_name": offer["supplier_name"] if offer else None,
                "unit_price": float(offer["price"]) if offer else None,
                "price_updated_at": offer.get("price_updated_at") if offer else None,
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS).sort_values(["supplier_name", "category", "material_name"], na_position="last").reset_index(drop=True)


def ordenes_price_age() -> int:
    """Vigencia de cotizaciones en días (la misma que se ajusta en la ficha del proveedor)."""
    return int(st.session_state.get("price_max_age", pricing.DEFAULT_MAX_AGE_DAYS))


def current_suggestions() -> pd.DataFrame:
    return compute_suggestions(
        repo.list_budgets(),
        repo.list_orders(),
        repo.list_order_items(),
        repo.stock_levels(),
        repo.site_consumption(),
        repo.list_offers(),
    )


@st.dialog("Sugerencia de compra", width="large")
def suggestion_dialog() -> None:
    forms.header(
        "Qué conviene pedir ahora",
        "Se compara lo presupuestado para las obras con el stock del almacén y con lo que ya viene en órdenes abiertas.",
    )
    data = current_suggestions()
    if data.empty:
        ui.empty_state(
            "No hace falta comprar nada",
            "El stock y las órdenes abiertas cubren lo presupuestado para las obras (y los stocks mínimos). "
            "Define presupuestos en Obras → Materiales para que aparezcan sugerencias.",
            ":material/check_circle:",
        )
        return

    buyable = data[data["supplier_id"].notna()].copy()
    unquoted = data[data["supplier_id"].isna()]
    total = float((buyable["deficit"] * buyable["unit_price"]).sum()) if not buyable.empty else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric("Materiales por pedir", len(buyable))
    c2.metric("Proveedores", int(buyable["supplier_id"].nunique()) if not buyable.empty else 0)
    c3.metric("Total estimado", f"{total:,.2f}")
    st.caption("Faltante = presupuesto sin despachar + stock mínimo − stock − lo que ya viene en órdenes. Cada material va al proveedor más barato.")

    if not buyable.empty:
        table = pd.DataFrame(
            {
                "Incluir": True,
                "Material": buyable["material_name"],
                "Proveedor": buyable["supplier_name"],
                "Stock": buyable["stock"].astype(float),
                "Por llegar": buyable["incoming"].astype(float),
                "Cantidad a pedir": buyable["deficit"].astype(float),
                "Precio unit.": buyable["unit_price"].astype(float),
                "Cotización": buyable["price_updated_at"].map(lambda v: pricing.describe(v, ordenes_price_age())),
            }
        )
        edited = st.data_editor(
            table, hide_index=True, width="stretch", key="suggestion_editor",
            disabled=["Material", "Proveedor", "Stock", "Por llegar", "Precio unit.", "Cotización"],
            column_config={
                "Cantidad a pedir": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help="Puedes ajustarla antes de crear las órdenes."),
                "Stock": st.column_config.NumberColumn(format="%.2f"),
                "Por llegar": st.column_config.NumberColumn(format="%.2f"),
                "Precio unit.": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        chosen = edited[(edited["Incluir"]) & (edited["Cantidad a pedir"] > 0)]
        stale = buyable[buyable["price_updated_at"].map(lambda v: pricing.is_stale(v, ordenes_price_age()))]
        if not stale.empty:
            st.warning(
                f"{len(stale)} cotización(es) con más de {ordenes_price_age()} días sin actualizarse: {', '.join(stale['material_name'].head(5))}"
                f"{'…' if len(stale) > 5 else ''}. Confirma esos precios antes de comprar.",
                icon=":material/history:",
            )
        st.caption(f"{len(chosen)} línea(s) seleccionada(s). Se crea una orden pendiente por proveedor, sin obra destino.")

        # Plazos y monto mínimo de compra de cada proveedor
        suppliers = repo.list_suppliers()
        chosen_lines = [
            {"supplier_id": buyable.loc[i, "supplier_id"], "quantity": row["Cantidad a pedir"], "unit_price": row["Precio unit."]}
            for i, row in chosen.iterrows()
        ]
        summary = supplier_summary(chosen_lines, suppliers)
        extra_lines: dict[str, list[dict]] = {}
        if summary:
            st.dataframe(
                pd.DataFrame(
                    {
                        "Proveedor": [r["supplier_name"] for r in summary],
                        "Líneas": [r["lines"] for r in summary],
                        "Total estimado": [r["total"] for r in summary],
                        "Mínimo de compra": [r["min_order_amount"] for r in summary],
                        "Plazo (días)": [r["lead_time_days"] for r in summary],
                        "Llegaría hacia": [r["arrival"].strftime("%d/%m/%Y") if r["arrival"] else "—" for r in summary],
                    }
                ),
                hide_index=True, width="stretch",
                column_config={
                    "Total estimado": st.column_config.NumberColumn(format="%.2f"),
                    "Mínimo de compra": st.column_config.NumberColumn(format="%.2f"),
                },
            )
        levels, offers = repo.stock_levels(), repo.list_offers()
        incoming = incoming_by_material(repo.list_orders(), repo.list_order_items())
        for r in summary:
            if not r["missing"]:
                continue
            st.warning(
                f"**{r['supplier_name']}**: el pedido suma {r['total']:,.2f} y su mínimo de compra es {r['min_order_amount']:,.2f} "
                f"(faltan {r['missing']:,.2f}). Aumenta cantidades, completa con materiales de abajo o junta este pedido con otro.",
                icon=":material/local_shipping:",
            )
            options = top_up_candidates(r["supplier_id"], offers, levels, incoming, {buyable.loc[k, "material_id"] for k in chosen.index})
            if options.empty:
                continue
            with st.expander(f"Completar el pedido a {r['supplier_name']} con materiales que están bajos"):
                st.caption("Materiales que este proveedor ofrece y están por debajo del doble de su stock mínimo. Marca los que quieras sumar.")
                pick = st.data_editor(
                    pd.DataFrame(
                        {
                            "Sumar": False, "Material": options["material_name"], "Stock": options["stock"], "Mínimo": options["min_stock"],
                            "Cantidad": options["quantity"], "Precio unit.": options["unit_price"], "Subtotal": options["subtotal"],
                        }
                    ),
                    hide_index=True, width="stretch", key=f"topup_{r['supplier_id']}",
                    disabled=["Material", "Stock", "Mínimo", "Precio unit.", "Subtotal"],
                    column_config={"Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.2f")},
                )
                for i, row in pick[pick["Sumar"] & (pick["Cantidad"] > 0)].iterrows():
                    extra_lines.setdefault(r["supplier_id"], []).append(
                        {
                            "material_id": options.loc[i, "material_id"], "material_name": options.loc[i, "material_name"],
                            "unit": options.loc[i, "unit"] or None, "quantity": float(row["Cantidad"]), "unit_price": float(row["Precio unit."]),
                        }
                    )
                added = sum(l["quantity"] * l["unit_price"] for l in extra_lines.get(r["supplier_id"], []))
                st.caption(f"Con lo marcado, el pedido sumaría {r['total'] + added:,.2f}.")

        if st.button("Crear las órdenes seleccionadas", type="primary", width="stretch", disabled=chosen.empty):
            created = []
            lead_by_supplier = {r["supplier_id"]: r["arrival"] for r in summary}
            for supplier_name, group in chosen.groupby("Proveedor"):
                source = buyable.loc[group.index]
                supplier_id = source.iloc[0]["supplier_id"]
                lines = [
                    {
                        "material_id": src["material_id"], "material_name": src["material_name"], "unit": src["unit"] or None,
                        "quantity": float(row["Cantidad a pedir"]), "unit_price": float(row["Precio unit."]),
                    }
                    for (_, row), (_, src) in zip(group.iterrows(), source.iterrows())
                ]
                lines += extra_lines.get(supplier_id, [])
                arrival = lead_by_supplier.get(supplier_id)
                terms = {**money.default_terms(), **({"expected_date": arrival} if arrival else {})}
                created.append(repo.create_order(supplier_id, supplier_name, None, "Sugerencia de compra", lines, terms))
            ui.flash(f"Órdenes creadas por sugerencia de compra: {', '.join(created)}.", ":material/receipt_long:")
            st.rerun()

    if not unquoted.empty:
        with st.expander(f"Sin proveedor con precio ({len(unquoted)})"):
            st.caption("Faltan, pero ningún proveedor tiene precio cargado. Cotízalos o impórtalos desde la lista de un proveedor.")
            st.dataframe(
                unquoted[["material_name", "unit", "deficit"]].rename(columns={"material_name": "Material", "unit": "Unidad", "deficit": "Faltante"}),
                hide_index=True, width="stretch",
            )
