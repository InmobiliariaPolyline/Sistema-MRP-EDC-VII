"""Módulo de Materiales: catálogo maestro con búsqueda, alta, edición y baja.
Cada material muestra el mejor precio disponible entre los proveedores."""
import streamlit as st

from db import repository as repo
from modules import ui

ALL_CATEGORIES = "Todas las categorías"


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
    c1, c2 = st.columns(2)
    category = c1.text_input("Categoría", value=material["category"] if material else "", placeholder="Ej. Concreto")
    name = c2.text_input("Nombre", value=material["name"] if material else "", placeholder="Ej. Concreto f'c=210")
    c3, c4 = st.columns(2)
    density = c3.number_input(
        "Densidad (kg/m³, opcional)",
        min_value=0.0,
        step=0.1,
        value=float(material["density"]) if material and material["density"] else 0.0,
    )
    metric_label = c4.text_input(
        "Métrica de cómputo", value=(material["metric_label"] or "") if material else "", placeholder="Ej. Volumen (m³)"
    )
    return category.strip(), name.strip(), density or None, metric_label.strip()


def _save(values: tuple[str, str, float | None, str], material_id: str | None) -> None:
    category, name, density, metric_label = values
    if not category or not name:
        st.error("Categoría y nombre son obligatorios.")
        return
    try:
        repo.upsert_material(category, name, density, metric_label, material_id)
    except Exception:
        st.error("Ya existe un material con esa categoría y nombre.")
        return
    ui.flash(f"Material «{name}» guardado.")
    st.rerun()


@st.dialog("Agregar material")
def _new_material_dialog() -> None:
    values = _material_form(None)
    if st.button("Guardar", type="primary", use_container_width=True):
        _save(values, None)


@st.dialog("Editar material")
def _edit_material_dialog(material: dict) -> None:
    values = _material_form(material)
    if st.button("Guardar cambios", type="primary", use_container_width=True):
        _save(values, material["id"])


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
        st.info("Todavía no hay materiales cargados. Usa «＋ Nuevo material» arriba para crear el primero.")
        return

    f1, f2 = st.columns([3, 2])
    query = f1.text_input("Buscar", placeholder="🔍 Buscar por nombre o categoría…", label_visibility="collapsed", key="mat_q")
    categories = sorted(df["category"].dropna().unique().tolist())
    category_filter = f2.selectbox("Categoría", [ALL_CATEGORIES] + categories, label_visibility="collapsed", key="mat_cat")

    if category_filter != ALL_CATEGORIES:
        df = df[df["category"] == category_filter]
    df = ui.filter_df(df, query, ["name", "category"])

    if df.empty:
        st.info("Ningún material coincide con la búsqueda.")
        return
    st.caption(f"{len(df)} material(es)")

    best = _best_prices()
    searching = bool(query.strip()) or category_filter != ALL_CATEGORIES

    for category, group in df.groupby("category"):
        with st.expander(f"{category} ({len(group)})", expanded=searching):
            for row in group.to_dict("records"):
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([4, 3, 1, 1])
                    with c1:
                        sub = f"{row['density']} kg/m³" if row["density"] else "Sin densidad"
                        st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], sub), unsafe_allow_html=True)
                    with c2:
                        pills = ui.pill(row["metric_label"] or "Sin métrica", "purple")
                        offer = best.get(row["id"])
                        if offer:
                            pills += " " + ui.pill(f"Mejor: {offer['price']:,.2f} · {offer['supplier']}", "green")
                        st.markdown(pills, unsafe_allow_html=True)
                    with c3:
                        if st.button("✏️", key=f"edit_material_{row['id']}", help="Editar material"):
                            _edit_material_dialog(row)
                    with c4:
                        if st.button("🗑", key=f"del_material_{row['id']}", help="Eliminar material"):
                            ui.confirm_delete(
                                f"¿Eliminar el material «{row['name']}»? También se quitará de los catálogos de los proveedores.",
                                lambda mid=row["id"], nm=row["name"]: _delete_material(mid, nm),
                            )
