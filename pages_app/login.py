"""Pantalla de acceso: login normal, o creación del primer administrador
cuando la tabla de usuarios está vacía (arranque en limpio del sistema)."""
import streamlit as st

from db import repository as repo
from db.auth import hash_password, verify_password

SESSION_KEY = "auth_user"


def is_logged_in() -> bool:
    return SESSION_KEY in st.session_state


def current_user() -> dict:
    return st.session_state[SESSION_KEY]


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)


def render() -> None:
    st.markdown(
        '<div class="mrp-brand" style="justify-content:center; margin: 40px 0 20px 0;">'
        '<div class="mrp-brand-badge" style="width:48px;height:48px;font-size:22px;">📦</div>'
        '<div><div class="mrp-brand-name" style="font-size:22px;">Sistema MRP</div>'
        '<div class="mrp-brand-sub">Materiales y proveedores</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.3, 1])
    with col:
        if repo.count_users() == 0:
            _render_bootstrap()
        else:
            _render_login()


def _render_login() -> None:
    with st.container(border=True):
        st.markdown('<div class="mrp-panel-title">Iniciar sesión</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)

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
    with st.container(border=True):
        st.markdown('<div class="mrp-panel-title">Crear administrador</div>', unsafe_allow_html=True)
        st.caption("Todavía no hay usuarios registrados. Esta cuenta quedará como Administrador.")
        with st.form("bootstrap_form"):
            name = st.text_input("Nombre completo")
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            password2 = st.text_input("Repetir contraseña", type="password")
            submitted = st.form_submit_button("Crear administrador", use_container_width=True)

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
