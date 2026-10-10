"""Módulo de Materiales: catálogo maestro con búsqueda, alta, edición y baja.
Cada material muestra el mejor precio disponible entre los proveedores."""
import html
import math

import streamlit as st

from db import repository as repo
from modules import forms, inventario, ui

ALL_CATEGORIES = "Todas las categorías"
DENSITY_MAX = float(forms.RULES["Densidad (kg/m³, opcional)"]["num"]["max"])


def render() -> None:
    clicked = ui.page_header(
        "Catálogo",
        "Materiales",
        "Categoría, densidad y métrica de cómputo de cada material.",
        action_label="＋ Nuevo material",
        action_key="new_material_open",
    )
    if clicked:
        _new_material_dialog()

    _render_table()


def _material_form(material: dict | None) -> tuple[str, str, float | None, str]:
    forms.section("Identificación", "Categoría y nombre son obligatorios; juntos identifican el material.")
    c1, c2 = st.columns(2)
    category = c1.text_input(
        "Categoría", value=material["category"] if material else "", placeholder="Ej. Concreto",
        max_chars=forms.RULES["Categoría"]["max"], help="Agrupa materiales similares: concreto, acero, agregados…",
    )
    name = c2.text_input(
        "Nombre", value=material["name"] if material else "", placeholder="Ej. Concreto f'c=210",
        max_chars=forms.RULES["Nombre"]["max"], help="Conserva la especificación técnica: resistencia, diámetro o presentación.",
    )
    forms.section("Datos de cómputo", "Son opcionales. La densidad permite convertir volumen en peso.")
    c3, c4 = st.columns(2)
    stored_density = float(material["density"]) if material and material["density"] else 0.0
    density = c3.number_input(
        "Densidad (kg/m³, opcional)",
        min_value=0.0,
        max_value=max(DENSITY_MAX, stored_density),
        step=0.1,
        value=stored_density,
        help="Ej. 2400 para concreto. Deja 0 si no conoces la densidad.",
    )
    metric_label = c4.text_input(
        "Métrica de cómputo", value=(material["metric_label"] or "") if material else "",
        placeholder="Ej. Volumen (m³)", max_chars=forms.RULES["Métrica de cómputo"]["max"],
        help="Unidad con la que presupuestas y solicitas el material: m³, kg, m², unidades…",
    )
    return category.strip(), name.strip(), density or None, metric_label.strip()


def _save(values: tuple[str, str, float | None, str], material_id: str | None) -> None:
    category, name, density, metric_label = values
    errors = forms.validate({"Categoría": category, "Nombre": name, "Métrica de cómputo": metric_label})
    if density is None or density <= DENSITY_MAX:
        errors += forms.validate({"Densidad (kg/m³, opcional)": density or 0.0})
    elif not math.isfinite(density):
        errors.append("Densidad (kg/m³, opcional): ingresa un número finito.")
    if forms.errors(errors):
        return
    # El límite se amplía al valor guardado para conservar materiales existentes.
    try:
        materials = repo.list_materials()
    except Exception:
        st.error("No se pudo comprobar el catálogo. Tus datos se conservan; inténtalo de nuevo.")
        return
    original = materials[materials["id"] == material_id] if material_id else materials.iloc[0:0]
    original_density = float(original.iloc[0]["density"] or 0) if not original.empty else 0.0
    density_max = max(DENSITY_MAX, original_density)
    if density is not None and (not math.isfinite(density) or not 0 <= density <= density_max):
        errors.append(f"Densidad (kg/m³, opcional): ingresa un número entre 0 y {density_max:g}.")
    duplicate = materials[(materials["category"] == category) & (materials["name"] == name)]
    if material_id:
        duplicate = duplicate[duplicate["id"] != material_id]
    if not duplicate.empty:
        errors.append("Ya existe un material con esa categoría y nombre. Edita su ficha para actualizarlo.")
    if forms.errors(errors):
        return
    try:
        repo.upsert_material(category, name, density, metric_label, material_id)
    except Exception:
        st.error("No se pudo guardar el material. Revisa que categoría y nombre no estén repetidos e inténtalo de nuevo.")
        return
    ui.flash(f"Material «{name}» guardado.")
    st.rerun()


@st.dialog("Agregar material")
def _new_material_dialog() -> None:
    _material_dialog_form(None)


@st.dialog("Editar material")
def _edit_material_dialog(material: dict) -> None:
    _material_dialog_form(material)


