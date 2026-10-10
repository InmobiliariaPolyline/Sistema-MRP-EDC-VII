"""Pantalla de acceso: una animación de carga breve, seguida de un login
partido en dos paneles (marca a la izquierda, formulario a la derecha), o
la creación del primer administrador cuando la tabla de usuarios está
vacía (arranque en limpio del sistema)."""
import time

import streamlit as st

from db import repository as repo
from db.auth import hash_password, verify_password
from db.repository import USING_LOCAL
from modules import forms, session, ui

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
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) {
    min-height: 100dvh;
    align-items: stretch;
    gap: 0 !important;
}
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"] {
    padding: 0 !important;
}
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(1) {
    background: linear-gradient(160deg, #241457 0%, #4B2FD1 60%, #6C5CE7 100%);
    color: #EDEBFB;
    padding: 56px 48px !important;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) {
    background: var(--mrp-surface);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 48px !important;
}
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"] { min-height: auto; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1) {
        padding: 28px 22px !important;
        gap: 22px;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
        padding: 28px 22px !important;
    }
    .mrp-lp-headline { font-size: 26px; }
    .mrp-rp-status { margin-bottom: 24px; }
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
.mrp-rp-headline { font-size: 28px; font-weight: 800; color: var(--mrp-text); margin-bottom: 8px; }
.mrp-rp-copy { font-size: 14px; color: var(--mrp-muted); margin-bottom: 22px; line-height: 1.6; }
.mrp-rp-status-label { color: var(--mrp-muted); }
.mrp-rp-eyebrow { color: var(--mrp-accent); }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) > div { width: 100%; max-width: 430px; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stVerticalBlock"] { gap: .9rem !important; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) input { border: none !important; }

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
    session.forget()


def render() -> None:
    if not st.session_state.get(BOOTED_KEY):
        _render_boot()
        return

    st.markdown(_SHELL_CSS, unsafe_allow_html=True)
    left, right = st.columns([1, 1])

    with left:
        _render_brand_panel()

    with right:
        ui.show_flash()
        _render_status_line()
        if repo.count_users() == 0:
            _render_bootstrap()
        else:
            _render_login()


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
    steps = ["Preparando tu espacio de trabajo…", "Organizando la interfaz…", "Preparando el acceso…", "Todo listo."]
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
        username = st.text_input("Usuario", placeholder="Escribe tu usuario", help="Usa el usuario que te asignó el administrador.")
        password = st.text_input("Contraseña", type="password", placeholder="Escribe tu contraseña", help="Puedes mostrarla con el icono del ojo.")
        submitted = st.form_submit_button("Iniciar sesión  →", type="primary", width="stretch")
    with st.popover("¿Necesitas ayuda para ingresar?"):
        st.write("Escribe tu usuario y contraseña y pulsa «Iniciar sesión». Si no tienes acceso, solicita una cuenta al administrador de tu obra.")

    if not submitted:
        return

    issues = []
    if not username.strip():
        issues.append("Usuario: escribe tu usuario de acceso.")
    if not password:
        issues.append("Contraseña: escribe tu contraseña.")
    if forms.errors(issues):
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
    session.remember(user["username"])
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
        name = st.text_input("Nombre completo", placeholder="Ej. Ana Pérez", max_chars=forms.RULES["Nombre completo"]["max"])
        username = st.text_input("Usuario", placeholder="Ej. aperez", max_chars=forms.RULES["Usuario"]["max"], help="Letras sin tildes, números, punto, guion y guion bajo.")
        password = st.text_input("Contraseña", type="password", help="Al menos 6 caracteres.")
        password2 = st.text_input("Repetir contraseña", type="password", help="Escribe la misma contraseña para confirmar.")
        submitted = st.form_submit_button("Crear administrador  →", type="primary", width="stretch")

    if not submitted:
        return

    issues = forms.validate({"Nombre completo": name, "Usuario": username})
    if password != password2:
        issues.append("Repetir contraseña: ambas contraseñas deben coincidir.")
    if len(password) < 6:
        issues.append("Contraseña: escribe al menos 6 caracteres.")
    if len(password.encode("utf-8")) > 72:
        issues.append("Contraseña: es demasiado larga. Utiliza como máximo 72 bytes (las tildes pueden ocupar más de uno).")
    if forms.errors(issues):
        return

    repo.create_user(username.strip(), hash_password(password), name.strip(), "admin")
    ui.flash("Administrador creado. Ya puedes iniciar sesión.", log=False)
    st.rerun()
