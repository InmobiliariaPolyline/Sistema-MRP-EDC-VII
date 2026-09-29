"""Punto de entrada de la app (Streamlit + Supabase)."""
import streamlit as st

from db.repository import USING_LOCAL
from pages_app import dashboard, login, materiales, ordenes, proveedores, reportes, usuarios

st.set_page_config(page_title="Sistema MRP", page_icon="📦", layout="wide")

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

MODULES = ["Dashboard", "Proveedores", "Materiales", "Órdenes de compra", "Reportes", "Usuarios"]

st.sidebar.title("Sistema MRP")
st.sidebar.caption(f"{user['name']} · {'Administrador' if user['role'] == 'admin' else 'Operador'}")
seccion = st.sidebar.radio("Módulo", MODULES)
st.sidebar.divider()
if st.sidebar.button("Cerrar sesión"):
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