def _material_dialog_form(material: dict | None) -> None:
    forms.header(
        "Editar material" if material else "Nuevo material",
        "Define su identificación y los datos que usarás en presupuestos, compras e inventario.",
    )
    with st.form(f"material_form_{material['id'] if material else 'new'}"):
        values = _material_form(material)
        cancel_col, save_col = st.columns([1, 2])
        # Crear primero Guardar mantiene esa acción al enviar con Enter.
        save = save_col.form_submit_button("Guardar cambios" if material else "Guardar", type="primary", width="stretch")
        cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
        preview = st.form_submit_button("Revisar datos", width="stretch", help="Muestra un resumen sin guardar.")
    if cancel:
        st.rerun()
    if preview:
        category, name, density, metric = values
        forms.section("Vista previa", "Estos datos todavía no se han guardado.")
        with st.container(border=True):
            st.write(name or "Nombre pendiente")
            st.caption(f"Categoría: {category or 'pendiente'} · Métrica: {metric or 'sin definir'}")
            st.caption(f"Densidad: {density:g} kg/m³" if density else "Sin densidad registrada")
    if save:
        _save(values, material["id"] if material else None)


@st.dialog("Ficha del material", width="large")
def info_dialog(material_id: str) -> None:
    """Todo lo que hay que saber de un material: qué es, cuánto pesa, quién lo
    vende y a qué precio, cuánto hay en el almacén y en qué obras se usa."""
    materials = repo.list_materials()
    match = materials[materials["id"] == material_id]
    if match.empty:
        ui.empty_state("Material no disponible", "Este material ya no existe en el catálogo.")
        if st.button("Cerrar", key="close_missing_material", width="stretch"):
            st.rerun()
        return
    m = match.to_dict("records")[0]

    st.markdown(f'<div class="mrp-eyebrow">{html.escape(m["category"])}</div><div class="mrp-page-title" style="font-size:24px">{html.escape(m["name"])}</div>', unsafe_allow_html=True)
    st.markdown(ui.pill(m["metric_label"] or "Sin métrica", "purple"), unsafe_allow_html=True)

    forms.section("Datos de cómputo", "Cómo usar la densidad y la unidad de este material.")
    if m["density"]:
        d = float(m["density"])
        st.write(
            f"**Densidad {d:,.0f} kg/m³:** un metro cúbico pesa ≈ {d:,.0f} kg ({d / 1000:,.2f} t). "
            f"Para convertir: peso (kg) = volumen (m³) × {d:,.0f}. Ejemplo: 10 m³ ≈ {10 * d:,.0f} kg."
        )
    else:
        st.write("Sin densidad registrada: no se puede convertir entre volumen y peso.")
    st.write(f"**Métrica de cómputo:** {m['metric_label'] or 'sin definir'} — es la unidad en la que se mide y se pide este material.")

    offers = repo.list_offers()
    offers = offers[offers["material_id"] == material_id] if not offers.empty else offers
    forms.section("Proveedores y precios", "Compara las ofertas y su disponibilidad.")
    if offers.empty:
        ui.empty_state("Sin ofertas", "Asigna este material desde el catálogo de un proveedor.", icon="🏪")
    else:
        ui.result_count(len(offers), len(offers), noun="ofertas")
        table = offers.assign(price=offers["price"].astype(float), Disponible=offers["available"].map(lambda v: "Sí" if v else "No"))
        st.dataframe(
            table[["supplier_name", "price", "Disponible"]].rename(columns={"supplier_name": "Proveedor", "price": "Precio"}),
            hide_index=True,
            width="stretch",
            column_config={"Precio": st.column_config.NumberColumn(format="%.2f")},
        )

    stock = inventario.stock_by_material()
    stock = stock[stock["material_id"] == material_id]
    forms.section("Inventario")
    if stock.empty:
        ui.empty_state("Sin movimientos", "Registra entradas o salidas en Inventario para ver el stock.")
    else:
        row = stock.to_dict("records")[0]
        st.write(f"En stock: **{row['stock']:g}** (entradas {row['entradas']:g} · salidas {row['salidas']:g})")

    budgets = repo.list_budgets()
    budgets = budgets[budgets["material_id"] == material_id] if not budgets.empty else budgets
    forms.section("Obras donde se usa")
    if budgets.empty:
        ui.empty_state("Sin obras asociadas", "Este material todavía no aparece en un presupuesto.", icon="🏗️")
    else:
        sites = repo.list_project_sites().set_index("id")["name"].to_dict()
        for b in budgets.to_dict("records"):
            st.write(f"• {sites.get(b['project_site_id'], 'Obra')}: {float(b['planned_qty']):g} previstos × {float(b['planned_unit_price']):,.2f}")
    if st.button("Cerrar ficha", key=f"close_material_{material_id}", width="stretch"):
        st.rerun()


