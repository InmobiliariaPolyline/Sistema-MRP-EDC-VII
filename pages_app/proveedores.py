"""Módulo de Proveedores: tarjetas apiladas, ficha de contacto y catálogo de
materiales por proveedor (disponible / no disponible, marcado a mano)."""
import streamlit as st

from db import repository as repo
from utils.excel import dataframe_to_excel_bytes, read_excel_upload

SELECTED_KEY = "selected_supplier_id"


def render() -> None:
    st.header("Proveedores")
    st.caption("Pensado para contactar: teléfono/email a la mano y qué materiales tiene disponibles cada uno.")

    if st.session_state.get(SELECTED_KEY):
        _render_supplier_detail(st.session_state[SELECTED_KEY])
        return

    _render_import_export()
    st.divider()
    _render_form()
    st.divider()
    _render_cards()


def _render_import_export() -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Exportar")
        df = repo.export_suppliers_df()
        st.download_button(
            "Descargar proveedores (Excel)",
            data=dataframe_to_excel_bytes(df, "Proveedores"),
            file_name="proveedores.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=df.empty,
        )

    with col2:
        st.subheader("Importar")
        uploaded = st.file_uploader(
            "Excel con columnas: name, contact_name, phone, email, notes (solo name es obligatoria)",
            type=["xlsx"],
            key="suppliers_uploader",
        )
        if uploaded is not None and st.button("Importar proveedores", key="import_suppliers_btn"):
            try:
                df = read_excel_upload(uploaded)
                ok, failed = repo.import_suppliers(df)
                st.success(f"Proveedores creados: {ok}. Filas descartadas: {failed}.")
                st.rerun()
            except Exception as exc:
                st.error(f"No fue posible importar el Excel: {exc}")


def _render_form() -> None:
    st.subheader("Registrar proveedor")
    with st.form("new_supplier_form", clear_on_submit=True):
        name = st.text_input("Nombre del proveedor")
        c1, c2 = st.columns(2)
        contact_name = c1.text_input("Persona de contacto (opcional)")
        phone = c2.text_input("Teléfono")
        c3, c4 = st.columns(2)
        email = c3.text_input("Correo (opcional)")
        notes = c4.text_input("Notas (opcional)")
        submitted = st.form_submit_button("Guardar")
        if submitted:
            if not name.strip():
                st.error("El nombre del proveedor es obligatorio.")
            else:
                repo.upsert_supplier(name.strip(), contact_name.strip() or None, phone.strip() or None, email.strip() or None, notes.strip() or None)
                st.success(f"Proveedor «{name}» registrado.")
                st.rerun()


def _render_cards() -> None:
    st.subheader("Proveedores registrados")
    df = repo.list_suppliers()
    if df.empty:
        st.info("Todavía no hay proveedores registrados.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"**{row['name']}**")
            c2.write(f"📞 {row['phone']}" if row["phone"] else "📞 —")
            c3.write(f"✉️ {row['email']}" if row["email"] else "✉️ —")
            with c4:
                cc1, cc2 = st.columns(2)
                if cc1.button("Ver catálogo", key=f"open_{row['id']}"):
                    st.session_state[SELECTED_KEY] = row["id"]
                    st.rerun()
                if cc2.button("Eliminar", key=f"del_supplier_{row['id']}"):
                    repo.delete_supplier(row["id"])
                    st.rerun()


def _render_supplier_detail(supplier_id: str) -> None:
    suppliers = repo.list_suppliers()
    match = suppliers[suppliers["id"] == supplier_id]
    if match.empty:
        st.session_state[SELECTED_KEY] = None
        st.rerun()
        return
    supplier = match.to_dict("records")[0]

    if st.button("← Volver a proveedores"):
        st.session_state[SELECTED_KEY] = None
        st.rerun()

    st.subheader(supplier["name"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Contacto", supplier["contact_name"] or "—")
    c2.metric("Teléfono", supplier["phone"] or "—")
    c3.metric("Correo", supplier["email"] or "—")
    if supplier["notes"]:
        st.caption(supplier["notes"])

    st.divider()
    st.write("**Catálogo de materiales de este proveedor**")
    catalog = repo.get_supplier_catalog(supplier_id)
    if catalog.empty:
        st.info("Todavía no hay materiales en el catálogo general para asignar.")
        return

    for category, group in catalog.groupby("category"):
        with st.expander(f"{category} ({int(group['offered'].sum())} ofrecidos de {len(group)})", expanded=True):
            for mat in group.to_dict("records"):
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.write(mat["name"])
                offered = c2.checkbox(
                    "Lo ofrece",
                    value=bool(mat["offered"]),
                    key=f"offered_{supplier_id}_{mat['id']}",
                )
                available = c3.checkbox(
                    "Disponible",
                    value=bool(mat["available"]),
                    disabled=not offered,
                    key=f"available_{supplier_id}_{mat['id']}",
                )
                if offered != bool(mat["offered"]) or available != bool(mat["available"]):
                    repo.set_supplier_material(supplier_id, mat["id"], offered, available, None)
                    st.rerun()
