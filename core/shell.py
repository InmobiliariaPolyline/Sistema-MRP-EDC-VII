"""Cascarón de la app ya autenticada: aviso de modo local, la marca y el
menú del sidebar, y el ruteo hacia el módulo que el usuario eligió.

`app.py` solo decide SI se muestra esto (según haya sesión o no); qué se
muestra y cómo se navega entre pantallas vive acá, separado de cada módulo
en sí (que vive en `modules/`) y del acceso a datos (que vive en `db/`)."""
import streamlit as st
from streamlit_option_menu import option_menu

from db.repository import USING_LOCAL
from modules import dashboard, login, materiales, ordenes, proveedores, reportes, trabajadores

# (etiqueta en el menú, ícono bootstrap, función que dibuja el módulo, solo-admin)
_ROUTES = [
    ("Dashboard", "speedometer2", lambda user: dashboard.render(user), False),
    ("Proveedores", "truck", lambda user: proveedores.render(), False),
    ("Materiales", "box-seam", lambda user: materiales.render(), False),
    ("Órdenes de compra", "cart3", lambda user: ordenes.render(), False),
    ("Reportes", "bar-chart-line", lambda user: reportes.render(), False),
    ("Trabajadores", "people", lambda user: trabajadores.render(user), True),
]


def render(user: dict) -> None:
    """Dibuja el sidebar (marca + menú + cerrar sesión) y el módulo activo."""
    if USING_LOCAL:
        st.sidebar.warning(
            "Modo local (sin Supabase): los datos se guardan en db/local.db, "
            "solo para probar la interfaz. Configura .env o .streamlit/secrets.toml "
            "para usar Supabase de verdad.",
            icon="⚠️",
        )

    routes = [r for r in _ROUTES if user["role"] == "admin" or not r[3]]

    with st.sidebar:
        _render_brand(user)
        seccion = option_menu(
            menu_title=None,
            options=[r[0] for r in routes],
            icons=[r[1] for r in routes],
            default_index=0,
            styles={
                "container": {"padding": "0", "background-color": "transparent"},
                "icon": {"font-size": "16px", "color": "#6B7280"},
                "nav-link": {
                    "font-size": "15px",
                    "text-align": "left",
                    "margin": "4px 0",
                    "border-radius": "10px",
                    "padding": "10px 14px",
                    "color": "#1F2333",
                },
                "nav-link-selected": {
                    "background-color": "#EFECFD",
                    "color": "#6C5CE7",
                    "font-weight": "700",
                    "icon-color": "#6C5CE7",
                },
            },
        )
        st.divider()
        if st.button("Cerrar sesión", use_container_width=True):
            login.logout()
            st.rerun()

    render_fn = next(r[2] for r in routes if r[0] == seccion)
    render_fn(user)


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
