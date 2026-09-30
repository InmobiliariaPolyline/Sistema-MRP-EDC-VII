"""Pantalla de acceso: una animación de carga breve, seguida de un login
partido en dos paneles (marca a la izquierda, formulario a la derecha), o
la creación del primer administrador cuando la tabla de usuarios está
vacía (arranque en limpio del sistema)."""
import time

import streamlit as st

from db import repository as repo
from db.auth import hash_password, verify_password
from db.repository import USING_LOCAL

SESSION_KEY = "auth_user"
BOOTED_KEY = "_mrp_booted"

_SHELL_CSS = """
<style>
#MainMenu, header, footer, div[data-testid="stHeader"] {
    visibility: hidden;
    height: 0 !important;
    min-height: 0 !important;
}
section[data-testid="stSidebar"] { display: none; }
div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
div[data-testid="stMainBlockContainer"] {
    padding: 0 !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] { gap: 0 !important; }
div[data-testid="stElementContainer"] { margin: 0 !important; }
div[data-testid="stHorizontalBlock"] {
    min-height: 100vh;
    align-items: stretch;
    gap: 0 !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    padding: 0 !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1) {
    background: linear-gradient(160deg, #241457 0%, #4B2FD1 60%, #6C5CE7 100%);
    color: #EDEBFB;
    padding: 56px 48px !important;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
    background: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 48px !important;
}
.mrp-lp-brand { display: flex; align-items: center; gap: 12px; }
.mrp-lp-brand-badge {
    width: 40px; height: 40px; border-radius: 10px;
    background: rgba(255,255,255,0.12);
    display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.mrp-lp-brand-name { font-weight: 800; letter-spacing: 0.04em; font-size: 14px; }
.mrp-lp-eyebrow {
    font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
    color: #C9C2F7; margin-bottom: 10px;
}
.mrp-lp-headline { font-size: 34px; font-weight: 800; line-height: 1.25; color: #FFFFFF; margin-bottom: 14px; }
.mrp-lp-copy { font-size: 14px; color: #D6D1F5; line-height: 1.5; max-width: 380px; }
.mrp-lp-divider { border-top: 1px solid rgba(255,255,255,0.18); margin: 28px 0 20px 0; }
.mrp-lp-stat-value { font-size: 32px; font-weight: 800; color: #FFFFFF; }
.mrp-lp-stat-label { font-size: 13px; color: #C9C2F7; }

.mrp-rp-inner { width: 100%; max-width: 360px; }
.mrp-rp-status { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }
.mrp-rp-status-label { font-size: 12px; color: #9095A6; }
.mrp-rp-status-dot { font-size: 12px; font-weight: 700; }
.mrp-rp-eyebrow {
    font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
    color: #6C5CE7; margin-bottom: 8px;
}
.mrp-rp-headline { font-size: 26px; font-weight: 800; color: #1F2333; margin-bottom: 8px; }
.mrp-rp-copy { font-size: 13.5px; color: #6B7280; margin-bottom: 28px; line-height: 1.5; }

div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) .stTextInput input {
    border-radius: 10px;
    border: 1px solid rgba(17,24,39,0.12);
    padding: 10px 14px;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) .stButton button,
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) .stFormSubmitButton button {
    background: linear-gradient(135deg, #6C5CE7, #4B2FD1);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    padding: 10px 0;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) .stButton button:hover,
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) .stFormSubmitButton button:hover {
    filter: brightness(1.08);
    color: white;
}
</style>
"""

_BOOT_CSS = """
<style>
#MainMenu, header, footer, div[data-testid="stHeader"] {
    visibility: hidden;
    height: 0 !important;
    min-height: 0 !important;
}
section[data-testid="stSidebar"] { display: none; }
div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
div[data-testid="stVerticalBlock"] { gap: 0 !important; }
div[data-testid="stElementContainer"] { margin: 0 !important; }
div[data-testid="stMainBlockContainer"] {
    padding: 0 !important;
    max-width: 100% !important;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(160deg, #241457 0%, #4B2FD1 60%, #6C5CE7 100%);
}
div[data-testid="stMainBlockContainer"] > div { width: 100%; max-width: 360px; }
.mrp-boot-badge {
    width: 64px; height: 64px; margin: 0 auto 18px auto; border-radius: 16px;
    background: rgba(255,255,255,0.12);
    display: flex; align-items: center; justify-content: center; font-size: 30px;
}
.mrp-boot-title {
    text-align: center; color: #FFFFFF; font-weight: 800; font-size: 18px;
    letter-spacing: 0.06em; margin-bottom: 2px;
}
.mrp-boot-sub { text-align: center; color: #C9C2F7; font-size: 12.5px; margin-bottom: 26px; }
.mrp-boot-status { text-align: center; color: #D6D1F5; font-size: 12.5px; margin-top: 10px; }
div[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #C9C2F7, #FFFFFF);
}
</style>
"""


