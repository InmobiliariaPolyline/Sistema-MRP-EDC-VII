"""Módulo de Obras: presupuesto de materiales por obra frente a lo que ya se
pidió, recibió y despachó desde el almacén."""
from datetime import date, timedelta
import math

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, inventario, materiales, ui
from utils.reports import site_report_pdf
from utils import audit
from utils.geocode import google_maps_search_url

SITE_KEY = "obras_site"
NEW_STAGE = "➕ Nueva etapa…"
NO_STAGE = "Sin etapa"
ALL_STAGES = "Todas las etapas"


def _clear_budget_draft(site_id: str) -> None:
    for key in list(st.session_state):
        if key.startswith(f"budget_{site_id}_"):
            st.session_state.pop(key, None)


def _delete_budget(budget_id: str, material_name: str, site_name: str) -> None:
    repo.delete_budget(budget_id)
    ui.flash(f"«{material_name}» quitado del presupuesto de {site_name}.", "🗑️")


def site_stages(site_id: str) -> list[str]:
    """Etapas con presupuesto en la obra (sin contar «sin etapa»), en orden alfabético."""
    budgets = repo.list_budgets(site_id)
    return sorted({str(x) for x in budgets["stage"] if x}) if not budgets.empty and "stage" in budgets.columns else []


def progress_by_material(site_id: str, stage: str | None = None) -> pd.DataFrame:
    """Por material: presupuestado, pedido, recibido, despachado y gasto, para una obra.

    `stage=None` suma todas las etapas. Con una etapa (o "" = sin etapa) solo cuentan el presupuesto y los
    despachos de esa etapa: las órdenes de compra no se asignan a etapas, así que Pedido y Recibido quedan en 0.
    Los importes de las órdenes van en soles y sin IGV."""
    budgets = repo.list_budgets(site_id)
    if stage is not None and not budgets.empty:
        budgets = budgets[budgets["stage"].fillna("") == stage]
    orders = repo.list_orders()
    orders = orders[(orders["project_site_id"] == site_id) & (orders["status"] != "cancelada")] if not orders.empty else orders
    items = repo.list_order_items()
    items = items[items["order_id"].isin(orders["id"])] if not orders.empty and not items.empty else items.iloc[0:0]
    if stage is not None:
        items = items.iloc[0:0]
    rates = dict(zip(orders["id"], orders["exchange_rate"].astype(float))) if not orders.empty else {}
    consumed = repo.site_consumption(site_id)  # ya sumado por la base: despachado − devuelto por material y etapa
    if stage is not None and not consumed.empty:
        consumed = consumed[consumed["stage"].fillna("") == stage]

    data: dict[str, dict] = {}

    def slot(material_id: str, name: str, category: str | None, unit: str | None) -> dict:
        return data.setdefault(
            material_id,
            {
                "material_id": material_id, "Material": name, "Categoría": category, "Unidad": unit,
                "Presupuesto": 0.0, "Pedido": 0.0, "Recibido": 0.0, "Despachado": 0.0,
                "Presupuesto $": 0.0, "Pedido $": 0.0, "Recibido $": 0.0, "Despachado $": 0.0,
                "budget_id": None, "planned_price": 0.0,
            },
        )

    for b in budgets.to_dict("records"):
        s = slot(b["material_id"], b["material_name"], b["category"], b["unit"])
        s["Presupuesto"] += float(b["planned_qty"])
        s["Presupuesto $"] += float(b["planned_qty"]) * float(b["planned_unit_price"])
        s["budget_id"] = b["id"]
        s["planned_price"] = s["Presupuesto $"] / s["Presupuesto"] if s["Presupuesto"] else float(b["planned_unit_price"])
    for i in items.to_dict("records"):
        if not i.get("material_id"):
            continue
        s = slot(i["material_id"], i["material_name"], None, i.get("unit"))
        s["Pedido"] += float(i["quantity"])
        s["Recibido"] += float(i["received_qty"])
        rate = rates.get(i["order_id"], 1.0)
        s["Pedido $"] += float(i["quantity"]) * float(i["unit_price"]) * rate
        s["Recibido $"] += float(i["received_qty"]) * float(i["unit_price"]) * rate
    for m in consumed.to_dict("records"):
        amount = float(m["quantity"] or 0)
        if not amount:
            continue
        s = slot(m["material_id"], m["material_name"], m["category"], m["unit"])
        s["Despachado"] += amount

    for s in data.values():  # el despacho se valora al precio presupuestado (o al promedio pedido)
        price = s["planned_price"] or (s["Pedido $"] / s["Pedido"] if s["Pedido"] else 0.0)
        s["Despachado $"] = s["Despachado"] * price

    columns = [
        "material_id", "budget_id", "Material", "Categoría", "Unidad", "Presupuesto", "Pedido", "Recibido",
        "Despachado", "Presupuesto $", "Pedido $", "Recibido $", "Despachado $", "planned_price",
    ]
    df = pd.DataFrame(list(data.values()))
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns].sort_values("Material").reset_index(drop=True) if not df.empty else df


