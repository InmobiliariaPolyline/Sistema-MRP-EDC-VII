"""Módulo de Obras: presupuesto de materiales por obra frente a lo que ya se
pidió, recibió y consumió."""
import pandas as pd
import streamlit as st

from db import repository as repo
from modules import inventario, ui

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
                "Presupuesto $": 0.0, "Gasto pedido $": 0.0, "budget_id": None,
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
    for m in consumed.to_dict("records"):
        if m["kind"] != "salida":
            continue
        s = slot(m["material_id"], m["material_name"], m["category"], m["unit"])
        s["Consumido"] += float(m["quantity"])

    columns = [
        "material_id", "budget_id", "Material", "Categoría", "Unidad", "Presupuesto", "Pedido", "Recibido",
        "Consumido", "Presupuesto $", "Gasto pedido $", "planned_price",
    ]
    df = pd.DataFrame(list(data.values()))
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns].sort_values("Material").reset_index(drop=True) if not df.empty else df


@st.dialog("Material del presupuesto")
def _budget_dialog(site_id: str, site_name: str) -> None:
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


def render() -> None:
    sites = repo.list_project_sites()
    ui.page_header(
        "Control de obra",
        "Obras y presupuesto",
        "Qué materiales se planea usar en cada obra y cuánto llevas pedido, recibido y consumido.",
    )
    if sites.empty:
        st.info("Todavía no hay obras. Se crean en Trabajadores → Obras / Proyectos.")
        return

    names = sites["name"].tolist()
    site_name = st.selectbox("Obra", names, key=SITE_KEY)
    site_id = sites.loc[sites["name"] == site_name, "id"].iloc[0]

    df = progress_by_material(site_id)
    budget_total = float(df["Presupuesto $"].sum()) if not df.empty else 0.0
    spent = float(df["Gasto pedido $"].sum()) if not df.empty else 0.0
    over = int(((df["Pedido"] > df["Presupuesto"]) & (df["Presupuesto"] > 0)).sum()) if not df.empty else 0
    pct = f"{spent / budget_total * 100:.0f}% del presupuesto" if budget_total else "sin presupuesto"
    ui.stat_grid(
        [
            ui.stat_card("🧮", f"{budget_total:,.0f}", "Presupuesto", "costo previsto de materiales"),
            ui.stat_card("🧾", f"{spent:,.0f}", "Pedido hasta hoy", pct, warn=budget_total > 0 and spent > budget_total),
            ui.stat_card("⚖️", f"{budget_total - spent:,.0f}", "Disponible", "presupuesto − pedido"),
            ui.stat_card("🚨", over, "Materiales excedidos", "pedido > presupuesto", warn=over > 0),
        ]
    )

    b1, b2, _ = st.columns([2, 2, 4])
    if b1.button("＋ Material al presupuesto", type="primary", use_container_width=True):
        _budget_dialog(site_id, site_name)
    if b2.button("📤 Registrar consumo", use_container_width=True):
        inventario.movement_dialog(default_site_id=site_id)

    if df.empty:
        st.info("Esta obra todavía no tiene presupuesto ni pedidos. Añade materiales con «＋ Material al presupuesto».")
        return

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Seguimiento</div><div class="mrp-panel-title">Presupuesto vs. ejecutado</div>', unsafe_allow_html=True)

    view = df.copy()
    view["Estado"] = view.apply(_state, axis=1)
    st.dataframe(
        view[["Material", "Unidad", "Presupuesto", "Pedido", "Recibido", "Consumido", "Presupuesto $", "Gasto pedido $", "Estado"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Presupuesto": st.column_config.NumberColumn(format="%.2f"),
            "Pedido": st.column_config.NumberColumn(format="%.2f"),
            "Recibido": st.column_config.NumberColumn(format="%.2f"),
            "Consumido": st.column_config.NumberColumn(format="%.2f"),
            "Presupuesto $": st.column_config.NumberColumn(format="%.2f"),
            "Gasto pedido $": st.column_config.NumberColumn(format="%.2f"),
        },
    )

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