def _delete_material(material_id: str, name: str) -> None:
    repo.delete_material(material_id)
    ui.flash(f"Material «{name}» eliminado.", "🗑️")


def _best_prices() -> dict[str, dict]:
    """Por material: el precio más bajo entre proveedores que lo tienen
    disponible y con precio cargado."""
    offers = repo.list_offers()
    if offers.empty:
        return {}
    offers = offers[offers["available"] & offers["price"].notna()]
    offers = offers[offers["price"].astype(float) > 0]
    best: dict[str, dict] = {}
    for row in offers.to_dict("records"):
        price = float(row["price"])
        current = best.get(row["material_id"])
        if current is None or price < current["price"]:
            best[row["material_id"]] = {"price": price, "supplier": row["supplier_name"]}
    return best


def _render_table() -> None:
    st.markdown('<div class="mrp-eyebrow">Inventario</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Catálogo</div>', unsafe_allow_html=True)

    df = repo.list_materials()
    if df.empty:
        ui.empty_state("Crea tu primer material", "Usa «＋ Nuevo material» para empezar el catálogo.")
        return

    total = len(df)
    best = _best_prices()
    ui.stat_grid([
        ui.stat_card("📦", total, "Materiales"),
        ui.stat_card("🗂️", df["category"].nunique(), "Categorías"),
        ui.stat_card("💰", len(best), "Con precio disponible"),
    ])

    f1, f2 = st.columns([3, 2])
    query = f1.text_input("Buscar", placeholder="Buscar por nombre o categoría…", key="mat_q", max_chars=100)
    categories = sorted(df["category"].dropna().unique().tolist())
    options = [ALL_CATEGORIES] + categories
    if st.session_state.get("mat_cat", ALL_CATEGORIES) not in options:
        st.session_state["mat_cat"] = ALL_CATEGORIES
    category_filter = f2.selectbox("Categoría", options, key="mat_cat")

    searching = bool(query.strip()) or category_filter != ALL_CATEGORIES
    if searching:
        st.button("Limpiar filtros", key="mat_reset", on_click=_reset_filters)

    if category_filter != ALL_CATEGORIES:
        df = df[df["category"] == category_filter]
    df = ui.filter_df(df, query, ["name", "category"])

    ui.result_count(len(df), total, noun="materiales")
    if df.empty:
        ui.empty_state("Sin coincidencias", "Prueba otro nombre o limpia los filtros para ver todo el catálogo.", icon="🔎")
        return
    df = ui.paginate(df, key="materials_catalog")

    for category, group in df.groupby("category"):
        with st.expander(f"{category} ({len(group)})", expanded=searching):
            for row in group.to_dict("records"):
                with st.container(border=True):
                    c1, c2, c0, c3, c4 = st.columns([4, 3, 1, 1, 1])
                    with c1:
                        sub = f"{row['density']} kg/m³" if row["density"] else "Sin densidad"
                        st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], sub), unsafe_allow_html=True)
                    with c2:
                        pills = ui.pill(row["metric_label"] or "Sin métrica", "purple")
                        offer = best.get(row["id"])
                        if offer:
                            pills += " " + ui.pill(f"Mejor: {offer['price']:,.2f} · {offer['supplier']}", "green")
                        st.markdown(pills, unsafe_allow_html=True)
                    with c0:
                        if st.button("ℹ️", key=f"info_material_{row['id']}", help="Ver información del material"):
                            info_dialog(row["id"])
                    with c3:
                        if st.button("✏️", key=f"edit_material_{row['id']}", help="Editar material"):
                            _edit_material_dialog(row)
                    with c4:
                        if st.button("🗑", key=f"del_material_{row['id']}", help="Eliminar material"):
                            ui.confirm_delete(
                                f"¿Eliminar el material «{row['name']}»? También se quitará de los catálogos de los proveedores.",
                                lambda mid=row["id"], nm=row["name"]: _delete_material(mid, nm),
                            )


def _reset_filters() -> None:
    st.session_state["mat_q"] = ""
    st.session_state["mat_cat"] = ALL_CATEGORIES
    st.session_state["materials_catalog_page"] = 1
