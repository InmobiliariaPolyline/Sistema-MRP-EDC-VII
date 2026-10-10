"""Panel principal: eyebrow + saludo, tarjetas de stats, actividad reciente
y una dona de estado general de los proveedores."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import repository as repo
from modules import ordenes, ui
from utils.timeago import time_ago

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _saludo() -> str:
    hora = datetime.now(timezone(timedelta(hours=-5))).hour
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def render(user: dict) -> None:
    now = datetime.now(timezone(timedelta(hours=-5)))
    ui.page_header(
        f"Centro de control · {MESES[now.month - 1].upper()} DE {now.year}",
        f"{_saludo()}, {user['name']}",
        "Materiales, compras y obras: identifica qué necesita atención y consulta tus últimos movimientos.",
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
            ui.stat_card("🧾", totals.get("orders_open", 0), "Órdenes abiertas", "pendientes o enviadas"),
        ]
    )

    _render_alerts()
    _render_order_charts()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        _render_activity()

    with col_right:
        _render_status_donut(totals)

    st.write("")
    _render_sites_map()


def _render_alerts() -> None:
    stale = ordenes.stale_orders(repo.list_orders())
    if stale.empty:
        return
    detail = ", ".join(f"{r['code']} ({r['supplier_name']}, {int(r['age'])} d)" for r in stale.to_dict("records")[:5])
    st.warning(
        f"⏰ {len(stale)} orden(es) abierta(s) hace más de {ordenes.alert_days()} días: {detail}. "
        "Revísalas en Órdenes de compra.",
    )


def _bar_layout(fig: go.Figure, height: int = 240) -> go.Figure:
    fig.update_layout(
        margin=dict(t=8, b=0, l=0, r=0),
        height=height,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, type="category"),
        yaxis=dict(gridcolor="rgba(17,24,39,0.08)"),
    )
    return fig


def _render_order_charts() -> None:
    """Gasto por mes, gasto por proveedor y órdenes por estado."""
    orders = repo.list_orders()
    if orders.empty:
        return
    orders = orders.assign(total=orders["total"].astype(float))
    billable = orders[orders["status"] != "cancelada"]

    c1, c2, c3 = st.columns([3, 3, 2])
    with c1:
        with st.container(border=True):
            ui.panel_header("Compras", "Gasto por mes")
            if billable.empty:
                st.caption("Sin órdenes activas.")
            else:
                monthly = billable.assign(mes=billable["created_at"].astype(str).str[:7]).groupby("mes")["total"].sum().reset_index()
                fig = go.Figure(go.Bar(x=monthly["mes"], y=monthly["total"], marker_color="#6C5CE7", hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
                st.plotly_chart(ui.chart_theme(_bar_layout(fig)), width="stretch", config={"displayModeBar": False})
    with c2:
        with st.container(border=True):
            ui.panel_header("Compras", "Gasto por proveedor")
            if billable.empty:
                st.caption("Sin órdenes activas.")
            else:
                by_sup = billable.groupby("supplier_name")["total"].sum().sort_values().tail(6).reset_index()
                fig = go.Figure(go.Bar(x=by_sup["total"], y=by_sup["supplier_name"], orientation="h", marker_color="#8B7CF0", hovertemplate="%{y}: %{x:,.2f}<extra></extra>"))
                fig = _bar_layout(fig)
                fig.update_layout(xaxis=dict(gridcolor="rgba(17,24,39,0.08)", type="linear"), yaxis=dict(showgrid=False, type="category"))
                st.plotly_chart(ui.chart_theme(fig), width="stretch", config={"displayModeBar": False})
    with c3:
        with st.container(border=True):
            ui.panel_header("Compras", "Órdenes por estado")
            counts = orders.groupby("status").size()
            keys = [k for k in ordenes.STATUSES if k in counts.index]
            palette = {"pendiente": "#E8A33D", "enviada": "#3B82F6", "parcial": "#8B7CF0", "recibida": "#2DAA6B", "cancelada": "#E05A5A"}
            fig = go.Figure(
                go.Pie(
                    labels=[ordenes.STATUSES[k][0] for k in keys],
                    values=[int(counts[k]) for k in keys],
                    hole=0.6,
                    marker=dict(colors=[palette[k] for k in keys]),
                    textinfo="value",
                )
            )
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=240, showlegend=True, legend=dict(orientation="h", y=-0.1, font=dict(size=11)), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(ui.chart_theme(fig), width="stretch", config={"displayModeBar": False})


def _render_sites_map() -> None:
    """Todas las obras con ubicación en un mapa, y cuántos trabajadores tiene cada una."""
    sites = repo.list_project_sites()
    workers = repo.list_workers()
    counts = workers.groupby("project_site_id").size().to_dict() if not workers.empty else {}

    with st.container(border=True):
        ui.panel_header("Ubicaciones", "Obras en el mapa")
        if sites.empty:
            st.markdown('<div class="mrp-activity-sub">Todavía no hay obras registradas (se crean en Trabajadores → Obras / Proyectos).</div>', unsafe_allow_html=True)
            return

        located = sites[sites["latitude"].notna() & sites["longitude"].notna()]
        map_col, list_col = st.columns([3, 2])
        with map_col:
            if located.empty:
                st.caption("Ninguna obra tiene ubicación todavía: usa «Buscar dirección» al crearla.")
            else:
                st.map(
                    pd.DataFrame({"lat": located["latitude"].astype(float), "lon": located["longitude"].astype(float)}),
                    zoom=None if len(located) > 1 else 14,
                )
        with list_col:
            rows = []
            for site in sites.to_dict("records"):
                n = int(counts.get(site["id"], 0))
                rows.append(
                    ui.activity_item(
                        site["name"],
                        site["address"] or "Sin dirección",
                        f"{n} trabajador{'es' if n != 1 else ''}",
                        "📍 en el mapa" if site.get("latitude") else "sin ubicación",
                    )
                )
            st.markdown("".join(rows), unsafe_allow_html=True)


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
        st.plotly_chart(ui.chart_theme(fig), width="stretch", config={"displayModeBar": False})

        st.markdown(
            f'<div class="mrp-activity-item"><div>🟣 Con disponibilidad</div><b>{con_disponible}</b></div>'
            f'<div class="mrp-activity-item"><div>⚪ Sin disponibilidad</div><b>{sin_disponible}</b></div>',
            unsafe_allow_html=True,
        )
