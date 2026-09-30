"""Panel principal: eyebrow + saludo, tarjetas de stats, actividad reciente
y una dona de estado general de los proveedores."""
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from db import repository as repo
from modules import ui
from utils.timeago import time_ago

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _saludo() -> str:
    hora = datetime.now().hour
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def render(user: dict) -> None:
    now = datetime.now()
    ui.page_header(
        f"Centro de control · {MESES[now.month - 1].upper()} DE {now.year}",
        f"{_saludo()}, {user['name']}",
        "Una lectura rápida de tus materiales y proveedores.",
    )

    totals = repo.dashboard_totals()

    ui.stat_grid(
        [
            ui.stat_card("📦", totals["materials"], "Materiales", "en el catálogo"),
            ui.stat_card("🏭", totals["suppliers"], "Proveedores", "registrados en total"),
            ui.stat_card("✅", totals["suppliers_with_available"], "Con disponibilidad", "ofrecen algo hoy"),
            ui.stat_card(
                "⚠️",
                totals["materials_without_supplier"],
                "Sin proveedor",
                "materiales por cotizar",
                warn=totals["materials_without_supplier"] > 0,
            ),
        ]
    )

    col_left, col_right = st.columns([3, 2])

    with col_left:
        _render_activity()

    with col_right:
        _render_status_donut(totals)


def _render_activity() -> None:
    items = repo.recent_activity(limit=6)
    rows = [ui.activity_item(it["name"], it["sub"], it["kind"], time_ago(it["created_at"])) for it in items]
    st.markdown(
        '<div class="mrp-panel">'
        '<div class="mrp-eyebrow">Seguimiento</div>'
        '<div class="mrp-panel-title">Actividad reciente</div>'
        f"{ui.activity_list(rows)}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_status_donut(totals: dict) -> None:
    con_disponible = totals["suppliers_with_available"]
    sin_disponible = max(totals["suppliers"] - con_disponible, 0)

    with st.container(border=True):
        st.markdown(
            '<div class="mrp-eyebrow">Lectura del portafolio</div>'
            '<div class="mrp-panel-title">Estado de proveedores</div>',
            unsafe_allow_html=True,
        )

        if totals["suppliers"] == 0:
            st.markdown('<div class="mrp-activity-sub">Todavía no hay proveedores registrados.</div>', unsafe_allow_html=True)
            return

        pct = round(100 * con_disponible / totals["suppliers"])
        fig = go.Figure(
            data=[
                go.Pie(
                    values=[con_disponible, sin_disponible],
                    hole=0.72,
                    marker=dict(colors=["#6C5CE7", "#E9E9F2"]),
                    textinfo="none",
                    hoverinfo="label+value",
                    labels=["Con disponibilidad", "Sin disponibilidad"],
                )
            ]
        )
        fig.update_layout(
            showlegend=False,
            margin=dict(t=0, b=0, l=0, r=0),
            height=200,
            annotations=[dict(text=f"<b>{pct}%</b><br><span style='font-size:11px'>con stock</span>", showarrow=False, font=dict(size=20))],
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown(
            f'<div class="mrp-activity-item"><div>🟣 Con disponibilidad</div><b>{con_disponible}</b></div>'
            f'<div class="mrp-activity-item"><div>⚪ Sin disponibilidad</div><b>{sin_disponible}</b></div>',
            unsafe_allow_html=True,
        )
