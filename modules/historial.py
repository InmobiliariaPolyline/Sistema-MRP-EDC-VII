"""Módulo Historial: quién hizo qué y cuándo (solo administradores)."""
import html

import streamlit as st

from db import repository as repo
from modules import ui
from utils.timeago import time_ago


def render() -> None:
    ui.page_header(
        "Auditoría",
        "Historial de cambios",
        "Registro de lo que se creó, editó, recibió o eliminó, con la persona que lo hizo.",
    )
    log = repo.list_audit(limit=500)
    if log.empty:
        st.info("Todavía no hay cambios registrados.")
        return

    c1, c2 = st.columns([3, 2])
    query = c1.text_input("Buscar", placeholder="🔍 Buscar en el historial…", label_visibility="collapsed", key="audit_q")
    actors = ["Todas las personas"] + sorted(log["actor"].dropna().unique().tolist())
    actor = c2.selectbox("Persona", actors, label_visibility="collapsed", key="audit_actor")

    if actor != actors[0]:
        log = log[log["actor"] == actor]
    log = ui.filter_df(log, query, ["summary", "actor"])
    if log.empty:
        st.info("Nada coincide con los filtros.")
        return

    rows = []
    for entry in log.to_dict("records"):
        stamp = str(entry["created_at"])
        rows.append(
            ui.activity_item(
                html.escape(entry["summary"]),
                f"{stamp[:16].replace('T', ' ')} · {time_ago(stamp.replace(' ', 'T'))}",
                html.escape(entry["actor"]),
            )
        )
    st.markdown('<div class="mrp-panel">' + "".join(rows) + "</div>", unsafe_allow_html=True)
