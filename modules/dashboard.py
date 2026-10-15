"""Panel principal: banner de bienvenida con accesos rápidos, tarjetas de
estadísticas, analítica de compras, avance por obra, asistencia, actividad
reciente y mapa de obras."""
import html
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import repository as repo
from modules import obras, ordenes, ui
from utils.timeago import time_ago

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ACCENT, ACCENT_SOFT, TEAL = "#7C66FF", "#B9AEFF", "#22C3B8"
STATUS_COLORS = {"pendiente": "#F0A93B", "enviada": "#4C8DF6", "parcial": "#9A86FF", "recibida": "#2EB67D", "cancelada": "#E5636D"}
ATTENDANCE_COLORS = {"presente": "#2EB67D", "tardanza": "#F0A93B", "permiso": "#4C8DF6", "ausente": "#E5636D"}
CONFIG = {"displayModeBar": False}


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
    _render_purchase_analytics(orders)
    _render_site_and_attendance()

    col_left, col_right = st.columns([3, 2])
    with col_left:
        _render_activity()
    with col_right:
        _render_status_donut(totals)

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


def _billable(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders
    active = orders[orders["status"] != "cancelada"]
    return active.assign(total=active["total"].astype(float), mes=active["created_at"].astype(str).str[:7])


def _monthly_spend(orders: pd.DataFrame) -> list[float]:
    billable = _billable(orders)
    if billable.empty:
        return []
    return billable.groupby("mes")["total"].sum().tail(8).tolist()


def _render_alerts(stale: pd.DataFrame) -> None:
    if stale.empty:
        return
    detail = ", ".join(f"{r['code']} ({r['supplier_name']}, {int(r['age'])} d)" for r in stale.to_dict("records")[:5])
    st.warning(
        f"**{len(stale)} orden(es) abierta(s) hace más de {ordenes.alert_days()} días:** {detail}. "
        "Revísalas en Órdenes de compra.",
        icon=":material/schedule:",
    )


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def _plot(fig: go.Figure, height: int = 300) -> None:
    fig.update_layout(height=height)
    st.plotly_chart(ui.chart_theme(fig), width="stretch", config=CONFIG)


def _panel(eyebrow: str, title: str, subtitle: str = "") -> None:
    ui.panel_header(eyebrow, title)
    if subtitle:
        st.markdown(f'<div class="mrp-chart-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def _empty_chart(message: str = "Aún no hay datos para este gráfico.") -> None:
    st.markdown(f'<div class="mrp-activity-sub" style="padding:2.2rem 0;text-align:center">{html.escape(message)}</div>', unsafe_allow_html=True)


def _bar_marker(color) -> dict:
    return dict(color=color, cornerradius=10) if hasattr(go.bar.Marker, "cornerradius") else dict(color=color)


def _render_purchase_analytics(orders: pd.DataFrame) -> None:
    """Gasto mensual, estado de las órdenes, gasto por categoría y por proveedor."""
    if orders.empty:
        return
    billable = _billable(orders)

    c1, c2 = st.columns([5, 3])
    with c1:
        with st.container(border=True):
            _panel("Compras", "Gasto mensual y órdenes", "Barras: monto comprado. Línea: cantidad de órdenes.")
            _spend_combo(billable)
    with c2:
        with st.container(border=True):
            _panel("Compras", "Órdenes por estado", "Dónde está cada pedido hoy.")
            _status_chart(orders)

    c3, c4 = st.columns([1, 1])
    with c3:
        with st.container(border=True):
            _panel("Compras", "Gasto por categoría", "En qué tipo de material se va el dinero.")
            _category_treemap()
    with c4:
        with st.container(border=True):
            _panel("Compras", "Gasto por proveedor", "Los seis proveedores con más compras.")
            _supplier_bars(billable)


def _spend_combo(billable: pd.DataFrame) -> None:
    if billable.empty:
        _empty_chart("Aún no hay órdenes activas.")
        return
    monthly = billable.groupby("mes").agg(total=("total", "sum"), n=("code", "count")).reset_index()
    fig = go.Figure()
    fig.add_bar(x=monthly["mes"], y=monthly["total"], name="Monto", marker=_bar_marker(ACCENT), hovertemplate="%{x}: %{y:,.2f}<extra>Monto</extra>")
    fig.add_scatter(x=monthly["mes"], y=monthly["n"], name="Órdenes", yaxis="y2", mode="lines+markers",
                    line=dict(color=TEAL, width=3, shape="spline"), marker=dict(size=9, line=dict(width=2, color="#FFFFFF")),
                    hovertemplate="%{x}: %{y} orden(es)<extra></extra>")
    fig.update_layout(
        margin=dict(t=8, b=0, l=0, r=0), bargap=0.4,
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, rangemode="tozero", dtick=1),
    )
    fig.update_xaxes(type="category", showgrid=False)
    _plot(fig, 300)


def _status_chart(orders: pd.DataFrame) -> None:
    counts = orders.groupby("status").size()
    keys = [k for k in ordenes.STATUSES if k in counts.index]
    fig = go.Figure(
        go.Pie(
            labels=[ordenes.STATUSES[k][0] for k in keys],
            values=[int(counts[k]) for k in keys],
            hole=0.68, sort=False, textinfo="value",
            marker=dict(colors=[STATUS_COLORS[k] for k in keys], line=dict(color="rgba(0,0,0,0)", width=0)),
        )
    )
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0), showlegend=True, legend=dict(orientation="h", y=-0.06, font=dict(size=11)),
        annotations=[dict(text=f"<b>{int(counts.sum())}</b><br><span style='font-size:11px'>órdenes</span>", showarrow=False, font=dict(size=24))],
    )
    _plot(fig, 300)


