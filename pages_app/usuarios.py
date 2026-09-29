"""Módulo de Usuarios: solo para administradores. Alta de cuentas y
activar/desactivar/eliminar acceso."""
import streamlit as st

from db import repository as repo
from db.auth import hash_password
from pages_app import ui

ROLES = ["operador", "admin"]


def render(user: dict) -> None:
    if user["role"] != "admin":
        ui.page_header("Usuarios", "Usuarios")
        st.error("Solo un administrador puede gestionar usuarios.")
        return

    ui.page_header("Cuentas", "Usuarios", "Quién tiene acceso al sistema y con qué rol.")

    _render_form(user)
    _render_table(user)


def _render_form(current_user: dict) -> None:
    with st.container(border=True):
        ui.panel_header("Nuevo registro", "Crear usuario")
        with st.form("new_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre completo")
            username = c2.text_input("Usuario")
            c3, c4 = st.columns(2)
            password = c3.text_input("Contraseña", type="password")
            role = c4.selectbox("Rol", ROLES)
            submitted = st.form_submit_button("Crear", use_container_width=True)

        if submitted:
            if not name.strip() or not username.strip() or not password:
                st.error("Completa todos los campos.")
            elif len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            elif repo.get_user_by_username(username.strip()):
                st.error(f"Ya existe un usuario con el nombre «{username}».")
            else:
                repo.create_user(username.strip(), hash_password(password), name.strip(), role)
                st.success(f"Usuario «{username}» creado.")
                st.rerun()
    st.write("")


def _render_table(current_user: dict) -> None:
    st.markdown('<div class="mrp-eyebrow">Directorio</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Usuarios registrados</div>', unsafe_allow_html=True)

    df = repo.list_users()
    if df.empty:
        st.info("No hay usuarios.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 2, 3, 1])
            with c1:
                st.markdown(ui.row_name_sub(ui.avatar(row["name"]), row["name"], f"@{row['username']}"), unsafe_allow_html=True)
            with c2:
                role_pill = ui.pill("Administrador", "purple") if row["role"] == "admin" else ui.pill("Operador", "gray")
                status_pill = ui.pill("Activo", "green") if row["active"] else ui.pill("Inactivo", "red")
                st.markdown(f"{role_pill} &nbsp; {status_pill}", unsafe_allow_html=True)
            is_self = row["id"] == current_user["id"]
            with c3:
                toggle_label = "Desactivar" if row["active"] else "Activar"
                if st.button(toggle_label, key=f"toggle_{row['id']}", disabled=is_self, use_container_width=True):
                    repo.set_user_active(row["id"], not row["active"])
                    st.rerun()
            with c4:
                if st.button("🗑", key=f"del_user_{row['id']}", disabled=is_self, help="Eliminar usuario"):
                    repo.delete_user(row["id"])
                    st.rerun()
            if is_self:
                st.caption("Esta es tu propia cuenta: no puedes desactivarla ni eliminarla desde aquí.")
