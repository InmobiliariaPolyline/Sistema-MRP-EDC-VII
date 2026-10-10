"""Punto de entrada de la app.

Streamlit no separa frontend y backend como Next.js/Express: es un solo
proceso Python que arma la página en cada interacción. Este archivo no es
"el frontend" — es apenas el arranque: configura la página, reabre la sesión
si el navegador la recuerda, exige sesión iniciada y le pasa el control a
`core.shell`, que dibuja el sidebar y decide qué módulo mostrar. Cada
pantalla vive en `modules/`, y el acceso a datos (Supabase o SQLite local)
vive aparte en `db/`."""
import streamlit as st

from core import shell
from modules import live_validation, login, session, ui

st.set_page_config(
    page_title="Sistema MRP",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get help": None, "Report a bug": None, "About": "Sistema MRP · materiales, proveedores y compras de obra."},
)
ui.inject()

try:
    session.restore()
    session.flush_cookie()

    if not login.is_logged_in():
        login.render()
        live_validation.inject()
        st.stop()

    shell.render(login.current_user())
    live_validation.inject()
except st.errors.StreamlitAPIException:
    raise  # st.stop()/st.rerun() y errores de uso de Streamlit siguen su curso normal
except Exception as exc:  # fallo de red/base de datos: mensaje claro en vez del traceback
    if type(exc).__name__ in ("StopException", "RerunException"):
        raise
    st.error("No se pudo completar esta operación. Revisa la conexión y vuelve a intentarlo.")
    with st.expander("Detalle del error para solicitar ayuda"):
        st.caption(f"{type(exc).__name__}: {exc}")
    if st.button("Reintentar", type="primary"):
        st.rerun()
