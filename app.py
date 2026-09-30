"""Punto de entrada de la app.

Streamlit no separa frontend y backend como Next.js/Express: es un solo
proceso Python que arma la página en cada interacción. Este archivo no es
"el frontend" — es apenas el arranque: configura la página, exige sesión
iniciada y le pasa el control a `core.shell`, que dibuja el sidebar y
decide qué módulo mostrar. Cada pantalla vive en `modules/`, y el acceso a
datos (Supabase o SQLite local) vive aparte en `db/`."""
import streamlit as st

from core import shell
from modules import login, ui

st.set_page_config(page_title="Sistema MRP", page_icon="📦", layout="wide")
ui.inject()

if not login.is_logged_in():
    login.render()
    st.stop()

shell.render(login.current_user())
