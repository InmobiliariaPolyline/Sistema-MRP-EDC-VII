"""Módulo de Proveedores: directorio con contacto rápido (llamar, WhatsApp,
correo) y, por proveedor, su catálogo de materiales con disponibilidad y
precio (para poder comparar quién vende más barato)."""
import math

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, ui

SELECTED_KEY = "selected_supplier_id"
ALL_CATALOG = "Todos los materiales"
CATALOG_STATES = [ALL_CATALOG, "Ofrecidos", "Disponibles", "Sin precio", "No ofrecidos"]
PRICE_MAX = 10000000.0


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
    forms.section("Identificación", "El nombre del proveedor es el único dato obligatorio.")
    name = st.text_input(
        "Nombre del proveedor", value=supplier["name"] if supplier else "",
        placeholder="Ej. Ferretería Norte", max_chars=forms.RULES["Nombre del proveedor"]["max"],
        help="Nombre comercial o razón social para identificarlo en compras y catálogos.",
    )
    forms.section("Contacto", "Todos estos datos son opcionales. Facilitan las llamadas, WhatsApp y el correo.")
    c1, c2 = st.columns(2)
    contact_name = c1.text_input(
        "Persona de contacto (opcional)", value=(supplier["contact_name"] or "") if supplier else "",
        placeholder="Ej. Ana Ruiz", max_chars=forms.RULES["Persona de contacto (opcional)"]["max"],
        help="Persona que recibe consultas y pedidos.",
    )
    phone = c2.text_input(
        "Teléfono", value=(supplier["phone"] or "") if supplier else "",
        placeholder="Ej. +51 987 654 321", max_chars=forms.RULES["Teléfono"]["max"],
        help="Opcional. Incluye el código de país para abrir WhatsApp.",
    )
    email = st.text_input(
        "Correo (opcional)", value=(supplier["email"] or "") if supplier else "",
        placeholder="Ej. ventas@empresa.com", max_chars=forms.RULES["Correo (opcional)"]["max"],
        help="Dirección a la que se enviarán consultas o solicitudes.",
    )
    forms.section("Información adicional")
    notes = st.text_area(
        "Notas (opcional)", value=(supplier["notes"] or "") if supplier else "",
        placeholder="Ej. Horario de atención, condiciones de entrega o forma de pago.",
        max_chars=forms.RULES["Notas (opcional)"]["max"], height=100,
        help="Información interna útil para coordinar las compras.",
    )
    return name.strip(), contact_name.strip() or None, phone.strip() or None, email.strip() or None, notes.strip() or None


def _save(values: tuple, supplier_id: str | None) -> None:
    name, contact_name, phone, email, notes = values
    if forms.errors(forms.validate({
        "Nombre del proveedor": name,
        "Persona de contacto (opcional)": contact_name,
        "Teléfono": phone,
        "Correo (opcional)": email,
        "Notas (opcional)": notes,
    })):
        return
    try:
        repo.upsert_supplier(name, contact_name, phone, email, notes, supplier_id)
    except Exception:
        st.error("No se pudo guardar el proveedor. Tus datos se conservan; inténtalo de nuevo.")
        return
    ui.flash(f"Proveedor «{name}» guardado.")
    st.rerun()


@st.dialog("Registrar proveedor")
def _new_supplier_dialog() -> None:
    _supplier_dialog_form(None)


@st.dialog("Editar proveedor")
def _edit_supplier_dialog(supplier: dict) -> None:
    _supplier_dialog_form(supplier)


