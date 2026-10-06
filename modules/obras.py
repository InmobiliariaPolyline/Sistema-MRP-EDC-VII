"""Módulo de Obras: presupuesto de materiales por obra frente a lo que ya se
pidió, recibió y consumió."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import inventario, materiales, ui
from utils.geocode import google_maps_search_url

SITE_KEY = "obras_site"


def progress_by_material(site_id: str) -> pd.DataFrame:
    """Por material: presupuestado, pedido, recibido, consumido y gasto, para una obra."""
    budgets = repo.list_budgets(site_id)
    orders = repo.list_orders()
    orders = orders[(orders["project_site_id"] == site_id) & (orders["status"] != "cancelada")] if not orders.empty else orders
    items = repo.list_order_items()
    items = items[items["order_id"].isin(orders["id"])] if not orders.empty and not items.empty else items.iloc[0:0]
    consumed = repo.list_movements(project_site_id=site_id, limit=5000)

    data: dict[str, dict] = {}

    def slot(material_id: str, name: str, category: str | None, unit: str | None) -> dict:
        return data.setdefault(
            material_id,
            {
                "material_id": material_id, "Material": name, "Categoría": category, "Unidad": unit,
                "Presupuesto": 0.0, "Pedido": 0.0, "Recibido": 0.0, "Consumido": 0.0,
                "Presupuesto $": 0.0, "Gasto pedido $": 0.0, "Recibido $": 0.0, "Consumido $": 0.0,
                "budget_id": None, "planned_price": 0.0,
            },
        )

    for b in budgets.to_dict("records"):
        s = slot(b["material_id"], b["material_name"], b["category"], b["unit"])
        s["Presupuesto"] = float(b["planned_qty"])
        s["Presupuesto $"] = float(b["planned_qty"]) * float(b["planned_unit_price"])
        s["budget_id"] = b["id"]
        s["planned_price"] = float(b["planned_unit_price"])
    for i in items.to_dict("records"):
        if not i.get("material_id"):
            continue
        s = slot(i["material_id"], i["material_name"], None, i.get("unit"))
        s["Pedido"] += float(i["quantity"])
        s["Recibido"] += float(i["received_qty"])
        s["Gasto pedido $"] += float(i["quantity"]) * float(i["unit_price"])
        s["Recibido $"] += float(i["received_qty"]) * float(i["unit_price"])
    for m in consumed.to_dict("records"):
        if m["kind"] != "salida":
            continue
        s = slot(m["material_id"], m["material_name"], m["category"], m["unit"])
        s["Consumido"] += float(m["quantity"])

    for s in data.values():  # el consumo se valora al precio presupuestado (o al promedio pedido)
        price = s["planned_price"] or (s["Gasto pedido $"] / s["Pedido"] if s["Pedido"] else 0.0)
        s["Consumido $"] = s["Consumido"] * price

    columns = [
        "material_id", "budget_id", "Material", "Categoría", "Unidad", "Presupuesto", "Pedido", "Recibido",
        "Consumido", "Presupuesto $", "Gasto pedido $", "Recibido $", "Consumido $", "planned_price",
    ]
    df = pd.DataFrame(list(data.values()))
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns].sort_values("Material").reset_index(drop=True) if not df.empty else df


@st.dialog("Material del presupuesto")
def _budget_dialog(site_id: str, site_name: str) -> None:
    ui.tip("Ejemplo: Concreto, 20 m³ previstos a 120.00 c/u. El precio se propone con el mejor de tus proveedores.")
    materials = repo.list_materials()
    if materials.empty:
        st.info("Primero carga materiales en el catálogo.")
        return
    offers = repo.list_offers()
    options = {f"{r['category']} · {r['name']}": r for r in materials.to_dict("records")}
    choice = st.selectbox("Material", list(options))
    material = options[choice]

    current = repo.list_budgets(site_id)
    current = current[current["material_id"] == material["id"]]
    planned_qty = float(current.iloc[0]["planned_qty"]) if not current.empty else 0.0
    if not current.empty:
        suggested = float(current.iloc[0]["planned_unit_price"])
    else:
        prices = offers[(offers["material_id"] == material["id"]) & offers["price"].notna()]["price"].astype(float)
        prices = prices[prices > 0]
        suggested = float(prices.min()) if not prices.empty else 0.0

    c1, c2 = st.columns(2)
    qty = c1.number_input(f"Cantidad prevista ({material['metric_label'] or 'unid.'})", min_value=0.0, value=planned_qty, step=1.0, key=f"bq_{material['id']}")
    price = c2.number_input("Precio unit. estimado", min_value=0.0, value=suggested, step=0.1, format="%.2f", key=f"bp_{material['id']}",
                            help="Se propone el mejor precio entre tus proveedores.")
    st.caption(f"Costo previsto: **{qty * price:,.2f}**")
    if st.button("Guardar en el presupuesto", type="primary", use_container_width=True):
        if qty <= 0:
            st.error("La cantidad debe ser mayor que 0.")
            return
        repo.set_budget(site_id, material["id"], qty, price)
        ui.flash(f"Presupuesto de «{site_name}»: {material['name']} × {qty:g}.", "🧮")
        st.rerun()


def site_progress(df: pd.DataFrame) -> dict:
    """Porcentajes de avance de una obra (ponderados por costo)."""
    if df.empty:
        return {"planned": 0.0, "ordered": 0.0, "pct_ordered": None, "pct_received": None, "pct_consumed": None}
    planned = float(df["Presupuesto $"].sum())
    ordered = float(df["Gasto pedido $"].sum())
    received = float(df["Recibido $"].sum())
    consumed_capped = float(df[["Consumido $", "Presupuesto $"]].min(axis=1).sum())
    return {
        "planned": planned,
        "ordered": ordered,
        "pct_ordered": min(ordered / planned, 1.0) if planned else None,
        "pct_received": min(received / ordered, 1.0) if ordered else None,
        "pct_consumed": min(consumed_capped / planned, 1.0) if planned else None,
    }


def render() -> None:
    sites = repo.list_project_sites()
    ui.page_header(
        "Control de obra",
        "Obras y presupuesto",
        "La ficha completa de cada obra: ubicación, materiales, trabajadores y progreso.",
    )
    if sites.empty:
        st.info("Todavía no hay obras. Se crean en Trabajadores → Obras / Proyectos.")
        return

    site_name = st.selectbox("Obra", sites["name"].tolist(), key=SITE_KEY)
    site = sites[sites["name"] == site_name].to_dict("records")[0]
    site_id = site["id"]

    df = progress_by_material(site_id)
    prog = site_progress(df)
    over = int(((df["Pedido"] > df["Presupuesto"]) & (df["Presupuesto"] > 0)).sum()) if not df.empty else 0
    pct = f"{prog['ordered'] / prog['planned'] * 100:.0f}% del presupuesto" if prog["planned"] else "sin presupuesto"
    ui.stat_grid(
        [
            ui.stat_card("🧮", f"{prog['planned']:,.0f}", "Presupuesto", "costo previsto de materiales"),
            ui.stat_card("🧾", f"{prog['ordered']:,.0f}", "Pedido hasta hoy", pct, warn=prog["planned"] > 0 and prog["ordered"] > prog["planned"]),
            ui.stat_card("⚖️", f"{prog['planned'] - prog['ordered']:,.0f}", "Disponible", "presupuesto − pedido"),
            ui.stat_card("🚨", over, "Materiales excedidos", "pedido > presupuesto", warn=over > 0),
        ]
    )

    tab_info, tab_materials, tab_workers, tab_progress = st.tabs(["📍 Información", "📦 Materiales", "👷 Trabajadores", "📈 Progreso"])
    with tab_info:
        _tab_info(site)
    with tab_materials:
        _tab_materials(site, df)
    with tab_workers:
        _tab_workers(site)
    with tab_progress:
        _tab_progress(site, df, prog)


def _tab_info(site: dict) -> None:
    workers = repo.list_workers()
    n_workers = int((workers["project_site_id"] == site["id"]).sum()) if not workers.empty else 0
    orders = repo.list_orders()
    n_orders = int((orders["project_site_id"] == site["id"]).sum()) if not orders.empty else 0

    st.markdown(f'<div class="mrp-panel-title">{site["name"]}</div>', unsafe_allow_html=True)
    st.write(f"**Dirección:** {site['address'] or 'sin dirección registrada'}")
    st.write(f"**Registrada el:** {str(site['created_at'])[:10]}  ·  **Trabajadores:** {n_workers}  ·  **Órdenes de compra:** {n_orders}")

    lat_raw, lon_raw = site.get("latitude"), site.get("longitude")
    if lat_raw is None or lon_raw is None or lat_raw != lat_raw:
        st.info("Esta obra no tiene ubicación en el mapa. Elimínala y vuelve a crearla en Trabajadores → Obras / Proyectos pegando el enlace de Google Maps.")
        return
    lat, lon = float(lat_raw), float(lon_raw)
    st.map(pd.DataFrame([{"lat": lat, "lon": lon}]), zoom=16)
    st.caption(f"Coordenadas: {lat:.6f}, {lon:.6f}")
    url = google_maps_search_url(coords=(lat, lon))
    st.markdown(f'<a class="mrp-link" href="{url}" target="_blank" rel="noopener">🗺️ Abrir en Google Maps</a>', unsafe_allow_html=True)


def _tab_materials(site: dict, df: pd.DataFrame) -> None:
    site_id, site_name = site["id"], site["name"]
    ui.tip("Primero define lo que esperas usar con «＋ Material al presupuesto». Luego verás cuánto llevas pedido, recibido y consumido.")
    b1, b2, _ = st.columns([2, 2, 4])
    if b1.button("＋ Material al presupuesto", type="primary", use_container_width=True):
        _budget_dialog(site_id, site_name)
    if b2.button("📤 Registrar consumo", use_container_width=True):
        inventario.movement_dialog(default_site_id=site_id)

    if df.empty:
        st.info("Esta obra todavía no tiene presupuesto ni pedidos.")
        return

    view = df.copy()
    view["Estado"] = view.apply(_state, axis=1)
    view["Consumido %"] = view.apply(lambda r: min(r["Consumido"] / r["Presupuesto"] * 100, 100) if r["Presupuesto"] else 0, axis=1)
    st.dataframe(
        view[["Material", "Unidad", "Presupuesto", "Pedido", "Recibido", "Consumido", "Consumido %", "Presupuesto $", "Gasto pedido $", "Estado"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Presupuesto": st.column_config.NumberColumn(format="%.2f"),
            "Pedido": st.column_config.NumberColumn(format="%.2f"),
            "Recibido": st.column_config.NumberColumn(format="%.2f"),
            "Consumido": st.column_config.NumberColumn(format="%.2f"),
            "Consumido %": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
            "Presupuesto $": st.column_config.NumberColumn(format="%.2f"),
            "Gasto pedido $": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.markdown("**Informarse de un material**")
    names = {r["Material"]: r["material_id"] for r in df.to_dict("records")}
    i1, i2 = st.columns([4, 2])
    chosen = i1.selectbox("Material", list(names), label_visibility="collapsed", key=f"obra_mat_info_{site_id}")
    if i2.button("ℹ️ Ver ficha", use_container_width=True, key=f"obra_mat_btn_{site_id}"):
        materiales.info_dialog(names[chosen])

    budgeted = df[df["budget_id"].notna()]
    if not budgeted.empty:
        with st.expander("Quitar materiales del presupuesto"):
            for row in budgeted.to_dict("records"):
                c1, c2 = st.columns([6, 1])
                c1.write(f"{row['Material']} · {row['Presupuesto']:g} {row['Unidad'] or ''}")
                if c2.button("🗑", key=f"del_budget_{row['budget_id']}", help="Quitar del presupuesto"):
                    repo.delete_budget(row["budget_id"])
                    ui.flash(f"«{row['Material']}» quitado del presupuesto de {site_name}.", "🗑️")
                    st.rerun()


def _tab_workers(site: dict) -> None:
    workers = repo.list_workers()
    workers = workers[workers["project_site_id"] == site["id"]] if not workers.empty else workers
    if workers.empty:
        st.info("Nadie está asignado a esta obra. Asigna trabajadores en el módulo Trabajadores.")
        return
    today = date.today()
    attendance = repo.list_attendance((today - timedelta(days=29)).isoformat(), today.isoformat())
    worked = {}
    if not attendance.empty:
        ok = attendance[(attendance["project_site_id"] == site["id"]) & attendance["status"].isin(["presente", "tardanza"])]
        worked = ok.groupby("worker_id").size().to_dict()

    st.caption(f"{len(workers)} trabajador(es) asignado(s) · jornadas = días presentes en esta obra en los últimos 30 días")
    for w in workers.to_dict("records"):
        with st.container(border=True):
            c1, c2 = st.columns([4, 3])
            with c1:
                sub = " · ".join(x for x in [w.get("position"), w.get("group_name")] if x) or "Sin puesto"
                st.markdown(ui.row_name_sub(ui.avatar(w["full_name"]), w["full_name"], sub), unsafe_allow_html=True)
            with c2:
                n = int(worked.get(w["id"], 0))
                st.markdown(ui.pill(f"{n} jornada{'s' if n != 1 else ''}", "green" if n else "gray"), unsafe_allow_html=True)
                st.markdown(ui.contact_links(w.get("phone"), None), unsafe_allow_html=True)


def _tab_progress(site: dict, df: pd.DataFrame, prog: dict) -> None:
    if df.empty or not prog["planned"]:
        st.info("Define el presupuesto de la obra (pestaña Materiales) para ver su progreso.")
        return
    overall = prog["pct_consumed"] or 0.0
    st.markdown(f'<div class="mrp-eyebrow">Avance de materiales</div><div class="mrp-page-title">{overall * 100:.0f}%</div>', unsafe_allow_html=True)
    st.caption("Porcentaje del presupuesto de materiales que ya se consumió en la obra (ponderado por costo).")

    def bar(label: str, value: float | None, detail: str) -> None:
        st.markdown(f"**{label}** — {detail}")
        st.progress(value if value is not None else 0.0)

    bar("Pedido", prog["pct_ordered"], f"{prog['ordered']:,.0f} de {prog['planned']:,.0f} presupuestados")
    received = float(df["Recibido $"].sum())
    bar("Recibido", prog["pct_received"], f"{received:,.0f} de {prog['ordered']:,.0f} pedidos" if prog["ordered"] else "todavía sin pedidos")
    consumed = float(df["Consumido $"].sum())
    bar("Consumido", prog["pct_consumed"], f"{consumed:,.0f} de {prog['planned']:,.0f} presupuestados")

    late = df[(df["Pedido"] > 0) & (df["Recibido"] < df["Pedido"])]
    if not late.empty:
        st.warning("Pendiente de recibir: " + ", ".join(f"{r['Material']} ({r['Pedido'] - r['Recibido']:g})" for r in late.to_dict("records")))
    over = df[(df["Presupuesto"] > 0) & (df["Pedido"] > df["Presupuesto"])]
    if not over.empty:
        st.error("Pedido por encima de lo presupuestado: " + ", ".join(over["Material"].tolist()))


def _state(row: pd.Series) -> str:
    if not row["Presupuesto"]:
        return "Fuera de presupuesto"
    if row["Pedido"] > row["Presupuesto"]:
        return "🚨 Excede lo previsto"
    if row["Pedido"] >= row["Presupuesto"]:
        return "✅ Completo"
    if row["Pedido"] == 0:
        return "Sin pedir"
    return f"{row['Pedido'] / row['Presupuesto'] * 100:.0f}% pedido"
