"""Módulo de Materiales: catálogo, alta/edición/baja e importar/exportar Excel."""
import streamlit as st

from db import repository as repo
from utils.excel import dataframe_to_excel_bytes, read_excel_upload


def render() -> None:
    st.header("Materiales")
    st.caption("Catálogo general de materiales, con categoría, densidad y métrica de cómputo.")

    _render_import_export()
    st.divider()
    _render_form()
    st.divider()
    _render_table()


def _render_import_export() -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Exportar")
        df = repo.export_materials_df()
        st.download_button(
            "Descargar materiales (Excel)",
            data=dataframe_to_excel_bytes(df, "Materiales"),
            file_name="materiales.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=df.empty,
        )

    with col2:
        st.subheader("Importar")
        uploaded = st.file_uploader(
            "Excel con columnas: category, name, density (opcional), metric_label",
            type=["xlsx"],
            key="materials_uploader",
        )
        if uploaded is not None and st.button("Importar materiales", key="import_materials_btn"):
            try:
                df = read_excel_upload(uploaded)
                ok, failed = repo.import_materials(df)
                st.success(f"Importados/actualizados: {ok}. Filas descartadas: {failed}.")
                st.rerun()
            except Exception as exc:
                st.error(f"No fue posible importar el Excel: {exc}")


def _render_form() -> None:
    st.subheader("Agregar material")
    with st.form("new_material_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        category = c1.text_input("Categoría", placeholder="Ej. Concreto")
        name = c2.text_input("Nombre", placeholder="Ej. Concreto f'c=210")
        c3, c4 = st.columns(2)
        density = c3.number_input("Densidad (kg/m³, opcional)", min_value=0.0, step=0.1, value=0.0)
        metric_label = c4.text_input("Métrica de cómputo", placeholder="Ej. Volumen (m³)")
        submitted = st.form_submit_button("Guardar")
        if submitted:
            if not category.strip() or not name.strip():
                st.error("Categoría y nombre son obligatorios.")
            else:
                repo.upsert_material(category.strip(), name.strip(), density or None, metric_label.strip())
                st.success(f"Material «{name}» guardado.")
                st.rerun()


def _render_table() -> None:
    st.subheader("Catálogo")
    df = repo.list_materials()
    if df.empty:
        st.info("Todavía no hay materiales cargados.")
        return

    for category, group in df.groupby("category"):
        with st.expander(f"{category} ({len(group)})", expanded=False):
            for row in group.to_dict("records"):
                c1, c2, c3, c4 = st.columns([3, 2, 3, 1])
                c1.write(f"**{row['name']}**")
                c2.write(f"{row['density']} kg/m³" if row["density"] else "—")
                c3.write(row["metric_label"] or "—")
                if c4.button("Eliminar", key=f"del_material_{row['id']}"):
                    repo.delete_material(row["id"])
                    st.rerun()