@st.dialog("Material del presupuesto")
def _budget_dialog(site_id: str, site_name: str) -> None:
    forms.header(f"Presupuesto de {site_name}", "Define la cantidad y el precio estimado de un material para comparar después con las compras.")
    ui.tip("Ejemplo: Concreto, 20 m³ previstos a 120.00 c/u. El precio se propone con el mejor de tus proveedores.")
    materials = repo.list_materials()
    if materials.empty:
        ui.empty_state("Faltan materiales", "Registra un material en el catálogo y vuelve para añadirlo al presupuesto.")
        if st.button("Cancelar", key="budget_cancel_empty", width="stretch"):
            _clear_budget_draft(site_id)
            st.rerun()
        return
    offers = repo.list_offers()
    options = {f"{r['category']} · {r['name']}": r for r in materials.to_dict("records")}
    forms.section("1. Material", "Si ya está presupuestado, guardar actualizará su cantidad y precio.")
    choice = st.selectbox("Material", list(options), key=f"budget_{site_id}_material")
    material = options[choice]

    budgets = repo.list_budgets(site_id)
    stages = site_stages(site_id)
    stage_options = [NO_STAGE, *stages, NEW_STAGE]
    stage_pick = st.selectbox(
        "Etapa de la obra (opcional)", stage_options, key=f"budget_{site_id}_stage",
        help="Para presupuestar por fases (cimentación, estructura, acabados…). El mismo material puede estar en varias etapas.",
    )
    stage = ""
    if stage_pick == NEW_STAGE:
        stage = st.text_input("Nombre de la etapa nueva", placeholder="Ej. Cimentación", max_chars=60, key=f"budget_{site_id}_stage_new").strip()
    elif stage_pick != NO_STAGE:
        stage = stage_pick
    current = budgets[(budgets["material_id"] == material["id"]) & (budgets["stage"].fillna("") == stage)]
    planned_qty = float(current.iloc[0]["planned_qty"]) if not current.empty else 0.0
    if not current.empty:
        suggested = float(current.iloc[0]["planned_unit_price"])
        st.caption(f"Actualmente: {planned_qty:g} {material['metric_label'] or 'unid.'} × {suggested:,.2f}. Guardar reemplaza estos valores.")
    else:
        prices = offers[(offers["material_id"] == material["id"]) & offers["price"].notna()]["price"].astype(float)
        prices = prices[prices > 0]
        suggested = float(prices.min()) if not prices.empty else 0.0

    forms.section("2. Cantidad y precio", "Usa la unidad del material. El precio puede quedar en 0 si aún no tienes una estimación.")
    c1, c2 = st.columns(2)
    qty_label = f"Cantidad prevista ({material['metric_label'] or 'unid.'})"
    skey = stage_pick if stage_pick != NEW_STAGE else f"new_{stage}"
    qty = c1.number_input(qty_label, min_value=0.0, value=planned_qty, step=1.0, key=f"budget_{site_id}_qty_{material['id']}_{skey}",
                          help="Cantidad total que esperas usar en esta obra; debe ser mayor que 0 y puede tener decimales.")
    price = c2.number_input("Precio unit. estimado", min_value=0.0, value=suggested, step=0.1, format="%.2f", key=f"budget_{site_id}_price_{material['id']}_{skey}",
                            help="Se propone el mejor precio entre tus proveedores para materiales nuevos. Puedes ajustarlo; 0 = sin precio estimado.")
    forms.section("3. Revisa el presupuesto", "Comprueba el costo previsto antes de guardar.")
    total = sum(float(r["planned_qty"]) * float(r["planned_unit_price"]) for r in budgets.to_dict("records"))
    previous_cost = planned_qty * suggested if not current.empty else 0.0
    material_cost, site_cost = st.columns(2)
    material_cost.metric("Costo del material", f"{qty * price:,.2f}")
    site_cost.metric("Presupuesto después", f"{total - previous_cost + qty * price:,.2f}")
    if price == 0:
        st.caption("Con precio 0, este material queda presupuestado en cantidad y no suma costo al total.")
    cancel, save = st.columns([1, 2])
    if cancel.button("Cancelar", key="budget_cancel", width="stretch"):
        _clear_budget_draft(site_id)
        st.rerun()
    if save.button("Guardar en el presupuesto", type="primary", width="stretch"):
        issues = forms.validate({qty_label: qty, "Precio unit. estimado": price})
        if not math.isfinite(qty * price):
            issues.append("Costo previsto: revisa la cantidad y el precio para obtener un total finito.")
        if stage_pick == NEW_STAGE and not stage:
            issues.append("Nombre de la etapa nueva: escribe cómo se llama la etapa.")
        if forms.errors(issues):
            return
        try:
            repo.set_budget(site_id, material["id"], qty, price, stage)
        except ValueError as exc:
            st.error(f"No se pudo guardar el presupuesto: {exc}")
            return
        _clear_budget_draft(site_id)
        summary = f"Presupuesto de «{site_name}»{f' · {stage}' if stage else ''}: {material['name']}"
        if current.empty:
            ui.flash(f"{summary} × {qty:g}.", "🧮")
        else:
            changes = audit.diff(
                {"qty": float(current.iloc[0]["planned_qty"]), "price": float(current.iloc[0]["planned_unit_price"])},
                {"qty": qty, "price": price}, {"qty": "Cantidad prevista", "price": "Precio estimado"},
            )
            ui.log_change(summary, "presupuesto", str(current.iloc[0]["id"]), changes, icon="🧮")
            if not changes:
                ui.flash(f"{summary}: sin cambios.", "🧮", log=False)
        st.rerun()


