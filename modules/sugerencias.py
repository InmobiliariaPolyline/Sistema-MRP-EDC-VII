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

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, ui
from utils.consumption import site_quantity

OPEN_STATUSES = ("pendiente", "enviada", "parcial")
COLUMNS = [
    "material_id", "category", "material_name", "unit", "demand", "stock", "incoming", "min_stock", "deficit",
    "supplier_id", "supplier_name", "unit_price",
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


def compute_suggestions(
    budgets: pd.DataFrame,
    orders: pd.DataFrame,
    items: pd.DataFrame,
    levels: pd.DataFrame,
    movements: pd.DataFrame,
    offers: pd.DataFrame,
) -> pd.DataFrame:
    """Materiales con faltante > 0, con el proveedor más barato asignado (ver el docstring del módulo)."""
    if levels.empty:
        return pd.DataFrame(columns=COLUMNS)

    dispatched: dict[tuple[str, str], float] = {}
    if not movements.empty:
        for row in movements[movements["project_site_id"].notna()].to_dict("records"):
            amount = site_quantity(row)
            if amount:
                key = (row["project_site_id"], row["material_id"])
                dispatched[key] = dispatched.get(key, 0.0) + amount

    demand: dict[str, float] = {}
    if not budgets.empty:
        for row in budgets.to_dict("records"):
            left = _num(row["planned_qty"]) - dispatched.get((row["project_site_id"], row["material_id"]), 0.0)
            if left > 0:
                demand[row["material_id"]] = demand.get(row["material_id"], 0.0) + left

    incoming: dict[str, float] = {}
    if not items.empty and not orders.empty:
        open_ids = set(orders.loc[orders["status"].isin(OPEN_STATUSES), "id"])
        for row in items[items["order_id"].isin(open_ids)].to_dict("records"):
            if row.get("material_id"):
                pending = _num(row["quantity"]) - _num(row.get("received_qty"))
                if pending > 0:
                    incoming[row["material_id"]] = incoming.get(row["material_id"], 0.0) + pending

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
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS).sort_values(["supplier_name", "category", "material_name"], na_position="last").reset_index(drop=True)


def current_suggestions() -> pd.DataFrame:
    return compute_suggestions(
        repo.list_budgets(),
        repo.list_orders(),
        repo.list_order_items(),
        repo.stock_levels(),
        repo.list_movements(limit=100000),
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
            "✅",
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
            }
        )
        edited = st.data_editor(
            table, hide_index=True, width="stretch", key="suggestion_editor",
            disabled=["Material", "Proveedor", "Stock", "Por llegar", "Precio unit."],
            column_config={
                "Cantidad a pedir": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help="Puedes ajustarla antes de crear las órdenes."),
                "Stock": st.column_config.NumberColumn(format="%.2f"),
                "Por llegar": st.column_config.NumberColumn(format="%.2f"),
                "Precio unit.": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        chosen = edited[(edited["Incluir"]) & (edited["Cantidad a pedir"] > 0)]
        st.caption(f"{len(chosen)} línea(s) seleccionada(s). Se crea una orden pendiente por proveedor, sin obra destino.")
        if st.button("Crear las órdenes seleccionadas", type="primary", width="stretch", disabled=chosen.empty):
            created = []
            for supplier_name, group in chosen.groupby("Proveedor"):
                source = buyable.loc[group.index]
                lines = [
                    {
                        "material_id": src["material_id"], "material_name": src["material_name"], "unit": src["unit"] or None,
                        "quantity": float(row["Cantidad a pedir"]), "unit_price": float(row["Precio unit."]),
                    }
                    for (_, row), (_, src) in zip(group.iterrows(), source.iterrows())
                ]
                created.append(repo.create_order(source.iloc[0]["supplier_id"], supplier_name, None, "Sugerencia de compra", lines))
            ui.flash(f"Órdenes creadas por sugerencia de compra: {', '.join(created)}.", "🧾")
            st.rerun()

    if not unquoted.empty:
        with st.expander(f"Sin proveedor con precio ({len(unquoted)})"):
            st.caption("Faltan, pero ningún proveedor tiene precio cargado. Cotízalos o impórtalos desde la lista de un proveedor.")
            st.dataframe(
                unquoted[["material_name", "unit", "deficit"]].rename(columns={"material_name": "Material", "unit": "Unidad", "deficit": "Faltante"}),
                hide_index=True, width="stretch",
            )