def _supplier_dialog_form(supplier: dict | None) -> None:
    forms.header(
        "Editar proveedor" if supplier else "Nuevo proveedor",
        "Registra sus datos de contacto. Después podrás configurar los materiales que ofrece y sus precios.",
    )
    with st.form(f"supplier_form_{supplier['id'] if supplier else 'new'}"):
        values = _supplier_form(supplier)
        cancel_col, save_col = st.columns([1, 2])
        save = save_col.form_submit_button("Guardar cambios" if supplier else "Guardar", type="primary", width="stretch")
        cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
        preview = st.form_submit_button("Revisar datos", width="stretch", help="Revisa el contacto sin guardar.")
    if cancel:
        st.rerun()
    if preview:
        name, contact, phone, email, notes = values
        forms.section("Vista previa", "Estos datos todavía no se han guardado.")
        with st.container(border=True):
            st.write(name or "Nombre pendiente")
            st.caption(contact or "Sin persona de contacto")
            st.write(f"Teléfono: {phone or 'sin registrar'}")
            st.write(f"Correo: {email or 'sin registrar'}")
            if notes:
                st.caption(notes)
    if save:
        _save(values, supplier["id"] if supplier else None)


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
        ui.empty_state("Registra tu primer proveedor", "Usa «＋ Nuevo proveedor» para guardar su contacto y configurar su catálogo.", icon="🏪")
        return

    total = len(df)
    with_contact = (df["phone"].fillna("").str.strip().ne("") | df["email"].fillna("").str.strip().ne("")).sum()
    ui.stat_grid([
        ui.stat_card("🏪", total, "Proveedores"),
        ui.stat_card("📞", int(with_contact), "Con teléfono o correo"),
    ])
    query = st.text_input("Buscar", placeholder="Buscar por nombre, contacto, teléfono o correo…", key="sup_q", max_chars=120)
    if query.strip():
        st.button("Limpiar búsqueda", key="sup_reset", on_click=_reset_search)
    df = ui.filter_df(df, query, ["name", "contact_name", "phone", "email"])
    ui.result_count(len(df), total, noun="proveedores")
    if df.empty:
        ui.empty_state("Sin coincidencias", "Prueba otro nombre o limpia la búsqueda para ver todos los proveedores.", icon="🔎")
        return
    df = ui.paginate(df, key="suppliers_directory")

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c3, c4, c5 = st.columns([6, 2.2, 1, 1])
            with c1:
                sub = row["contact_name"] or row["phone"] or "Sin contacto"
                st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], sub), unsafe_allow_html=True)
                st.markdown(ui.contact_links(row["phone"], row["email"]), unsafe_allow_html=True)
            with c3:
                if st.button("Catálogo", key=f"open_{row['id']}", width="stretch"):
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
        forms.section("Notas del proveedor")
        st.caption(supplier["notes"])

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Catálogo</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Materiales de este proveedor</div>', unsafe_allow_html=True)

    catalog = repo.get_supplier_catalog(supplier_id)
    if catalog.empty:
        ui.empty_state("El catálogo general está vacío", "Crea materiales en Materiales y vuelve aquí para indicar cuáles ofrece el proveedor.")
        return

    total = len(catalog)
    offered_count = int(catalog["offered"].sum())
    available_count = int((catalog["offered"] & catalog["available"]).sum())
    with_price = catalog["price"].fillna(0).astype(float) > 0
    priced_count = int((catalog["offered"] & with_price).sum())
    ui.stat_grid([
        ui.stat_card("📦", offered_count, "Materiales ofrecidos", f"De {total} en el catálogo general"),
        ui.stat_card("✅", available_count, "Disponibles"),
        ui.stat_card("💰", priced_count, "Con precio"),
    ])
    if offered_count:
        st.progress(priced_count / offered_count, text=f"Precios registrados: {priced_count} de {offered_count} materiales ofrecidos")
    st.caption("Los cambios se guardan automáticamente. Marca «Lo ofrece», indica disponibilidad y registra el precio unitario. 0 significa sin precio.")
    f1, f2 = st.columns([3, 2])
    query = f1.text_input("Buscar material", placeholder="Buscar material o categoría…", key=f"cat_q_{supplier_id}", max_chars=180)
    state = f2.selectbox("Estado del catálogo", CATALOG_STATES, key=f"cat_state_{supplier_id}")
    searching = bool(query.strip()) or state != ALL_CATALOG
    if searching:
        st.button("Limpiar filtros", key=f"cat_reset_{supplier_id}", on_click=_reset_catalog_filters, args=(supplier_id,))
    if state == "Ofrecidos":
        catalog = catalog[catalog["offered"]]
    elif state == "Disponibles":
        catalog = catalog[catalog["offered"] & catalog["available"]]
    elif state == "Sin precio":
        catalog = catalog[catalog["offered"] & ~with_price]
    elif state == "No ofrecidos":
        catalog = catalog[~catalog["offered"]]
    catalog = ui.filter_df(catalog, query, ["name", "category"])
    ui.result_count(len(catalog), total, noun="materiales")
    if catalog.empty:
        ui.empty_state("Sin materiales para estos filtros", "Cambia el estado del catálogo o limpia los filtros para ver todos los materiales.", icon="🔎")
        return
    catalog = ui.paginate(catalog, key=f"supplier_catalog_{supplier_id}")
    remembered = st.session_state.get(f"_catalog_values_{supplier_id}", {})

    for category, group in catalog.groupby("category"):
        offered_count = int(group["offered"].sum())
        with st.expander(f"{category} ({offered_count} ofrecidos de {len(group)})", expanded=searching or offered_count > 0):
            for mat in group.to_dict("records"):
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 2])
                    c1.write(mat["name"])
                    c1.caption(mat.get("metric_label") or "Sin métrica definida")
                    draft = remembered.get(mat["id"], {})
                    offered = c2.checkbox(
                        "Lo ofrece", value=bool(mat["offered"]), key=f"offered_{supplier_id}_{mat['id']}",
                        on_change=_remember_catalog_values, args=(supplier_id, mat["id"]),
                    )
                    available = c3.checkbox(
                        "Disponible", value=bool(mat["available"]) if mat["offered"] else bool(draft.get("available", False)), disabled=not offered,
                        key=f"available_{supplier_id}_{mat['id']}", help="Activa si el proveedor puede suministrarlo ahora.",
                        on_change=_remember_catalog_values, args=(supplier_id, mat["id"]),
                    )
                    stored_price = float(mat["price"]) if pd.notna(mat["price"]) else 0.0
                    widget_price = stored_price if mat["offered"] else float(draft.get("price", stored_price))
                    price_max = max(PRICE_MAX, stored_price, widget_price)
                    price = c4.number_input(
                        "Precio", min_value=0.0, max_value=price_max, step=0.1, format="%.2f",
                        value=widget_price, disabled=not offered, key=f"price_{supplier_id}_{mat['id']}",
                        help="Precio unitario de este proveedor en la métrica indicada (0 = sin precio).",
                        on_change=_remember_catalog_values, args=(supplier_id, mat["id"]),
                    )
                    changed = offered != bool(mat["offered"]) or (offered and (available != bool(mat["available"]) or price != stored_price))
                    if changed:
                        errors = []
                        if offered and (not math.isfinite(price) or not 0 <= price <= price_max):
                            errors.append(f"Precio: ingresa un número entre 0 y {price_max:g} para «{mat['name']}».")
                        if forms.errors(errors):
                            continue
                        try:
                            repo.set_supplier_material(supplier_id, mat["id"], offered, available, price or None)
                        except Exception:
                            st.error("No se pudo actualizar este material. Revisa la conexión e inténtalo de nuevo.")
                            continue
                        ui.flash(f"Catálogo actualizado: {mat['name']}.", log=False)
                        st.rerun()


def _reset_search() -> None:
    st.session_state["sup_q"] = ""
    st.session_state["suppliers_directory_page"] = 1


def _reset_catalog_filters(supplier_id: str) -> None:
    st.session_state[f"cat_q_{supplier_id}"] = ""
    st.session_state[f"cat_state_{supplier_id}"] = ALL_CATALOG
    st.session_state[f"supplier_catalog_{supplier_id}_page"] = 1


def _remember_catalog_values(supplier_id: str, material_id: str) -> None:
    """Respaldo independiente de los widgets, que Streamlit retira al paginar."""
    key = f"_catalog_values_{supplier_id}"
    remembered = dict(st.session_state.get(key, {}))
    remembered[material_id] = {
        "available": bool(st.session_state.get(f"available_{supplier_id}_{material_id}", False)),
        "price": st.session_state.get(f"price_{supplier_id}_{material_id}", 0.0),
    }
    st.session_state[key] = remembered
