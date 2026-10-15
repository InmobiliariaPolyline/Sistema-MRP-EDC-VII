"""Panel principal: banner de bienvenida con accesos rápidos, tarjetas de
estadísticas, gráficos de compras, actividad reciente y mapa de obras."""
import html
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
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ACCENT, ACCENT_SOFT = "#7C66FF", "#B9AEFF"
STATUS_COLORS = {"pendiente": "#F0A93B", "enviada": "#4C8DF6", "parcial": "#9A86FF", "recibida": "#2EB67D", "cancelada": "#E5636D"}


def _now() -> datetime:
    return datetime.now(timezone(timedelta(hours=-5)))


def _saludo() -> str:
    hora = _now().hour
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def render(user: dict) -> None:
    now = _now()
    totals = repo.dashboard_totals()
    orders = repo.list_orders()
    stale = ordenes.stale_orders(orders)

    chips = [f"📅 {DIAS[now.weekday()].capitalize()} {now.day} de {MESES[now.month - 1]}"]
    chips.append(f"🧾 {totals.get('orders_open', 0)} orden(es) abierta(s)")
    if len(stale):
        chips.append(f"⏰ {len(stale)} atrasada(s)")
    ui.hero(
        f"Centro de control · {MESES[now.month - 1].upper()} DE {now.year}",
        f"{_saludo()}, {user['name'].split()[0]}",
        "Materiales, compras y obras: identifica qué necesita atención y consulta tus últimos movimientos.",
        chips,
    )
    ui.guide_button("Dashboard")
    _render_quick_actions()

    monthly = _monthly_spend(orders)
    ui.stat_grid(
        [
            ui.stat_card("📦", totals["materials"], "Materiales", "en el catálogo", tone="purple"),
            ui.stat_card("🏭", totals["suppliers"], "Proveedores", "registrados en total", tone="blue"),
            ui.stat_card("✅", totals["suppliers_with_available"], "Con disponibilidad", "ofrecen algo hoy", tone="green"),
            ui.stat_card(
                "⚠️",
                totals["materials_without_supplier"],
                "Sin proveedor",
                "materiales por cotizar",
                warn=totals["materials_without_supplier"] > 0,
            ),
            ui.stat_card("🧾", totals.get("orders_open", 0), "Órdenes abiertas", "pendientes, enviadas o parciales", tone="teal", trend=monthly),
        ]
    )

    _render_alerts(stale)
    _render_order_charts(orders)

    col_left, col_right = st.columns([3, 2])
    with col_left:
        _render_activity()
    with col_right:
        _render_status_donut(totals)

    st.write("")
    _render_sites_map()


def _render_quick_actions() -> None:
    """Accesos directos a lo que más se hace."""
    actions = [
        ("Nueva orden", ":material/add_shopping_cart:", "Órdenes de compra"),
        ("Pasar lista", ":material/event_available:", "Asistencia"),
        ("Ver inventario", ":material/inventory_2:", "Inventario"),
        ("Ver obras", ":material/apartment:", "Obras"),
    ]
    cols = st.columns(len(actions))
    for col, (label, icon, route) in zip(cols, actions):
        col.button(label, icon=icon, key=f"quick_{route}", width="stretch", on_click=ui.go, args=(route,))


def _monthly_spend(orders: pd.DataFrame) -> list[float]:
    if orders.empty:
        return []
    billable = orders[orders["status"] != "cancelada"]
    if billable.empty:
        return []
    grouped = billable.assign(mes=billable["created_at"].astype(str).str[:7], total=billable["total"].astype(float)).groupby("mes")["total"].sum()
    return grouped.tail(8).tolist()


def _render_alerts(stale: pd.DataFrame) -> None:
    if stale.empty:
        return
    detail = ", ".join(f"{r['code']} ({r['supplier_name']}, {int(r['age'])} d)" for r in stale.to_dict("records")[:5])
    st.warning(
        f"**{len(stale)} orden(es) abierta(s) hace más de {ordenes.alert_days()} días:** {detail}. "
        "Revísalas en Órdenes de compra.",
        icon=":material/schedule:",
    )


def _bar_layout(fig: go.Figure, height: int = 250) -> go.Figure:
    fig.update_layout(margin=dict(t=8, b=0, l=0, r=0), height=height, showlegend=False, bargap=0.38)
    return fig


def _empty_chart(message: str = "Aún no hay órdenes activas.") -> None:
    st.markdown(f'<div class="mrp-activity-sub" style="padding:36px 0;text-align:center">{message}</div>', unsafe_allow_html=True)


