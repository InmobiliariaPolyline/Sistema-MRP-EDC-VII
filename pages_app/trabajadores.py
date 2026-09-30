"""Módulo de Trabajadores (antes «Usuarios»): catálogo de personal de obra
—información personal, cuadrilla y obra donde trabajan, con su ubicación
en el mapa— y, cuando haga falta, el acceso al sistema (usuario/contraseña)
para quienes también deban entrar a administrarlo."""
import pandas as pd
import streamlit as st

from db import repository as repo
from db.auth import hash_password
from pages_app import ui
from utils.geocode import geocode_address

ROLES = ["operador", "admin"]
NO_GROUP = "Sin cuadrilla"
NO_SITE = "Sin obra asignada"


def render(user: dict) -> None:
    if user["role"] != "admin":
        ui.page_header("Trabajadores", "Trabajadores")
        st.error("Solo un administrador puede gestionar trabajadores.")
        return

    clicked = ui.page_header(
        "Personal de obra",
        "Trabajadores",
        "Información personal, cuadrilla y obra donde trabaja cada uno.",
        action_label="＋ Nuevo trabajador",
        action_key="new_worker_open",
    )
    if clicked:
        _new_worker_dialog()

    col1, col2 = st.columns(2)
    with col1:
        _render_groups_panel()
    with col2:
        _render_sites_panel()

    _render_workers_list()


# ---------------------------------------------------------------------------
# Cuadrillas y obras (catálogos de apoyo)
# ---------------------------------------------------------------------------

