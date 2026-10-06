"""Sesión que sobrevive a recargar la página.

Al iniciar sesión se guarda en el navegador una cookie con un token firmado
(HMAC) que contiene el usuario y su vencimiento. Al recargar, `restore()` lo
lee del lado del servidor (`st.context.cookies`), verifica la firma y vuelve
a cargar al usuario desde la base (así un usuario desactivado o borrado ya no
entra). Cerrar sesión borra la cookie.

La cookie no guarda la contraseña ni el hash; sin el secreto del servidor no
se puede fabricar un token válido."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

import streamlit as st
import streamlit.components.v1 as components

from db import repository as repo

COOKIE = "mrp_session"
TTL_SECONDS = 7 * 24 * 3600
SESSION_KEY = "auth_user"
PENDING_KEY = "_cookie_pending"  # "set:<token>" | "clear"
LOGGED_OUT_KEY = "_logged_out"


def _secret() -> bytes:
    for name in ("SESSION_SECRET", "SUPABASE_KEY"):
        value = os.getenv(name)
        if not value:
            try:
                value = st.secrets.get(name)
            except Exception:
                value = None
        if value:
            return str(value).encode()
    return b"mrp-local-dev-secret"


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(username: str) -> str:
    payload = base64.urlsafe_b64encode(f"{username}|{int(time.time()) + TTL_SECONDS}".encode()).decode()
    return f"{payload}.{_sign(payload)}"


def _username_from(token: str) -> str | None:
    try:
        payload, signature = token.rsplit(".", 1)
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        username, expires = base64.urlsafe_b64decode(payload.encode()).decode().rsplit("|", 1)
        return username if int(expires) > time.time() else None
    except Exception:
        return None


def restore() -> None:
    """Si no hay sesión pero el navegador trae una cookie válida, la reabre."""
    if SESSION_KEY in st.session_state or st.session_state.get(LOGGED_OUT_KEY):
        return
    token = st.context.cookies.get(COOKIE)
    username = _username_from(token) if token else None
    if not username:
        return
    user = repo.get_user_by_username(username)
    if not user or not user.get("active", True):
        return
    st.session_state[SESSION_KEY] = {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
    }
    st.session_state["_mrp_booted"] = True  # ya hay sesión: sin pantalla de carga


def remember(username: str) -> None:
    st.session_state.pop(LOGGED_OUT_KEY, None)
    st.session_state[PENDING_KEY] = f"set:{make_token(username)}"


def forget() -> None:
    st.session_state[LOGGED_OUT_KEY] = True
    st.session_state[PENDING_KEY] = "clear"


def flush_cookie() -> None:
    """Escribe/borra la cookie en el navegador (un script invisible, porque
    Streamlit no puede fijar cookies por sí solo). Se llama en cada recarga."""
    action = st.session_state.pop(PENDING_KEY, None)
    if not action:
        return
    if action == "clear":
        script = f"window.parent.document.cookie = '{COOKIE}=; max-age=0; path=/; SameSite=Lax';"
    else:
        token = action.split(":", 1)[1]
        script = f"window.parent.document.cookie = '{COOKIE}={token}; max-age={TTL_SECONDS}; path=/; SameSite=Lax';"
    components.html(f"<script>{script}</script>", height=0)
