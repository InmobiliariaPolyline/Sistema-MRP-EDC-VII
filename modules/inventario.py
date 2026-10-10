"""Módulo de Inventario: stock por material (entradas de las recepciones de
órdenes menos salidas por consumo en obra o mermas) y el historial de
movimientos."""
import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, ui
from utils.timeago import time_ago

ENTRY = "Entrada (ajuste / compra directa)"
CONSUMPTION = "Consumo en una obra"
LOSS = "Salida sin obra (merma, préstamo…)"


def _clear_movement_draft(context: str) -> None:
    for field in ("kind", "material", "site", "qty", "note"):
        st.session_state.pop(f"move_{field}_{context}", None)


def _clear_stock_search() -> None:
    st.session_state["stock_q"] = ""


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
    context = default_site_id or "warehouse"
    forms.header("Registra una entrada o salida", "Revisa el material, la cantidad y el efecto sobre el stock antes de guardar.")
    materials = repo.list_materials()
    if materials.empty:
        ui.empty_state("Faltan materiales", "Registra un material en el catálogo para comenzar a controlar el stock.")
        if st.button("Cancelar", key="move_cancel_empty", width="stretch"):
            _clear_movement_draft(context)
            st.rerun()
        return
    ui.tip("Ejemplo: «Consumo en una obra», Concreto, 2, obra Torre Central. Las entradas de órdenes se registran solas al recibirlas.")
    sites = repo.list_project_sites()
    stock = stock_by_material().set_index("material_id")["stock"].to_dict()

    kinds = [CONSUMPTION, ENTRY, LOSS] if default_site_id else [ENTRY, CONSUMPTION, LOSS]
    forms.section("1. Tipo y material", "Las recepciones de órdenes ya generan entradas; usa este formulario para otros movimientos.")
    kind = st.radio("Tipo de movimiento", kinds, horizontal=False, key=f"move_kind_{context}",
                    help="Entrada suma stock. Consumo y salida sin obra lo descuentan.")

    options = {f"{r['category']} · {r['name']}": r for r in materials.to_dict("records")}
    choice = st.selectbox("Material", list(options), key=f"move_material_{context}", help="Verifica la unidad antes de indicar la cantidad.")
    material = options[choice]
    available = float(stock.get(material["id"], 0.0))
    st.caption(f"Stock actual: **{available:g}** {material['metric_label'] or ''}")

    site_id = None
    site_name = None
    if kind == CONSUMPTION:
        if sites.empty:
            st.warning("Primero registra una obra (Trabajadores → Obras / Proyectos).")
            if st.button("Cancelar", key="move_cancel_no_site", width="stretch"):
                _clear_movement_draft(context)
                st.rerun()
            return
        names = sites["name"].tolist()
        matched = sites[sites["id"] == default_site_id] if default_site_id else sites.iloc[0:0]
        index = names.index(matched.iloc[0]["name"]) if not matched.empty else 0
        site_name = st.selectbox("Obra", names, index=index, key=f"move_site_{context}",
                               help="El consumo aparecerá en el seguimiento de materiales de esta obra.")
        site_id = sites.loc[sites["name"] == site_name, "id"].iloc[0]

    forms.section("2. Cantidad y motivo", "Puedes usar decimales. Las salidas deben estar cubiertas por el stock actual.")
    qty = st.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, key=f"move_qty_{context}",
                          help=f"Unidad: {material['metric_label'] or 'unid.'}. Debe ser mayor que 0.")
    note = st.text_input("Nota (opcional)", placeholder="Ej. Consumo para vaciado de losa / ajuste por conteo",
                         max_chars=500, key=f"move_note_{context}", help="Describe el motivo para reconocerlo después en el historial. Hasta 500 caracteres.")

    forms.section("3. Revisa el movimiento", "El inventario se actualiza al guardar.")
    after = available + qty if kind == ENTRY else available - qty
    before_col, after_col = st.columns(2)
    before_col.metric("Stock actual", f"{available:g} {material['metric_label'] or 'unid.'}")
    after_col.metric("Stock después", f"{after:g} {material['metric_label'] or 'unid.'}")
    st.caption(f"{kind} · {material['name']}" + (f" · {site_name}" if site_name else ""))
    if kind != ENTRY and qty > available:
        st.warning(f"Reduce la cantidad: solo hay {available:g} {material['metric_label'] or 'unid.'} disponibles.")
    cancel, save = st.columns([1, 2])
    if cancel.button("Cancelar", key="move_cancel", width="stretch"):
        _clear_movement_draft(context)
        st.rerun()
    if save.button("Guardar movimiento", type="primary", width="stretch"):
        issues = forms.validate({"Cantidad": qty, "Nota (opcional)": note})
        if kind != ENTRY:
            clear = getattr(repo.list_movements, "clear", None)
            if callable(clear):
                clear()
            current = stock_by_material().set_index("material_id")["stock"].to_dict()
            available = float(current.get(material["id"], 0.0))
            if qty > available:
                issues.append(f"Cantidad: stock insuficiente; quedan {available:g} {material['metric_label'] or 'unid.'}.")
        if forms.errors(issues):
            return
        repo.add_movement(
            material["id"], "entrada" if kind == ENTRY else "salida", qty, site_id, note.strip() or None, ui.current_actor()
        )
        verb = {ENTRY: "Entrada", CONSUMPTION: "Consumo", LOSS: "Salida"}[kind]
        _clear_movement_draft(context)
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
        ui.empty_state("Aún no hay movimientos de stock", "Registra una recepción en Órdenes de compra o una entrada con «Movimiento».")
        return
    total = len(stock)
    query = st.text_input("Buscar", placeholder="Material o categoría…", key="stock_q")
    stock = ui.filter_df(stock, query, ["material_name", "category"])
    ui.result_count(len(stock), total, noun="materiales")
    if query:
        st.button("Limpiar búsqueda", key="stock_clear", on_click=_clear_stock_search)
    if stock.empty:
        ui.empty_state("Sin coincidencias", "Prueba otro nombre o limpia la búsqueda para ver todo el inventario.", icon="🔎")
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
        ui.empty_state("Aún no hay movimientos", "Las recepciones, entradas y consumos aparecerán aquí con su fecha y responsable.")
        return
    st.caption(f"{len(moves)} movimiento(s) reciente(s). Se muestran hasta los últimos 300.")
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