def _render_groups_panel() -> None:
    with st.expander("Cuadrillas"):
        with st.form("new_group_form", clear_on_submit=True):
            name = st.text_input("Nombre de la cuadrilla", placeholder="Ej. Electricistas")
            submitted = st.form_submit_button("Agregar", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                repo.create_work_group(name.strip())
                st.rerun()

        groups = repo.list_work_groups()
        if groups.empty:
            st.caption("Todavía no hay cuadrillas.")
        for row in groups.to_dict("records"):
            c1, c2 = st.columns([4, 1])
            c1.write(row["name"])
            if c2.button("🗑", key=f"del_group_{row['id']}", help="Eliminar cuadrilla"):
                repo.delete_work_group(row["id"])
                st.rerun()


def _render_sites_panel() -> None:
    with st.expander("Obras / Proyectos"):
        with st.form("new_site_form"):
            name = st.text_input("Nombre de la obra", placeholder="Ej. Torre Central")
            address = st.text_input("Dirección", placeholder="Calle, ciudad, país")
            c1, c2 = st.columns(2)
            search = c1.form_submit_button("🔍 Buscar dirección", use_container_width=True)
            save = c2.form_submit_button("Guardar obra", type="primary", use_container_width=True)

        if search:
            result = geocode_address(address)
            if result:
                st.session_state["_site_geocode"] = result
            else:
                st.session_state.pop("_site_geocode", None)
                st.warning("No se encontró esa dirección. Intenta ser más específico (ciudad, país).")

        geocode = st.session_state.get("_site_geocode")
        if geocode:
            st.caption(f"📍 {geocode['display_name']}")
            st.map(pd.DataFrame([{"lat": geocode["lat"], "lon": geocode["lon"]}]), zoom=14)

        if save:
            if not name.strip():
                st.error("El nombre de la obra es obligatorio.")
            else:
                geocode = st.session_state.get("_site_geocode")
                lat = geocode["lat"] if geocode else None
                lon = geocode["lon"] if geocode else None
                repo.create_project_site(name.strip(), address.strip() or None, lat, lon)
                st.session_state.pop("_site_geocode", None)
                st.rerun()

        sites = repo.list_project_sites()
        if sites.empty:
            st.caption("Todavía no hay obras registradas.")
        for row in sites.to_dict("records"):
            c1, c2 = st.columns([4, 1])
            c1.write(row["name"] + (" 📍" if row.get("latitude") else ""))
            if c2.button("🗑", key=f"del_site_{row['id']}", help="Eliminar obra"):
                repo.delete_project_site(row["id"])
                st.rerun()


# ---------------------------------------------------------------------------
# Alta de trabajador
# ---------------------------------------------------------------------------

@st.dialog("Registrar trabajador")
def _new_worker_dialog() -> None:
    full_name = st.text_input("Nombre completo")
    c1, c2 = st.columns(2)
    document_id = c1.text_input("Documento (opcional)")
    phone = c2.text_input("Teléfono")
    position = st.text_input("Puesto (opcional)", placeholder="Ej. Albañil, Operador de grúa")

    groups = repo.list_work_groups()
    group_choice = st.selectbox("Cuadrilla", [NO_GROUP] + groups["name"].tolist())

    sites = repo.list_project_sites()
    site_choice = st.selectbox("Obra / Proyecto", [NO_SITE] + sites["name"].tolist())

    grant_access = st.checkbox("Dar acceso al sistema (usuario y contraseña)")
    username = password = None
    role = "operador"
    if grant_access:
        c3, c4 = st.columns(2)
        username = c3.text_input("Usuario")
        password = c4.text_input("Contraseña", type="password")
        role = st.selectbox("Rol de acceso", ROLES)

    if st.button("Guardar", type="primary", use_container_width=True):
        if not full_name.strip():
            st.error("El nombre completo es obligatorio.")
            return
        if grant_access:
            if not username or not username.strip() or not password:
                st.error("Completa usuario y contraseña para dar acceso.")
                return
            if len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
                return
            if repo.get_user_by_username(username.strip()):
                st.error(f"Ya existe un usuario con el nombre «{username}».")
                return

        group_id = None
        if group_choice != NO_GROUP:
            group_id = groups.loc[groups["name"] == group_choice, "id"].iloc[0]
        site_id = None
        if site_choice != NO_SITE:
            site_id = sites.loc[sites["name"] == site_choice, "id"].iloc[0]

        worker_id = repo.create_worker(
            full_name.strip(), document_id.strip() or None, phone.strip() or None, position.strip() or None, group_id, site_id
        )
        if grant_access:
            repo.grant_worker_access(worker_id, username.strip(), hash_password(password), full_name.strip(), role)

        st.success(f"Trabajador «{full_name}» registrado.")
        st.rerun()


@st.dialog("Dar acceso al sistema")
def _grant_access_dialog(worker: dict) -> None:
    st.caption(f"Para {worker['full_name']}")
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    role = st.selectbox("Rol de acceso", ROLES)
    if st.button("Dar acceso", type="primary", use_container_width=True):
        if not username.strip() or not password:
            st.error("Completa usuario y contraseña.")
            return
        if len(password) < 6:
            st.error("La contraseña debe tener al menos 6 caracteres.")
            return
        if repo.get_user_by_username(username.strip()):
            st.error(f"Ya existe un usuario con el nombre «{username}».")
            return
        repo.grant_worker_access(worker["id"], username.strip(), hash_password(password), worker["full_name"], role)
        st.success("Acceso creado.")
        st.rerun()


# ---------------------------------------------------------------------------
# Directorio
# ---------------------------------------------------------------------------

def _render_workers_list() -> None:
    st.markdown('<div class="mrp-eyebrow">Directorio</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Trabajadores registrados</div>', unsafe_allow_html=True)

    df = repo.list_workers()
    if df.empty:
        st.info("Todavía no hay trabajadores registrados. Usa «＋ Nuevo trabajador» arriba para crear el primero.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 2, 3, 1])
            with c1:
                sub = row.get("document_id") or row.get("phone") or "Sin datos de contacto"
                st.markdown(ui.row_name_sub(ui.avatar(row["full_name"]), row["full_name"], sub), unsafe_allow_html=True)
            with c2:
                pills = ui.pill(row.get("group_name") or "Sin cuadrilla", "purple")
                pills += " " + ui.pill(row.get("site_name") or "Sin obra", "gray")
                st.markdown(pills, unsafe_allow_html=True)
            with c3:
                if row.get("user_id"):
                    if st.button("Quitar acceso", key=f"revoke_{row['id']}", use_container_width=True):
                        repo.revoke_worker_access(row["id"], row["user_id"])
                        st.rerun()
                else:
                    if st.button("Dar acceso", key=f"grant_{row['id']}", use_container_width=True):
                        _grant_access_dialog(row)
            with c4:
                if st.button("🗑", key=f"del_worker_{row['id']}", help="Eliminar trabajador"):
                    repo.delete_worker(row["id"])
                    st.rerun()

            if row.get("username"):
                st.caption(f"Acceso al sistema: @{row['username']} ({row.get('role') or 'operador'})")

            if row.get("latitude") and row.get("longitude"):
                with st.expander(f"📍 Ubicación — {row.get('site_name') or ''}"):
                    if row.get("site_address"):
                        st.caption(row["site_address"])
                    st.map(pd.DataFrame([{"lat": row["latitude"], "lon": row["longitude"]}]), zoom=13)
