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


UNLOCK_KEY = "_company_unlocked_until"
UNLOCK_SECONDS = 180
COMPANY_LABELS = {"legal_name": "Razón social", "trade_name": "Nombre comercial", "ruc": "RUC", "fiscal_address": "Dirección fiscal"}


def _rerun_dialog() -> None:
    """Redibuja solo el diálogo (sin cerrarlo). Si se llama fuera de una recarga del fragmento, redibuja todo."""
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        st.rerun()


def lock_company() -> None:
    """Vuelve a ocultar los datos de la empresa (se llama al abrir «Mi cuenta» y al pulsar «Ocultar»)."""
    st.session_state.pop(UNLOCK_KEY, None)


def company_unlocked(now: float | None = None) -> bool:
    """¿Se ingresó la contraseña hace menos de `UNLOCK_SECONDS`?"""
    return (time.time() if now is None else now) < float(st.session_state.get(UNLOCK_KEY, 0))


def check_password(user: dict, password: str) -> tuple[bool, str]:
    """Comprueba la contraseña de la persona con sesión iniciada, con el mismo bloqueo por intentos que el inicio de sesión.
    Devuelve (¿es correcta?, mensaje de error si no lo es)."""
    wait = lock_remaining(user["username"])
    if wait:
        return False, f"Demasiados intentos. Espera {minutes(wait)} para volver a intentarlo."
    record = repo.get_user_by_username(user["username"])
    if not record or not verify_password(password, record["password_hash"]):
        left, locked = register_failure(user["username"])
        return False, "La contraseña no es correcta." + (f" Te quedan {left} intento(s)." if left else f" Cuenta bloqueada {minutes(locked)}.")
    register_success(user["username"])
    return True, ""


def _password_tab(user: dict) -> None:
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
    ok, message = check_password(user, current)
    if not ok:
        st.error(message)
        return
    record = repo.get_user_by_username(user["username"])
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
    ui.flash("Contraseña actualizada.", "🔑")
    st.rerun()


def _company_tab(user: dict) -> None:
    """Datos de facturación de la empresa. El RUC solo se muestra después de ingresar la contraseña de la sesión."""
    forms.header(
        "Datos de la empresa",
        "Razón social y RUC con los que se hacen las compras. El sistema no paga nada: estos datos salen en las órdenes de compra para que el proveedor facture a la empresa.",
    )
    if not company_unlocked():
        lock_company()
        st.info("Por seguridad, ingresa tu contraseña para ver o cambiar el RUC.", icon=":material/lock:")
        with st.form("company_unlock_form"):
            password = st.text_input("Tu contraseña", type="password", key="acct_company_pw")
            go = st.form_submit_button("Mostrar datos de la empresa", type="primary", width="stretch")
        if go:
            ok, message = check_password(user, password)
            if not ok:
                st.error(message)
                return
            st.session_state[UNLOCK_KEY] = time.time() + UNLOCK_SECONDS
            _rerun_dialog()
        return

    from utils import ruc as ruc_rules

    company = repo.get_company()
    left = max(int(float(st.session_state[UNLOCK_KEY]) - time.time()), 0)
    top, hide = st.columns([4, 1.4], vertical_alignment="center")
    top.caption(f"Visible durante {minutes(left)} más; después se vuelve a ocultar.")
    if hide.button("Ocultar", key="company_hide", width="stretch", icon=":material/visibility_off:"):
        lock_company()
        _rerun_dialog()
    with st.form("company_form"):
        legal = st.text_input("Razón social", value=company.get("legal_name") or "", placeholder="Ej. Constructora Andina S.A.C.", max_chars=160)
        trade = st.text_input("Nombre comercial (opcional)", value=company.get("trade_name") or "", max_chars=160)
        ruc_value = st.text_input("RUC", value=company.get("ruc") or "", placeholder="11 dígitos, ej. 20131312955", max_chars=14,
                                  help="Debe tener 11 dígitos y empezar con 20 (empresa) o 10 (persona natural con negocio).")
        address = st.text_input("Dirección fiscal (opcional)", value=company.get("fiscal_address") or "", max_chars=240)
        save = st.form_submit_button("Guardar datos de la empresa", type="primary", width="stretch")
    kind = ruc_rules.kind(company.get("ruc"))
    if company.get("ruc"):
        st.caption(f"RUC guardado: {company['ruc']}" + (f" · {kind}" if kind else "") + (f" · actualizado por {company['updated_by']}" if company.get("updated_by") else ""))
    if not save:
        return
    issues = ruc_rules.issues(ruc_value, "RUC", required=True)
    if not legal.strip():
        issues.insert(0, "Razón social: completa este campo obligatorio.")
    if forms.errors(issues):
        return
    new = {"legal_name": legal.strip(), "trade_name": trade.strip() or None, "ruc": ruc_rules.clean(ruc_value), "fiscal_address": address.strip() or None}
    try:
        repo.set_company(legal, trade, ruc_value, address, ui.current_actor())
    except ValueError as exc:
        st.error(str(exc))
        return
    from utils import audit

    changed = [k for k in COMPANY_LABELS if (company.get(k) or None) != (new.get(k) or None)]
    # el RUC no se escribe en el historial (se ve sin contraseña): solo se anota que cambió
    changes = [
        {"field": COMPANY_LABELS[k], "before": "(oculto)" if k == "ruc" else audit.fmt(company.get(k)), "after": "(oculto)" if k == "ruc" else audit.fmt(new.get(k))}
        for k in changed
    ]
    ui.log_change("Datos de la empresa editados", "empresa", None, changes, icon="🏢")
    if not changes:
        st.toast("Sin cambios.", icon="ℹ️")
    _rerun_dialog()


@st.dialog("Mi cuenta", width="large")
def account_dialog(user: dict) -> None:
    """Mi cuenta: cambio de contraseña y, para el administrador, los datos de la empresa (RUC) tras confirmar la contraseña."""
    if user.get("role") == "admin":
        tab_password, tab_company = st.tabs(["Contraseña", "Empresa y RUC"])
        with tab_password:
            _password_tab(user)
        with tab_company:
            _company_tab(user)
    else:
        _password_tab(user)
