"""Punto de entrada de la app (Streamlit + Supabase)."""
import streamlit as st

from db.repository import USING_LOCAL
from pages_app import materiales, proveedores

st.set_page_config(page_title="Sistema MRP", page_icon="📦", layout="wide")

st.sidebar.title("Sistema MRP")
if USING_LOCAL:
    st.sidebar.warning(
        "Modo local (sin Supabase): los datos se guardan en db/local.db, "
        "solo para probar la interfaz. Configura .env o .streamlit/secrets.toml "
        "para usar Supabase de verdad.",
        icon="⚠️",
    )
seccion = st.sidebar.radio("Módulo", ["Proveedores", "Materiales"])

if seccion == "Proveedores":
    proveedores.render()
else:
    materiales.render()
