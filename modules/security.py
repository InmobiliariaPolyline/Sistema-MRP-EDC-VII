"""Seguridad de acceso: bloqueo por intentos fallidos, política de contraseñas y cambio de contraseña.

- **Bloqueo**: tras `MAX_ATTEMPTS` contraseñas incorrectas seguidas para un mismo usuario, ese usuario
  queda bloqueado `LOCK_SECONDS`. Se cuenta también por nombres que no existen (para no revelar cuáles
  usuarios existen). El registro vive en la memoria del servidor: frena la adivinanza de contraseñas
  en línea; al reiniciar la app se reinicia.
- **Política de contraseñas**: al menos 8 caracteres, con letras y números, distinta del usuario y
  de las más comunes. (bcrypt solo admite 72 bytes.)
- **Mi cuenta**: cada persona puede cambiar su contraseña con la actual."""
from __future__ import annotations

import time

import streamlit as st

from db import repository as repo
from db.auth import hash_password, verify_password
from modules import forms, ui

MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
MIN_LENGTH = 8
COMMON = {
    "12345678", "123456789", "1234567890", "password", "password1", "contraseña", "contrasena", "qwerty123",
    "11111111", "00000000", "abcd1234", "admin123", "admin1234", "prueba123", "iloveyou", "letmein1",
}


@st.cache_resource
def _registry() -> dict[str, dict]:
    """Usuario (normalizado) -> {"fails": int, "locked_until": float}."""
    return {}


def _key(username: str) -> str:
    return (username or "").strip().lower()


def lock_remaining(username: str, now: float | None = None, registry: dict | None = None) -> int:
    """Segundos que faltan para que el usuario pueda volver a intentar (0 = no está bloqueado)."""
    reg = _registry() if registry is None else registry
    entry = reg.get(_key(username))
    if not entry:
        return 0
    remaining = entry["locked_until"] - (time.time() if now is None else now)
    if remaining <= 0 and entry["locked_until"]:
        reg.pop(_key(username), None)  # el bloqueo venció: se empieza de cero
        return 0
    return max(int(remaining + 0.999), 0)


def register_failure(username: str, now: float | None = None, registry: dict | None = None) -> tuple[int, int]:
    """Anota un intento fallido. Devuelve (intentos que quedan, segundos de bloqueo si se acaba de bloquear)."""
    reg = _registry() if registry is None else registry
    current = time.time() if now is None else now
    entry = reg.setdefault(_key(username), {"fails": 0, "locked_until": 0.0})
    entry["fails"] += 1
    if entry["fails"] >= MAX_ATTEMPTS:
        entry["locked_until"] = current + LOCK_SECONDS
        entry["fails"] = 0
        return 0, LOCK_SECONDS
    return MAX_ATTEMPTS - entry["fails"], 0


def register_success(username: str, registry: dict | None = None) -> None:
    (_registry() if registry is None else registry).pop(_key(username), None)


def password_issues(password: str, username: str | None = None) -> list[str]:
    """Problemas de una contraseña nueva (lista vacía = válida)."""
    issues = []
    if not password or not password.strip():
        return ["Contraseña: completa este campo obligatorio."]
    if len(password) < MIN_LENGTH:
        issues.append(f"Contraseña: usa al menos {MIN_LENGTH} caracteres.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        issues.append("Contraseña: combina letras y números.")
    if password.lower() in COMMON:
        issues.append("Contraseña: es demasiado común; elige otra.")
    if username and password.lower() == username.strip().lower():
        issues.append("Contraseña: no puede ser igual al usuario.")
    if len(password.encode("utf-8")) > 72:
        issues.append("Contraseña: es demasiado larga (máximo 72 bytes; las tildes pueden ocupar más de uno).")
    return issues


def minutes(seconds: int) -> str:
    return f"{max(seconds // 60, 1)} min" if seconds >= 60 else f"{seconds} s"


@st.dialog("Mi cuenta")
def account_dialog(user: dict) -> None:
    """Cambio de contraseña de la persona que tiene la sesión iniciada."""
    forms.header("Cambiar mi contraseña", f"Sesión de {user['name']} (@{user['username']}). Usa una contraseña que no uses en otros sitios.")
    with st.form("change_password_form"):
        current = st.text_input("Contraseña actual", type="password", key="acct_current")
        new = st.text_input("Contraseña", type="password", key="acct_new", help="Al menos 8 caracteres, con letras y números.")
        again = st.text_input("Repetir contraseña", type="password", key="acct_again")
        cancel_col, save_col = st.columns([1, 2])
        save = save_col.form_submit_button("Cambiar contraseña", type="primary", width="stretch")
        cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
    if cancel:
        st.rerun()
    if not save:
        return

    wait = lock_remaining(user["username"])
    if wait:
        st.error(f"Demasiados intentos. Espera {minutes(wait)} para volver a intentarlo.")
        return
    record = repo.get_user_by_username(user["username"])
    if not record or not verify_password(current, record["password_hash"]):
        left, locked = register_failure(user["username"])
        st.error("La contraseña actual no es correcta." + (f" Te quedan {left} intento(s)." if left else f" Cuenta bloqueada {minutes(locked)}."))
        return
    issues = password_issues(new, user["username"])
    if new != again:
        issues.append("Repetir contraseña: ambas contraseñas deben coincidir.")
    if new == current:
        issues.append("Contraseña: la nueva debe ser distinta de la actual.")
    if forms.errors(issues):
        return
    try:
        repo.set_user_password(record["id"], hash_password(new))
    except Exception as exc:
        ui.db_error(exc, "No se pudo cambiar la contraseña. Inténtalo de nuevo.")
        return
    register_success(user["username"])
    ui.flash("Contraseña actualizada.", "🔑")
    st.rerun()