def _render_order_charts(orders: pd.DataFrame) -> None:
    """Gasto por mes, gasto por proveedor y órdenes por estado."""
    if orders.empty:
        return
    orders = orders.assign(total=orders["total"].astype(float))
    billable = orders[orders["status"] != "cancelada"]
    bar_style = dict(cornerradius=10) if hasattr(go.bar.Marker, "cornerradius") else {}

    c1, c2, c3 = st.columns([3, 3, 2])
    with c1:
        with st.container(border=True):
            ui.panel_header("Compras", "Gasto por mes")
            if billable.empty:
                _empty_chart()
            else:
                monthly = billable.assign(mes=billable["created_at"].astype(str).str[:7]).groupby("mes")["total"].sum().reset_index()
                fig = go.Figure(go.Bar(x=monthly["mes"], y=monthly["total"], marker=dict(color=ACCENT, **bar_style), hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
                fig.update_xaxes(type="category", showgrid=False)
                st.plotly_chart(ui.chart_theme(_bar_layout(fig)), width="stretch", config={"displayModeBar": False})
    with c2:
        with st.container(border=True):
            ui.panel_header("Compras", "Gasto por proveedor")
            if billable.empty:
                _empty_chart()
            else:
                by_sup = billable.groupby("supplier_name")["total"].sum().sort_values().tail(6).reset_index()
                fig = go.Figure(go.Bar(x=by_sup["total"], y=by_sup["supplier_name"], orientation="h", marker=dict(color=ACCENT_SOFT, **bar_style), hovertemplate="%{y}: %{x:,.2f}<extra></extra>"))
                fig.update_yaxes(type="category", showgrid=False)
                st.plotly_chart(ui.chart_theme(_bar_layout(fig)), width="stretch", config={"displayModeBar": False})
    with c3:
        with st.container(border=True):
            ui.panel_header("Compras", "Órdenes por estado")
            counts = orders.groupby("status").size()
            keys = [k for k in ordenes.STATUSES if k in counts.index]
            fig = go.Figure(
                go.Pie(
                    labels=[ordenes.STATUSES[k][0] for k in keys],
                    values=[int(counts[k]) for k in keys],
                    hole=0.66,
                    marker=dict(colors=[STATUS_COLORS[k] for k in keys], line=dict(color="rgba(0,0,0,0)", width=0)),
                    textinfo="value",
                    sort=False,
                )
            )
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250, showlegend=True, legend=dict(orientation="h", y=-0.08, font=dict(size=11)))
            st.plotly_chart(ui.chart_theme(fig), width="stretch", config={"displayModeBar": False})


def _render_sites_map() -> None:
    """Todas las obras con ubicación en un mapa, y cuántos trabajadores tiene cada una."""
    sites = repo.list_project_sites()
    workers = repo.list_workers()
    counts = workers.groupby("project_site_id").size().to_dict() if not workers.empty else {}

    with st.container(border=True):
        ui.panel_header("Ubicaciones", "Obras en el mapa")
        if sites.empty:
            ui.empty_state("Aún no hay obras", "Se crean en Trabajadores → Obras / Proyectos y aparecerán aquí con su ubicación.", "🏗️")
            return

        located = sites[sites["latitude"].notna() & sites["longitude"].notna()]
        map_col, list_col = st.columns([3, 2])
        with map_col:
            if located.empty:
                st.caption("Ninguna obra tiene ubicación todavía: pega el enlace de Google Maps al crearla.")
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
                        html.escape(site["name"]),
                        html.escape(site["address"] or "Sin dirección"),
                        f"{n} trabajador{'es' if n != 1 else ''}",
                        "📍 en el mapa" if site.get("latitude") else "sin ubicación",
                    )
                )
            st.markdown("".join(rows), unsafe_allow_html=True)


def _icon_for(summary: str) -> str:
    text = summary.lower()
    for words, icon in [
        (("eliminad",), "🗑️"), (("recepci", "stock", "movimiento", "consumo", "entrada", "salida"), "📦"),
        (("orden",), "🧾"), (("proveedor",), "🏭"), (("material", "presupuesto"), "🧱"),
        (("asistencia",), "📅"), (("trabajador", "obra", "cuadrilla", "acceso"), "👷"),
    ]:
        if any(w in text for w in words):
            return icon
    return "✨"


def _render_activity() -> None:
    log = repo.list_audit(limit=6)
    if not log.empty:
        rows = [
            ui.timeline_item(
                _icon_for(e["summary"]),
                html.escape(e["summary"]),
                html.escape(e["actor"]),
                time_ago(str(e["created_at"]).replace(" ", "T")),
            )
            for e in log.to_dict("records")
        ]
    else:
        rows = [
            ui.timeline_item("🧱" if it["kind"] == "Material" else "🏭", html.escape(it["name"]), html.escape(it["sub"]), time_ago(it["created_at"]))
            for it in repo.recent_activity(limit=6)
        ]
    body = "".join(rows) if rows else '<div class="mrp-activity-sub">Todavía no hay actividad.</div>'
    st.markdown(
        '<div class="mrp-panel">'
        '<div class="mrp-eyebrow">Seguimiento</div>'
        '<div class="mrp-panel-title">Actividad reciente</div>'
        f"{body}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_status_donut(totals: dict) -> None:
    con_disponible = totals["suppliers_with_available"]
    sin_disponible = max(totals["suppliers"] - con_disponible, 0)

    with st.container(border=True):
        ui.panel_header("Lectura del portafolio", "Estado de proveedores")

        if totals["suppliers"] == 0:
            ui.empty_state("Sin proveedores", "Registra tu primer proveedor para ver su disponibilidad aquí.", "🏭")
            return

        pct = round(100 * con_disponible / totals["suppliers"])
        fig = go.Figure(
            data=[
                go.Pie(
                    values=[con_disponible, sin_disponible],
                    hole=0.74,
                    marker=dict(colors=[ACCENT, "rgba(150,160,190,.25)"], line=dict(color="rgba(0,0,0,0)", width=0)),
                    textinfo="none",
                    hoverinfo="label+value",
                    labels=["Con disponibilidad", "Sin disponibilidad"],
                    sort=False,
                )
            ]
        )
        fig.update_layout(
            showlegend=False,
            margin=dict(t=0, b=0, l=0, r=0),
            height=210,
            annotations=[dict(text=f"<b>{pct}%</b><br><span style='font-size:11px'>con stock</span>", showarrow=False, font=dict(size=24))],
        )
        st.plotly_chart(ui.chart_theme(fig), width="stretch", config={"displayModeBar": False})

        st.markdown(
            f'<div class="mrp-activity-item"><div>🟣 Con disponibilidad</div><b>{con_disponible}</b></div>'
            f'<div class="mrp-activity-item"><div>⚪ Sin disponibilidad</div><b>{sin_disponible}</b></div>',
            unsafe_allow_html=True,
        )