def is_logged_in() -> bool:
    return SESSION_KEY in st.session_state


def current_user() -> dict:
    return st.session_state[SESSION_KEY]


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)


def render() -> None:
    if not st.session_state.get(BOOTED_KEY):
        _render_boot()
        return

    st.markdown(_SHELL_CSS, unsafe_allow_html=True)
    left, right = st.columns([1, 1])

    with left:
        _render_brand_panel()

    with right:
        st.markdown('<div class="mrp-rp-inner">', unsafe_allow_html=True)
        _render_status_line()
        if repo.count_users() == 0:
            _render_bootstrap()
        else:
            _render_login()
        st.markdown("</div>", unsafe_allow_html=True)


def _render_boot() -> None:
    st.markdown(_BOOT_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="mrp-boot-badge">📦</div>'
        '<div class="mrp-boot-title">SISTEMA MRP</div>'
        '<div class="mrp-boot-sub">Materiales y proveedores</div>',
        unsafe_allow_html=True,
    )
    progress = st.progress(0)
    status = st.empty()
    steps = ["Conectando con la base de datos...", "Cargando catálogo...", "Verificando sesión...", "Todo listo."]
    for i in range(100):
        time.sleep(0.009)
        progress.progress(i + 1)
        status.markdown(f'<div class="mrp-boot-status">{steps[min(i // 25, len(steps) - 1)]}</div>', unsafe_allow_html=True)
    st.session_state[BOOTED_KEY] = True
    st.rerun()


def _render_brand_panel() -> None:
    try:
        suppliers_count = len(repo.list_suppliers())
    except Exception:
        suppliers_count = None

    stat_html = ""
    if suppliers_count is not None:
        noun = "proveedor" if suppliers_count == 1 else "proveedores"
        stat_html = (
            '<div>'
            f'<div class="mrp-lp-stat-value">{suppliers_count}</div>'
            f'<div class="mrp-lp-stat-label">{noun} registrados</div>'
            "</div>"
        )

    st.markdown(
        '<div class="mrp-lp-brand">'
        '<div class="mrp-lp-brand-badge">📦</div>'
        '<div class="mrp-lp-brand-name">SISTEMA MRP</div>'
        "</div>"
        "<div>"
        '<div class="mrp-lp-eyebrow">Control de materiales</div>'
        '<div class="mrp-lp-headline">Cada material, con<br/>un proveedor claro.</div>'
        '<div class="mrp-lp-copy">Consulta el catálogo, contacta proveedores y mantén '
        "la disponibilidad al día desde un solo panel.</div>"
        "</div>"
        '<div>'
        '<div class="mrp-lp-divider"></div>'
        f"{stat_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_status_line() -> None:
    if USING_LOCAL:
        label, color = "Modo local (SQLite)", "#D68A0C"
    else:
        label, color = "Conectado a Supabase", "#1F9254"
    st.markdown(
        '<div class="mrp-rp-status">'
        '<div class="mrp-rp-status-label">Acceso al sistema</div>'
        f'<div class="mrp-rp-status-dot" style="color:{color};">● {label}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_login() -> None:
    st.markdown(
        '<div class="mrp-rp-eyebrow">Bienvenido</div>'
        '<div class="mrp-rp-headline">Inicia sesión para continuar.</div>'
        '<div class="mrp-rp-copy">Entra con tu usuario y contraseña para gestionar '
        "materiales y proveedores.</div>",
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar  →", use_container_width=True)

    if not submitted:
        return

    user = repo.get_user_by_username(username.strip())
    if not user or not user.get("active", True) or not verify_password(password, user["password_hash"]):
        st.error("Usuario o contraseña incorrectos.")
        return

    st.session_state[SESSION_KEY] = {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
    }
    st.rerun()


def _render_bootstrap() -> None:
    st.markdown(
        '<div class="mrp-rp-eyebrow">Primer acceso</div>'
        '<div class="mrp-rp-headline">Crea el administrador.</div>'
        '<div class="mrp-rp-copy">Todavía no hay usuarios registrados; esta cuenta '
        "quedará como Administrador del sistema.</div>",
        unsafe_allow_html=True,
    )
    with st.form("bootstrap_form"):
        name = st.text_input("Nombre completo")
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        password2 = st.text_input("Repetir contraseña", type="password")
        submitted = st.form_submit_button("Crear administrador  →", use_container_width=True)

    if not submitted:
        return

    if not name.strip() or not username.strip() or not password:
        st.error("Completa todos los campos.")
        return
    if password != password2:
        st.error("Las contraseñas no coinciden.")
        return
    if len(password) < 6:
        st.error("La contraseña debe tener al menos 6 caracteres.")
        return

    repo.create_user(username.strip(), hash_password(password), name.strip(), "admin")
    st.success("Administrador creado. Ya puedes iniciar sesión.")
    st.rerun()
