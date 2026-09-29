"""Punto de entrada de la app (Streamlit + Supabase)."""
import streamlit as st
from streamlit_option_menu import option_menu

from db.repository import USING_LOCAL
from pages_app import dashboard, login, materiales, ordenes, proveedores, reportes, ui, usuarios

st.set_page_config(page_title="Sistema MRP", page_icon="📦", layout="wide")
ui.inject()

if USING_LOCAL:
    st.sidebar.warning(
        "Modo local (sin Supabase): los datos se guardan en db/local.db, "
        "solo para probar la interfaz. Configura .env o .streamlit/secrets.toml "
        "para usar Supabase de verdad.",
        icon="⚠️",
    )

if not login.is_logged_in():
    login.render()
    st.stop()

user = login.current_user()

MODULES = [
    ("Dashboard", "speedometer2"),
    ("Proveedores", "truck"),
    ("Materiales", "box-seam"),
    ("Órdenes de compra", "cart3"),
    ("Reportes", "bar-chart-line"),
]
if user["role"] == "admin":
    MODULES.append(("Usuarios", "people"))

with st.sidebar:
    st.markdown("### 📦 Sistema MRP")
    st.caption(f"{user['name']} · {'Administrador' if user['role'] == 'admin' else 'Operador'}")

    seccion = option_menu(
        menu_title=None,
        options=[m[0] for m in MODULES],
        icons=[m[1] for m in MODULES],
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": "transparent"},
            "icon": {"font-size": "16px"},
            "nav-link": {
                "font-size": "15px",
                "text-align": "left",
                "margin": "4px 0",
                "border-radius": "10px",
                "padding": "10px 14px",
            },
            "nav-link-selected": {"background-color": "#2F80ED"},
        },
    )

    st.divider()
    if st.button("Cerrar sesión", use_container_width=True):
        login.logout()
        st.rerun()

if seccion == "Dashboard":
    dashboard.render(user)
elif seccion == "Proveedores":
    proveedores.render()
elif seccion == "Materiales":
    materiales.render()
elif seccion == "Órdenes de compra":
    ordenes.render()
elif seccion == "Reportes":
    reportes.render()
elif seccion == "Usuarios":
    usuarios.render(user)
