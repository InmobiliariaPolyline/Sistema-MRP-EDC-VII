"""Módulo de Usuarios: solo para administradores. Alta de cuentas y
activar/desactivar/eliminar acceso."""
import streamlit as st

from db import repository as repo
from db.auth import hash_password

ROLES = ["operador", "admin"]


def render(user: dict) -> None:
    st.header("Usuarios")

    if user["role"] != "admin":
        st.error("Solo un administrador puede gestionar usuarios.")
        return

    st.caption("Cuentas con acceso al sistema.")

    _render_form(user)
    st.divider()
    _render_table(user)


def _render_form(current_user: dict) -> None:
    st.subheader("Crear usuario")
    with st.form("new_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre completo")
        username = c2.text_input("Usuario")
        c3, c4 = st.columns(2)
        password = c3.text_input("Contraseña", type="password")
        role = c4.selectbox("Rol", ROLES)
        submitted = st.form_submit_button("Crear")

    if not submitted:
        return

    if not name.strip() or not username.strip() or not password:
        st.error("Completa todos los campos.")
        return
    if len(password) < 6:
        st.error("La contraseña debe tener al menos 6 caracteres.")
        return
    if repo.get_user_by_username(username.strip()):
        st.error(f"Ya existe un usuario con el nombre «{username}».")
        return

    repo.create_user(username.strip(), hash_password(password), name.strip(), role)
    st.success(f"Usuario «{username}» creado.")
    st.rerun()


def _render_table(current_user: dict) -> None:
    st.subheader("Usuarios registrados")
    df = repo.list_users()
    if df.empty:
        st.info("No hay usuarios.")
        return

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"**{row['name']}** (@{row['username']})")
            c2.write("Administrador" if row["role"] == "admin" else "Operador")
            c3.write("Activo ✅" if row["active"] else "Inactivo ⛔")
            is_self = row["id"] == current_user["id"]
            with c4:
                cc1, cc2 = st.columns(2)
                toggle_label = "Desactivar" if row["active"] else "Activar"
                if cc1.button(toggle_label, key=f"toggle_{row['id']}", disabled=is_self):
                    repo.set_user_active(row["id"], not row["active"])
                    st.rerun()
                if cc2.button("Eliminar", key=f"del_user_{row['id']}", disabled=is_self):
                    repo.delete_user(row["id"])
                    st.rerun()
            if is_self:
                st.caption("Esta es tu propia cuenta: no puedes desactivarla ni eliminarla desde aquí.")
