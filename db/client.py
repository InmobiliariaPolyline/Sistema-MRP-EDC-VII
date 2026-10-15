"""Cliente de Supabase, compartido por toda la app.

Dos tipos de clave:

- `SUPABASE_SERVICE_KEY` (service_role): vive solo en el servidor de la app (secrets de Streamlit
  o `.env`), nunca llega al navegador, y salta las políticas de RLS. Es la recomendada: con ella la
  base puede quedar cerrada (RLS activo, sin acceso para la clave pública).
- `SUPABASE_KEY` (anon / publishable): clave pública. Con ella la app solo funciona si las tablas
  están abiertas (RLS desactivado), lo que deja los datos expuestos a quien la consiga.

Si hay clave de servicio se usa esa; si no, se usa la pública (modo abierto, como hasta ahora)."""
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _get_setting(name: str) -> str | None:
    # Prioridad: st.secrets (Streamlit Cloud) y si no, variables de entorno (.env local).
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name)


def has_supabase_config() -> bool:
    return bool(_get_setting("SUPABASE_URL") and (_get_setting("SUPABASE_SERVICE_KEY") or _get_setting("SUPABASE_KEY")))


def using_service_key() -> bool:
    """¿La app se conecta con la clave de servicio (base protegida)?"""
    return bool(_get_setting("SUPABASE_SERVICE_KEY"))


def _key() -> str | None:
    return _get_setting("SUPABASE_SERVICE_KEY") or _get_setting("SUPABASE_KEY")


@st.cache_resource
def get_client():
    from supabase import Client, create_client  # import diferido: no hace falta si se usa el modo local

    url = _get_setting("SUPABASE_URL")
    key = _key()
    if not url or not key:
        st.error(
            "Falta configurar SUPABASE_URL y SUPABASE_SERVICE_KEY (o SUPABASE_KEY). "
            "Copia .env.example a .env (o .streamlit/secrets.toml.example a "
            ".streamlit/secrets.toml) y completa tus datos."
        )
        st.stop()
    return create_client(url, key)