def site_report_stages(site_id: str) -> list[dict]:
    """Presupuesto y despachado (en soles) de cada etapa de la obra, para el reporte. Vacío si la obra no usa etapas."""
    stages = site_stages(site_id)
    if not stages:
        return []
    out = []
    for stage in [*stages, ""]:
        df = progress_by_material(site_id, stage)
        budget = float(df["Presupuesto $"].sum()) if not df.empty else 0.0
        dispatched = float(df["Despachado $"].sum()) if not df.empty else 0.0
        if stage == "" and not budget and not dispatched:
            continue
        out.append({"stage": stage, "budget": budget, "dispatched": dispatched})
    return out


def site_report(site: dict, df: pd.DataFrame, prog: dict) -> bytes:
    """PDF de la obra: resumen, materiales, etapas y vales."""
    vouchers = repo.list_dispatches(limit=1000)
    vouchers = vouchers[vouchers["project_site_id"] == site["id"]] if not vouchers.empty else vouchers
    workers = repo.list_workers()
    n_workers = int((workers["project_site_id"] == site["id"]).sum()) if not workers.empty else 0
    return site_report_pdf(site, prog, df, site_report_stages(site["id"]), vouchers, n_workers)


def site_progress(df: pd.DataFrame) -> dict:
    """Porcentajes de avance de una obra (ponderados por costo)."""
    if df.empty:
        return {"planned": 0.0, "ordered": 0.0, "pct_ordered": None, "pct_received": None, "pct_consumed": None}
    planned = float(df["Presupuesto $"].sum())
    ordered = float(df["Pedido $"].sum())
    received = float(df["Recibido $"].sum())
    consumed_capped = float(df[["Despachado $", "Presupuesto $"]].min(axis=1).sum())
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
        ui.empty_state("Aún no hay obras", "Crea una obra en Trabajadores → Obras / Proyectos para definir su presupuesto y seguir el avance.", icon="🏗️")
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
            ui.stat_card("⚖️", f"{prog['planned'] - prog['ordered']:,.0f}", "Saldo del presupuesto", "presupuesto − pedido"),
            ui.stat_card("📐", over, "Sobre lo presupuestado", "materiales pedidos por encima de lo previsto", warn=over > 0),
        ]
    )

    st.download_button(
        "📄 Reporte de la obra (PDF)", data=site_report(site, df, prog), file_name=f"reporte_obra_{site_name.replace(' ', '_')}.pdf",
        mime="application/pdf", key=f"site_report_{site_id}",
        help="Presupuesto frente a lo pedido, recibido y despachado, por material y por etapa, con los vales de salida. Listo para imprimir.",
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
    if pd.isna(lat_raw) or pd.isna(lon_raw):
        ui.empty_state("Ubicación sin registrar", "Esta obra tiene información disponible, pero aún no tiene coordenadas para mostrar el mapa.", icon="📍")
        return
    try:
        lat, lon = float(lat_raw), float(lon_raw)
    except (TypeError, ValueError):
        st.warning("Revisa las coordenadas registradas: no se puede mostrar esta ubicación.")
        return
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        st.warning("Las coordenadas registradas están fuera del rango válido del mapa.")
        return
    st.map(pd.DataFrame([{"lat": lat, "lon": lon}]), zoom=16)
    st.caption(f"Coordenadas: {lat:.6f}, {lon:.6f}")
    url = google_maps_search_url(coords=(lat, lon))
    st.markdown(f'<a class="mrp-link" href="{url}" target="_blank" rel="noopener">🗺️ Abrir en Google Maps</a>', unsafe_allow_html=True)


def _tab_materials(site: dict, df: pd.DataFrame) -> None:
    site_id, site_name = site["id"], site["name"]
    ui.tip("Primero define lo que esperas usar con «＋ Material al presupuesto». Luego verás cuánto llevas pedido, recibido y despachado.")
    b1, b2, b3, _ = st.columns([2, 2, 2, 2])
    if b1.button("＋ Material al presupuesto", type="primary", width="stretch"):
        _clear_budget_draft(site_id)
        _budget_dialog(site_id, site_name)
    if b2.button("🚚 Despachar material", width="stretch", help="Saca material del almacén hacia esta obra y genera el vale de salida."):
        inventario.dispatch_dialog(default_site_id=site_id)
    if b3.button("↩️ Devolver material", width="stretch", help="El material que sobra en esta obra vuelve al almacén."):
        inventario._clear_return_draft()
        inventario.return_dialog(default_site_id=site_id)

    stages = site_stages(site_id)
    stage_view = None
    if stages:
        pick = st.selectbox(
            "Etapa", [ALL_STAGES, NO_STAGE, *stages], key=f"obra_stage_{site_id}",
            help="Ver el presupuesto y lo despachado de una etapa. «Todas las etapas» suma todo, incluidos los pedidos.",
        )
        stage_view = None if pick == ALL_STAGES else ("" if pick == NO_STAGE else pick)
        if stage_view is not None:
            df = progress_by_material(site_id, stage_view)
            st.caption("Las órdenes de compra no se asignan a etapas: aquí se comparan solo el presupuesto y lo despachado de la etapa.")

    if df.empty:
        ui.empty_state("Aún no hay materiales en esta obra", "Añade un material al presupuesto o crea una orden con esta obra como destino.")
        return

    ui.result_count(len(df), len(df), noun="materiales")
    view = df.copy()
    view["Estado"] = view.apply(_state, axis=1)
    view["Despachado %"] = view.apply(lambda r: min(r["Despachado"] / r["Presupuesto"] * 100, 100) if r["Presupuesto"] else 0, axis=1)
    shown = ["Material", "Unidad", "Presupuesto", "Pedido", "Recibido", "Despachado", "Despachado %", "Presupuesto $", "Pedido $", "Estado"]
    if stage_view is not None:
        shown = ["Material", "Unidad", "Presupuesto", "Despachado", "Despachado %", "Presupuesto $", "Despachado $"]
    st.dataframe(
        view[shown],
        hide_index=True,
        width="stretch",
        column_config={
            "Presupuesto": st.column_config.NumberColumn(format="%.2f"),
            "Pedido": st.column_config.NumberColumn(format="%.2f"),
            "Recibido": st.column_config.NumberColumn(format="%.2f"),
            "Despachado": st.column_config.NumberColumn(format="%.2f"),
            "Despachado %": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
            "Presupuesto $": st.column_config.NumberColumn(format="%.2f"),
            "Pedido $": st.column_config.NumberColumn(format="%.2f"),
            "Despachado $": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.markdown("**Consulta la ficha de un material**")
    names = {r["Material"]: r["material_id"] for r in df.to_dict("records")}
    i1, i2 = st.columns([4, 2])
    chosen = i1.selectbox("Material", list(names), key=f"obra_mat_info_{site_id}", help="Abre su ficha para consultar especificaciones y proveedores.")
    if i2.button("ℹ️ Ver ficha", width="stretch", key=f"obra_mat_btn_{site_id}"):
        materiales.info_dialog(names[chosen])

    budgeted = repo.list_budgets(site_id)
    if not budgeted.empty:
        with st.expander("Quitar materiales del presupuesto"):
            for row in budgeted.to_dict("records"):
                c1, c2 = st.columns([6, 1])
                where = f" · etapa {row['stage']}" if row.get("stage") else ""
                c1.write(f"{row['material_name']} · {float(row['planned_qty']):g} {row['unit'] or ''}{where}")
                if c2.button("🗑", key=f"del_budget_{row['id']}", help="Quitar del presupuesto"):
                    ui.confirm_delete(
                        f"¿Quitar «{row['material_name']}»{where} del presupuesto de «{site_name}»? Se eliminará su cantidad y costo previstos. Sus pedidos y despachos se conservan.",
                        lambda bid=row["id"], name=row["material_name"], sn=site_name: _delete_budget(bid, name, sn),
                    )


def _tab_workers(site: dict) -> None:
    workers = repo.list_workers()
    workers = workers[workers["project_site_id"] == site["id"]] if not workers.empty else workers
    if workers.empty:
        ui.empty_state("Esta obra no tiene trabajadores asignados", "Asigna trabajadores desde el módulo Trabajadores para ver aquí sus jornadas.", icon="👷")
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
        ui.empty_state("Falta un presupuesto con costo", "En Materiales, define cantidades y precios estimados para calcular el progreso de la obra.", icon="📈")
        return
    overall = prog["pct_consumed"] or 0.0
    st.markdown(f'<div class="mrp-eyebrow">Avance de materiales</div><div class="mrp-page-title">{overall * 100:.0f}%</div>', unsafe_allow_html=True)
    st.caption("Porcentaje del presupuesto de materiales que ya se despachó a la obra desde el almacén (ponderado por costo).")

    def bar(label: str, value: float | None, detail: str) -> None:
        st.markdown(f"**{label}** — {detail}")
        st.progress(value if value is not None else 0.0)

    bar("Pedido", prog["pct_ordered"], f"{prog['ordered']:,.0f} de {prog['planned']:,.0f} presupuestados")
    received = float(df["Recibido $"].sum())
    bar("Recibido", prog["pct_received"], f"{received:,.0f} de {prog['ordered']:,.0f} pedidos" if prog["ordered"] else "todavía sin pedidos")
    consumed = float(df["Despachado $"].sum())
    bar("Despachado", prog["pct_consumed"], f"{consumed:,.0f} de {prog['planned']:,.0f} presupuestados")

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
        return "Sobre lo presupuestado"
    if row["Pedido"] >= row["Presupuesto"]:
        return "✅ Completo"
    if row["Pedido"] == 0:
        return "Sin pedir"
    return f"{row['Pedido'] / row['Presupuesto'] * 100:.0f}% pedido"
