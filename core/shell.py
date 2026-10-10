"""Cascarón de la app ya autenticada: aviso de modo local, la marca y el
menú del sidebar, y el ruteo hacia el módulo que el usuario eligió.

`app.py` solo decide SI se muestra esto (según haya sesión o no); qué se
muestra y cómo se navega entre pantallas vive acá, separado de cada módulo
en sí (que vive en `modules/`) y del acceso a datos (que vive en `db/`)."""
import streamlit as st

from core.version import APP_VERSION
from db.repository import USING_LOCAL
from modules import (
    asistencia, dashboard, historial, inventario, login, materiales, obras, ordenes, proveedores, reportes,
    trabajadores, ui,
)

# (etiqueta en el menú, icono, función que dibuja el módulo, solo-admin)
_ROUTES = [
    ("Dashboard", "📊", lambda user: dashboard.render(user), False),
    ("Proveedores", "🏭", lambda user: proveedores.render(), False),
    ("Materiales", "📦", lambda user: materiales.render(), False),
    ("Órdenes de compra", "🧾", lambda user: ordenes.render(), False),
    ("Inventario", "🏷️", lambda user: inventario.render(), False),
    ("Obras", "🏗️", lambda user: obras.render(), False),
    ("Asistencia", "📅", lambda user: asistencia.render(), False),
    ("Reportes", "📄", lambda user: reportes.render(), False),
    ("Trabajadores", "👷", lambda user: trabajadores.render(user), True),
    ("Historial", "🕘", lambda user: historial.render(), True),
]


def render(user: dict) -> None:
    """Dibuja el sidebar (marca + menú + cerrar sesión) y el módulo activo."""
    ui.show_flash()
    if USING_LOCAL:
        st.sidebar.info("Modo de prueba: los datos se guardan en este equipo.", icon="🧪")

    routes = [r for r in _ROUTES if user["role"] == "admin" or not r[3]]

    options = [route[0] for route in routes]
    if st.session_state.get("mrp_active_route") not in options:
        st.session_state["mrp_active_route"] = options[0]
    seccion = st.session_state["mrp_active_route"]
    with st.sidebar:
        _render_brand(user)
        with st.container(key="mrp_sidebar_navigation"):
            for label, icon, _, _ in routes:
                st.button(
                    label, icon=icon, key=f"mrp_nav_{label}", width="stretch",
                    type="primary" if label == seccion else "secondary",
                    on_click=_select_route, args=(label,),
                )
        st.divider()
        st.toggle("🌙 Modo oscuro", key="dark_mode")
        if st.button("Cerrar sesión", width="stretch"):
            login.logout()
            st.rerun()
        st.caption(f"Sistema MRP · {APP_VERSION}")

    render_fn = next(r[2] for r in routes if r[0] == seccion)
    render_fn(user)


def _select_route(label: str) -> None:
    st.session_state["mrp_active_route"] = label


def _render_brand(user: dict) -> None:
    st.markdown(
        '<div class="mrp-brand">'
        '<div class="mrp-brand-badge">📦</div>'
        '<div><div class="mrp-brand-name">Sistema MRP</div>'
        '<div class="mrp-brand-sub">Materiales y proveedores</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"{user['name']} · {'Administrador' if user['role'] == 'admin' else 'Operador'}")
    st.write("")
    st.markdown('<div class="mrp-sidebar-section">Espacio de trabajo</div>', unsafe_allow_html=True)
