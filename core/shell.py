"""Cascarón de la app ya autenticada: aviso de modo local, la marca y el
menú del sidebar, y el ruteo hacia el módulo que el usuario eligió.

`app.py` solo decide SI se muestra esto (según haya sesión o no); qué se
muestra y cómo se navega entre pantallas vive acá, separado de cada módulo
en sí (que vive en `modules/`) y del acceso a datos (que vive en `db/`)."""
import html

import streamlit as st

from core.version import APP_VERSION
from db.client import using_service_key
from db.repository import USING_LOCAL
from utils import icons
from modules import (
    asistencia, dashboard, historial, inventario, login, manual_Usuario, materiales, obras, ordenes, proveedores, reportes,
    respaldo, security, sistema, trabajadores, ui,
)

# (etiqueta en el menú, icono Material, función que dibuja el módulo, solo-admin)
_ROUTES = [
    ("Dashboard", ":material/space_dashboard:", lambda user: dashboard.render(user), False),
    ("Órdenes de compra", ":material/receipt_long:", lambda user: ordenes.render(), False),
    ("Proveedores", ":material/local_shipping:", lambda user: proveedores.render(), False),
    ("Materiales", ":material/category:", lambda user: materiales.render(), False),
    ("Inventario", ":material/inventory_2:", lambda user: inventario.render(), False),
    ("Obras", ":material/apartment:", lambda user: obras.render(), False),
    ("Asistencia", ":material/event_available:", lambda user: asistencia.render(), False),
    ("Trabajadores", ":material/engineering:", lambda user: trabajadores.render(user), True),
    ("Reportes", ":material/monitoring:", lambda user: reportes.render(), False),
    ("Manual de Usuario", ":material/menu_book:", lambda user: manual_Usuario.show(), False),
    ("Historial", ":material/history:", lambda user: historial.render(), True),
    ("Respaldo", ":material/backup:", lambda user: respaldo.render(), True),
    ("Sistema", ":material/info:", lambda user: sistema.render(), False),
]

# secciones del menú, en el orden en que se muestran
_GROUPS = [
    ("Resumen", ["Dashboard"]),
    ("Compras y almacén", ["Órdenes de compra", "Proveedores", "Materiales", "Inventario"]),
    ("Obra y personal", ["Obras", "Asistencia", "Trabajadores"]),
    ("Análisis", ["Reportes", "Historial", "Respaldo"]),
    ("Sistema", ["Sistema", "Manual de Usuario"]),
]


def render(user: dict) -> None:
    """Dibuja el sidebar (marca + menú + cerrar sesión) y el módulo activo."""
    ui.show_flash()
    if USING_LOCAL:
        st.sidebar.info("Modo de prueba: los datos se guardan en este equipo.", icon=":material/science:")

    if not USING_LOCAL and not using_service_key():
        st.sidebar.warning(
            "La base está en **modo abierto**: cualquiera con la clave pública podría leer o cambiar los datos. "
            "Configura SUPABASE_SERVICE_KEY y cierra la base (db/migrations/040_cerrar_base.sql).",
            icon=":material/lock_open:",
        )

    routes = {r[0]: r for r in _ROUTES if user["role"] == "admin" or not r[3]}

    options = list(routes)
    if st.session_state.get("mrp_active_route") not in options:
        st.session_state["mrp_active_route"] = options[0]
    seccion = st.session_state["mrp_active_route"]
    with st.sidebar:
        _render_brand(user)
        with st.container(key="mrp_sidebar_navigation"):
            for group, labels in _GROUPS:
                visible = [label for label in labels if label in routes]
                if not visible:
                    continue
                st.markdown(f'<div class="mrp-sidebar-section">{html.escape(group)}</div>', unsafe_allow_html=True)
                for label in visible:
                    st.button(
                        label, icon=routes[label][1], key=f"mrp_nav_{label}", width="stretch",
                        type="primary" if label == seccion else "secondary",
                        on_click=_select_route, args=(label,),
                    )
        st.divider()
        if st.button("Mi cuenta", icon=":material/manage_accounts:", width="stretch", help="Cambia tu contraseña."):
            security.lock_company()
            security.account_dialog(user)
        if st.button("Actualizar datos", icon=":material/refresh:", width="stretch", help="Vuelve a leer todo de la base. Úsalo si otra persona acaba de hacer cambios (los datos se guardan unos segundos en memoria para ir más rápido)."):
            st.cache_data.clear()
            st.rerun()
        st.toggle("Modo oscuro", key="dark_mode", help="Cambia entre el tema claro y el oscuro.")
        if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
            login.logout()
            st.rerun()
        st.caption(f"Sistema MRP · {APP_VERSION}")

    routes[seccion][2](user)


def _select_route(label: str) -> None:
    st.session_state["mrp_active_route"] = label
    st.session_state["_mrp_nav"] = st.session_state.get("_mrp_nav", 0) + 1


def _render_brand(user: dict) -> None:
    role = "Administrador" if user["role"] == "admin" else "Operador"
    name = html.escape(user["name"])
    st.markdown(
        '<div class="mrp-brand">'
        f'<div class="mrp-brand-badge">{icons.brand_mark(26, animated=True)}</div>'
        '<div><div class="mrp-brand-name">Sistema MRP</div>'
        '<div class="mrp-brand-sub">Materiales y proveedores</div></div>'
        "</div>"
        '<div class="mrp-usercard">'
        f'{ui.avatar(user["name"])}'
        f'<div><div class="mrp-usercard-name">{name}</div><div class="mrp-usercard-role">{role}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )