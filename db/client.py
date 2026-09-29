"""Cliente de Supabase, compartido por toda la app."""
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
    return bool(_get_setting("SUPABASE_URL") and _get_setting("SUPABASE_KEY"))


@st.cache_resource
def get_client():
    from supabase import Client, create_client  # import diferido: no hace falta si se usa el modo local

    url = _get_setting("SUPABASE_URL")
    key = _get_setting("SUPABASE_KEY")
    if not url or not key:
        st.error(
            "Falta configurar SUPABASE_URL y SUPABASE_KEY. "
            "Copia .env.example a .env (o .streamlit/secrets.toml.example a "
            ".streamlit/secrets.toml) y completa tus datos."
        )
        st.stop()
    return create_client(url, key)