def _category_treemap() -> None:
    items = repo.list_order_items()
    orders = repo.list_orders()
    if items.empty or orders.empty:
        _empty_chart("Sin líneas de órdenes todavía.")
        return
    active = set(orders.loc[orders["status"] != "cancelada", "id"])
    items = items[items["order_id"].isin(active)]
    if items.empty:
        _empty_chart("Sin líneas de órdenes activas.")
        return
    categories = repo.list_materials().set_index("id")["category"].to_dict()
    spend = (
        items.assign(category=items["material_id"].map(categories).fillna("Sin categoría"), amount=items["subtotal"].astype(float))
        .groupby("category")["amount"].sum().sort_values(ascending=False)
    )
    spend = spend[spend > 0]
    if spend.empty:
        _empty_chart("Las líneas todavía no tienen precio.")
        return
    fig = go.Figure(
        go.Treemap(
            labels=spend.index.tolist(), parents=[""] * len(spend), values=spend.tolist(),
            textinfo="label+percent root", texttemplate="<b>%{label}</b><br>%{value:,.0f}",
            marker=dict(colors=spend.tolist(), colorscale=[[0, "#D9D2FF"], [1, "#5A3FF0"]], line=dict(width=3, color="rgba(0,0,0,0)")),
            hovertemplate="%{label}: %{value:,.2f}<extra></extra>", pathbar=dict(visible=False),
        )
    )
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
    _plot(fig, 300)


def _supplier_bars(billable: pd.DataFrame) -> None:
    if billable.empty:
        _empty_chart("Aún no hay órdenes activas.")
        return
    by_sup = billable.groupby("supplier_name")["total"].sum().sort_values().tail(6).reset_index()
    share = by_sup["total"] / by_sup["total"].sum() * 100
    fig = go.Figure(
        go.Bar(
            x=by_sup["total"], y=by_sup["supplier_name"], orientation="h", marker=_bar_marker(ACCENT_SOFT),
            text=[f"{v:,.0f}  ·  {p:.0f}%" for v, p in zip(by_sup["total"], share)], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: %{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(margin=dict(t=4, b=0, l=0, r=70), bargap=0.4)
    fig.update_yaxes(type="category", showgrid=False)
    fig.update_xaxes(showgrid=False, showticklabels=False)
    _plot(fig, 300)


def _render_site_and_attendance() -> None:
    c1, c2 = st.columns([5, 3])
    with c1:
        with st.container(border=True):
            _panel("Obras", "Avance de materiales por obra", "Presupuesto frente a lo pedido y lo consumido (en costo).")
            _site_progress_chart()
    with c2:
        with st.container(border=True):
            _panel("Personal", "Asistencia de los últimos 14 días", "Personas por estado y día.")
            _attendance_chart()


def _site_progress_chart() -> None:
    sites = repo.list_project_sites()
    rows = []
    for site in sites.to_dict("records"):
        df = obras.progress_by_material(site["id"])
        if df.empty or not float(df["Presupuesto $"].sum()):
            continue
        rows.append(
            {
                "obra": site["name"],
                "Presupuesto": float(df["Presupuesto $"].sum()),
                "Pedido": float(df["Gasto pedido $"].sum()),
                "Consumido": float(df["Consumido $"].sum()),
            }
        )
    if not rows:
        _empty_chart("Define el presupuesto de una obra (Obras → Materiales) para ver su avance.")
        return
    data = pd.DataFrame(rows).iloc[::-1]
    fig = go.Figure()
    for name, color in (("Presupuesto", "rgba(150,160,190,.38)"), ("Pedido", ACCENT), ("Consumido", TEAL)):
        fig.add_bar(y=data["obra"], x=data[name], name=name, orientation="h", marker=_bar_marker(color), hovertemplate="%{y}: %{x:,.2f}<extra>" + name + "</extra>")
    fig.update_layout(margin=dict(t=8, b=0, l=0, r=0), barmode="group", bargap=0.3, bargroupgap=0.08, legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)))
    fig.update_yaxes(type="category", showgrid=False)
    _plot(fig, max(300, 90 * len(rows) + 120))


def _attendance_chart() -> None:
    today = date.today()
    records = repo.list_attendance((today - timedelta(days=13)).isoformat(), today.isoformat())
    if records.empty:
        _empty_chart("Aún no hay asistencia registrada en los últimos 14 días.")
        return
    counts = records.groupby(["work_date", "status"]).size().unstack(fill_value=0).reindex(
        [(today - timedelta(days=13 - i)).isoformat() for i in range(14)], fill_value=0
    )
    fig = go.Figure()
    for status, color in ATTENDANCE_COLORS.items():
        if status in counts.columns:
            fig.add_bar(x=[d[5:] for d in counts.index], y=counts[status], name=status.capitalize(), marker=dict(color=color), hovertemplate="%{x}: %{y}<extra>" + status + "</extra>")
    fig.update_layout(margin=dict(t=8, b=0, l=0, r=0), barmode="stack", bargap=0.25, legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)))
    fig.update_xaxes(type="category", showgrid=False)
    _plot(fig, 300)


# ---------------------------------------------------------------------------
# Paneles
# ---------------------------------------------------------------------------

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
            annotations=[dict(text=f"<b>{pct}%</b><br><span style='font-size:11px'>con stock</span>", showarrow=False, font=dict(size=24))],
        )
        _plot(fig, 220)

        st.markdown(
            f'<div class="mrp-activity-item"><div>🟣 Con disponibilidad</div><b>{con_disponible}</b></div>'
            f'<div class="mrp-activity-item"><div>⚪ Sin disponibilidad</div><b>{sin_disponible}</b></div>',
            unsafe_allow_html=True,
        )
