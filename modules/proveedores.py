"""Módulo de Proveedores: directorio con contacto rápido (llamar, WhatsApp,
correo) y, por proveedor, su catálogo de materiales con disponibilidad y
precio (para poder comparar quién vende más barato)."""
import pandas as pd
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
        "Pensado para contactar: llama o escribe por WhatsApp con un clic, y mira qué materiales tiene cada uno.",
        action_label="＋ Nuevo proveedor",
        action_key="new_supplier_open",
    )
    if clicked:
        _new_supplier_dialog()

    _render_cards()


def _supplier_form(supplier: dict | None) -> tuple[str, str | None, str | None, str | None, str | None]:
    ui.tip("Ejemplo: «Ferretería Norte», contacto «Ana Ruiz», teléfono «51987654321» (con código de país para usar WhatsApp).")
    name = st.text_input("Nombre del proveedor", value=supplier["name"] if supplier else "")
    c1, c2 = st.columns(2)
    contact_name = c1.text_input("Persona de contacto (opcional)", value=(supplier["contact_name"] or "") if supplier else "")
    phone = c2.text_input("Teléfono", value=(supplier["phone"] or "") if supplier else "", help="Con código de país para que WhatsApp funcione, ej. 34600111222")
    c3, c4 = st.columns(2)
    email = c3.text_input("Correo (opcional)", value=(supplier["email"] or "") if supplier else "")
    notes = c4.text_input("Notas (opcional)", value=(supplier["notes"] or "") if supplier else "")
    return name.strip(), contact_name.strip() or None, phone.strip() or None, email.strip() or None, notes.strip() or None


def _save(values: tuple, supplier_id: str | None) -> None:
    name, contact_name, phone, email, notes = values
    if not name:
        st.error("El nombre del proveedor es obligatorio.")
        return
    repo.upsert_supplier(name, contact_name, phone, email, notes, supplier_id)
    ui.flash(f"Proveedor «{name}» guardado.")
    st.rerun()


@st.dialog("Registrar proveedor")
def _new_supplier_dialog() -> None:
    values = _supplier_form(None)
    if st.button("Guardar", type="primary", use_container_width=True):
        _save(values, None)


@st.dialog("Editar proveedor")
def _edit_supplier_dialog(supplier: dict) -> None:
    values = _supplier_form(supplier)
    if st.button("Guardar cambios", type="primary", use_container_width=True):
        _save(values, supplier["id"])


def _delete_supplier(supplier_id: str, name: str) -> None:
    repo.delete_supplier(supplier_id)
    if st.session_state.get(SELECTED_KEY) == supplier_id:
        st.session_state[SELECTED_KEY] = None
    ui.flash(f"Proveedor «{name}» eliminado.", "🗑️")


def _render_cards() -> None:
    st.markdown('<div class="mrp-eyebrow">Directorio</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Proveedores registrados</div>', unsafe_allow_html=True)

    df = repo.list_suppliers()
    if df.empty:
        st.info("Todavía no hay proveedores registrados. Usa «＋ Nuevo proveedor» arriba para crear el primero.")
        return

    query = st.text_input("Buscar", placeholder="🔍 Buscar por nombre, contacto, teléfono o correo…", label_visibility="collapsed", key="sup_q")
    df = ui.filter_df(df, query, ["name", "contact_name", "phone", "email"])
    if df.empty:
        st.info("Ningún proveedor coincide con la búsqueda.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c3, c4, c5 = st.columns([6, 2.2, 1, 1])
            with c1:
                sub = row["contact_name"] or row["phone"] or "Sin contacto"
                st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], sub), unsafe_allow_html=True)
                st.markdown(ui.contact_links(row["phone"], row["email"]), unsafe_allow_html=True)
            with c3:
                if st.button("Catálogo", key=f"open_{row['id']}", use_container_width=True):
                    st.session_state[SELECTED_KEY] = row["id"]
                    st.rerun()
            with c4:
                if st.button("✏️", key=f"edit_supplier_{row['id']}", help="Editar proveedor"):
                    _edit_supplier_dialog(row)
            with c5:
                if st.button("🗑", key=f"del_supplier_{row['id']}", help="Eliminar proveedor"):
                    ui.confirm_delete(
                        f"¿Eliminar al proveedor «{row['name']}»? Se borra también su catálogo de materiales; las órdenes de compra ya creadas se conservan.",
                        lambda sid=row["id"], nm=row["name"]: _delete_supplier(sid, nm),
                    )


def _render_supplier_detail(supplier_id: str) -> None:
    suppliers = repo.list_suppliers()
    match = suppliers[suppliers["id"] == supplier_id]
    if match.empty:
        st.session_state[SELECTED_KEY] = None
        st.rerun()
        return
    supplier = match.to_dict("records")[0]

    b1, b2, _ = st.columns([1.5, 1.5, 5])
    if b1.button("← Volver"):
        st.session_state[SELECTED_KEY] = None
        st.rerun()
    if b2.button("✏️ Editar"):
        _edit_supplier_dialog(supplier)

    ui.page_header("Ficha de proveedor", supplier["name"])

    ui.stat_grid(
        [
            ui.stat_card("🙍", supplier["contact_name"] or "—", "Contacto"),
            ui.stat_card("📞", supplier["phone"] or "—", "Teléfono"),
            ui.stat_card("✉️", supplier["email"] or "—", "Correo"),
        ]
    )
    st.markdown(ui.contact_links(supplier["phone"], supplier["email"]), unsafe_allow_html=True)
    if supplier["notes"]:
        st.caption(supplier["notes"])

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Catálogo</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Materiales de este proveedor</div>', unsafe_allow_html=True)

    catalog = repo.get_supplier_catalog(supplier_id)
    if catalog.empty:
        st.info("Todavía no hay materiales en el catálogo general para asignar.")
        return

    query = st.text_input("Buscar material", placeholder="🔍 Buscar material o categoría…", label_visibility="collapsed", key=f"cat_q_{supplier_id}")
    catalog = ui.filter_df(catalog, query, ["name", "category"])
    if catalog.empty:
        st.info("Ningún material coincide con la búsqueda.")
        return
    searching = bool(query.strip())

    for category, group in catalog.groupby("category"):
        offered_count = int(group["offered"].sum())
        with st.expander(f"{category} ({offered_count} ofrecidos de {len(group)})", expanded=searching or offered_count > 0):
            for mat in group.to_dict("records"):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                c1.write(mat["name"])
                offered = c2.checkbox("Lo ofrece", value=bool(mat["offered"]), key=f"offered_{supplier_id}_{mat['id']}")
                available = c3.checkbox(
                    "Disponible",
                    value=bool(mat["available"]),
                    disabled=not offered,
                    key=f"available_{supplier_id}_{mat['id']}",
                )
                stored_price = float(mat["price"]) if pd.notna(mat["price"]) else 0.0
                price = c4.number_input(
                    "Precio",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    value=stored_price,
                    disabled=not offered,
                    label_visibility="collapsed",
                    key=f"price_{supplier_id}_{mat['id']}",
                    help="Precio unitario de este proveedor (0 = sin precio)",
                )
                if offered != bool(mat["offered"]) or available != bool(mat["available"]) or (offered and price != stored_price):
                    repo.set_supplier_material(supplier_id, mat["id"], offered, available, price or None)
                    st.rerun()
