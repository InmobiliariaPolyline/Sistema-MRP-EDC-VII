"""Módulo de Inventario: stock por material (entradas de las recepciones de
órdenes menos salidas por consumo en obra o mermas) y el historial de
movimientos."""
import pandas as pd
import streamlit as st

from db import repository as repo
from modules import ui
from utils.timeago import time_ago

ENTRY = "Entrada (ajuste / compra directa)"
CONSUMPTION = "Consumo en una obra"
LOSS = "Salida sin obra (merma, préstamo…)"


def stock_by_material() -> pd.DataFrame:
    """Entradas, salidas y stock actual de cada material con movimientos."""
    moves = repo.list_movements(limit=5000)
    columns = ["material_id", "material_name", "category", "unit", "entradas", "salidas", "stock"]
    if moves.empty:
        return pd.DataFrame(columns=columns)
    moves = moves.assign(quantity=moves["quantity"].astype(float))
    rows = []
    for material_id, group in moves.groupby("material_id"):
        first = group.iloc[0]
        entradas = group.loc[group["kind"] == "entrada", "quantity"].sum()
        salidas = group.loc[group["kind"] == "salida", "quantity"].sum()
        rows.append(
            {
                "material_id": material_id,
                "material_name": first["material_name"],
                "category": first["category"],
                "unit": first["unit"],
                "entradas": float(entradas),
                "salidas": float(salidas),
                "stock": float(entradas - salidas),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(["category", "material_name"]).reset_index(drop=True)


@st.dialog("Registrar movimiento de inventario")
def movement_dialog(default_site_id: str | None = None) -> None:
    """Entrada manual, consumo en obra o salida sin obra. También lo usa el módulo Obras."""
    materials = repo.list_materials()
    if materials.empty:
        st.info("Primero carga materiales en el catálogo.")
        return
    sites = repo.list_project_sites()
    stock = stock_by_material().set_index("material_id")["stock"].to_dict()

    kinds = [CONSUMPTION, ENTRY, LOSS] if default_site_id else [ENTRY, CONSUMPTION, LOSS]
    kind = st.radio("Tipo de movimiento", kinds, horizontal=False)

    options = {f"{r['category']} · {r['name']}": r for r in materials.to_dict("records")}
    choice = st.selectbox("Material", list(options))
    material = options[choice]
    available = float(stock.get(material["id"], 0.0))
    st.caption(f"Stock actual: **{available:g}** {material['metric_label'] or ''}")

    site_id = None
    if kind == CONSUMPTION:
        if sites.empty:
            st.warning("Primero registra una obra (Trabajadores → Obras / Proyectos).")
            return
        names = sites["name"].tolist()
        index = int(sites.index[sites["id"] == default_site_id][0]) if default_site_id and (sites["id"] == default_site_id).any() else 0
        site_name = st.selectbox("Obra", names, index=index)
        site_id = sites.loc[sites["name"] == site_name, "id"].iloc[0]

    qty = st.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0)
    note = st.text_input("Nota (opcional)")

    if st.button("Guardar movimiento", type="primary", use_container_width=True):
        if qty <= 0:
            st.error("La cantidad debe ser mayor que 0.")
            return
        if kind != ENTRY and qty > available:
            st.error(f"No hay stock suficiente: solo hay {available:g}.")
            return
        repo.add_movement(
            material["id"], "entrada" if kind == ENTRY else "salida", qty, site_id, note.strip() or None, ui.current_actor()
        )
        verb = {ENTRY: "Entrada", CONSUMPTION: "Consumo", LOSS: "Salida"}[kind]
        ui.flash(f"{verb} de {qty:g} × {material['name']} registrada.", "📦")
        st.rerun()


def render() -> None:
    if ui.page_header(
        "Almacén",
        "Inventario",
        "Cuánto hay de cada material: lo que llega con las recepciones menos lo que se consume en obra.",
        action_label="＋ Movimiento",
        action_key="new_movement_open",
    ):
        movement_dialog()

    stock = stock_by_material()
    total_in = float(stock["entradas"].sum()) if not stock.empty else 0.0
    total_out = float(stock["salidas"].sum()) if not stock.empty else 0.0
    low = int((stock["stock"] <= 0).sum()) if not stock.empty else 0
    ui.stat_grid(
        [
            ui.stat_card("📦", len(stock), "Materiales con movimiento", "en el almacén"),
            ui.stat_card("⬇️", f"{total_in:,.0f}", "Entradas", "unidades recibidas"),
            ui.stat_card("⬆️", f"{total_out:,.0f}", "Salidas", "consumo y mermas"),
            ui.stat_card("⚠️", low, "Agotados", "stock en cero", warn=low > 0),
        ]
    )

    tab_stock, tab_moves = st.tabs(["Stock actual", "Movimientos"])
    with tab_stock:
        _render_stock(stock)
    with tab_moves:
        _render_movements()


def _render_stock(stock: pd.DataFrame) -> None:
    if stock.empty:
        st.info("Todavía no hay stock. Se llena al registrar recepciones en las órdenes de compra, o con «＋ Movimiento».")
        return
    query = st.text_input("Buscar", placeholder="🔍 Buscar material o categoría…", label_visibility="collapsed", key="stock_q")
    stock = ui.filter_df(stock, query, ["material_name", "category"])
    if stock.empty:
        st.info("Ningún material coincide con la búsqueda.")
        return
    for row in stock.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 2])
            with c1:
                st.markdown(
                    ui.row_name_sub(ui.avatar(row["material_name"]), row["material_name"], f"{row['category']} · {row['unit'] or 'sin unidad'}"),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="mrp-row-sub">entradas {row["entradas"]:g} · salidas {row["salidas"]:g}</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                color = "red" if row["stock"] <= 0 else ("amber" if row["stock"] < row["entradas"] * 0.2 else "green")
                st.markdown(ui.pill(f"{row['stock']:g} en stock", color), unsafe_allow_html=True)


def _render_movements() -> None:
    moves = repo.list_movements(limit=300)
    if moves.empty:
        st.info("Sin movimientos todavía.")
        return
    rows = []
    for m in moves.to_dict("records"):
        sign = "+" if m["kind"] == "entrada" else "−"
        where = m["site_name"] or m["order_code"] or m["note"] or ""
        rows.append(
            ui.activity_item(
                f"{sign}{float(m['quantity']):g} {m['material_name']}",
                f"{where} · {m['actor'] or 'sistema'}" if where else (m["actor"] or "sistema"),
                "Entrada" if m["kind"] == "entrada" else "Salida",
                time_ago(str(m["created_at"]).replace(" ", "T")),
            )
        )
    st.markdown('<div class="mrp-panel">' + "".join(rows) + "</div>", unsafe_allow_html=True)
