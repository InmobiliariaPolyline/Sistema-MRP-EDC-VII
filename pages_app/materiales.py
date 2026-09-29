"""Módulo de Materiales: catálogo, alta/edición/baja e importar/exportar Excel."""
import streamlit as st

from db import repository as repo
from pages_app import ui
from utils.excel import dataframe_to_excel_bytes, read_excel_upload


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

    _render_import_export()
    _render_table()


@st.dialog("Agregar material")
def _new_material_dialog() -> None:
    c1, c2 = st.columns(2)
    category = c1.text_input("Categoría", placeholder="Ej. Concreto")
    name = c2.text_input("Nombre", placeholder="Ej. Concreto f'c=210")
    c3, c4 = st.columns(2)
    density = c3.number_input("Densidad (kg/m³, opcional)", min_value=0.0, step=0.1, value=0.0)
    metric_label = c4.text_input("Métrica de cómputo", placeholder="Ej. Volumen (m³)")
    if st.button("Guardar", type="primary", use_container_width=True):
        if not category.strip() or not name.strip():
            st.error("Categoría y nombre son obligatorios.")
        else:
            repo.upsert_material(category.strip(), name.strip(), density or None, metric_label.strip())
            st.success(f"Material «{name}» guardado.")
            st.rerun()


def _render_import_export() -> None:
    with st.expander("Importar / exportar Excel"):
        col1, col2 = st.columns(2)

        with col1:
            st.caption("EXPORTAR")
            df = repo.export_materials_df()
            st.download_button(
                "⬇ Descargar materiales (Excel)",
                data=dataframe_to_excel_bytes(df, "Materiales"),
                file_name="materiales.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=df.empty,
                use_container_width=True,
            )

        with col2:
            st.caption("IMPORTAR")
            uploaded = st.file_uploader(
                "Excel: category, name, density (opcional), metric_label",
                type=["xlsx"],
                key="materials_uploader",
                label_visibility="collapsed",
            )
            if uploaded is not None and st.button("Importar materiales", key="import_materials_btn", use_container_width=True):
                try:
                    df = read_excel_upload(uploaded)
                    ok, failed = repo.import_materials(df)
                    st.success(f"Importados/actualizados: {ok}. Filas descartadas: {failed}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"No fue posible importar el Excel: {exc}")
    st.write("")


def _render_table() -> None:
    st.markdown('<div class="mrp-eyebrow">Inventario</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Catálogo</div>', unsafe_allow_html=True)

    df = repo.list_materials()
    if df.empty:
        st.info("Todavía no hay materiales cargados. Usa «＋ Nuevo material» arriba para crear el primero.")
        return

    for category, group in df.groupby("category"):
        with st.expander(f"{category} ({len(group)})", expanded=False):
            for row in group.to_dict("records"):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 3, 1])
                    with c1:
                        sub = f"{row['density']} kg/m³" if row["density"] else "Sin densidad"
                        st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], sub), unsafe_allow_html=True)
                    with c2:
                        st.markdown(ui.pill(row["metric_label"] or "Sin métrica", "purple"), unsafe_allow_html=True)
                    with c3:
                        if st.button("🗑", key=f"del_material_{row['id']}", help="Eliminar material"):
                            repo.delete_material(row["id"])
                            st.rerun()
