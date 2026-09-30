"""Módulo de Proveedores: tarjetas apiladas, ficha de contacto y catálogo de
materiales por proveedor (disponible / no disponible, marcado a mano)."""
import streamlit as st

from db import repository as repo
from modules import ui

SELECTED_KEY = "selected_supplier_id"


def render() -> None:
    if st.session_state.get(SELECTED_KEY):
        _render_supplier_detail(st.session_state[SELECTED_KEY])
        return

    clicked = ui.page_header(
        "Gestión de proveedores",
        "Proveedores",
        "Pensado para contactar: teléfono/email a la mano y qué materiales tiene disponible cada uno.",
        action_label="＋ Nuevo proveedor",
        action_key="new_supplier_open",
    )
    if clicked:
        _new_supplier_dialog()

    _render_cards()


@st.dialog("Registrar proveedor")
def _new_supplier_dialog() -> None:
    name = st.text_input("Nombre del proveedor")
    c1, c2 = st.columns(2)
    contact_name = c1.text_input("Persona de contacto (opcional)")
    phone = c2.text_input("Teléfono")
    c3, c4 = st.columns(2)
    email = c3.text_input("Correo (opcional)")
    notes = c4.text_input("Notas (opcional)")
    if st.button("Guardar", type="primary", use_container_width=True):
        if not name.strip():
            st.error("El nombre del proveedor es obligatorio.")
        else:
            repo.upsert_supplier(name.strip(), contact_name.strip() or None, phone.strip() or None, email.strip() or None, notes.strip() or None)
            st.success(f"Proveedor «{name}» registrado.")
            st.rerun()


def _render_cards() -> None:
    st.markdown('<div class="mrp-eyebrow">Directorio</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Proveedores registrados</div>', unsafe_allow_html=True)

    df = repo.list_suppliers()
    if df.empty:
        st.info("Todavía no hay proveedores registrados. Usa «＋ Nuevo proveedor» arriba para crear el primero.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 2, 3, 1])
            with c1:
                sub = row["phone"] or "Sin teléfono"
                st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], sub), unsafe_allow_html=True)
            with c2:
                st.markdown(
                    f'<div class="mrp-row-sub">✉️ {row["email"] or "—"}</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                if st.button("Catálogo", key=f"open_{row['id']}", use_container_width=True):
                    st.session_state[SELECTED_KEY] = row["id"]
                    st.rerun()
            with c4:
                if st.button("🗑", key=f"del_supplier_{row['id']}", help="Eliminar proveedor"):
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

    ui.page_header("Ficha de proveedor", supplier["name"])

    ui.stat_grid(
        [
            ui.stat_card("🙍", supplier["contact_name"] or "—", "Contacto"),
            ui.stat_card("📞", supplier["phone"] or "—", "Teléfono"),
            ui.stat_card("✉️", supplier["email"] or "—", "Correo"),
        ]
    )
    if supplier["notes"]:
        st.caption(supplier["notes"])

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Catálogo</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Materiales de este proveedor</div>', unsafe_allow_html=True)

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
