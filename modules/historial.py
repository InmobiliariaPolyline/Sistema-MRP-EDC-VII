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
        ui.empty_state("El historial está listo", "Los registros, cambios y movimientos que realices aparecerán aquí con su responsable y fecha.", "🕘")
        return

    total = len(log)
    c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="bottom")
    query = c1.text_input("Buscar", placeholder="Buscar un cambio o una persona…", key="audit_q")
    actors = ["Todas las personas"] + sorted(log["actor"].dropna().unique().tolist())
    actor = c2.selectbox("Persona", actors, key="audit_actor")
    def reset():
        st.session_state["audit_q"] = ""
        st.session_state["audit_actor"] = actors[0]
        st.session_state["audit_list_page"] = 1
    c3.button("Limpiar", on_click=reset, width="stretch")

    if actor != actors[0]:
        log = log[log["actor"] == actor]
    log = ui.filter_df(log, query, ["summary", "actor"])
    ui.result_count(len(log), total, "cambios recientes")
    if log.empty:
        ui.empty_state("Sin coincidencias", "Prueba otra búsqueda o pulsa «Limpiar» para ver los cambios recientes.", "🔎")
        return
    log = ui.paginate(log, "audit_list")

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
