"""Módulo de Inventario: stock del almacén, despachos a obra con su vale de salida y
el historial de movimientos.

El flujo de la empresa es: el material llega del proveedor al almacén (entrada,
por recepción de una orden) y sale hacia una obra cuando alguien lo pide en
persona (despacho, con vale). Lo que sobra puede volver de la obra (devolución) y
el stock del sistema se contrasta con lo que hay en estantería (toma de inventario).
La merma o una entrada de ajuste son casos aparte."""
import pandas as pd
import streamlit as st

from db import repository as repo
from modules import attachments_ui, forms, ui
from utils import kardex
from utils.mail import mailto_url
from utils.reports import dispatch_pdf, dispatch_text, to_excel, to_pdf
from utils.timeago import time_ago
from utils import clock

ENTRY = "Entrada (ajuste / compra directa)"
LOSS = "Merma o salida sin obra (préstamo, pérdida…)"
SUPPLIER_RETURN = "Devolución a un proveedor (sale del almacén)"
OTHER_PERSON = "Otra persona (escribir el nombre)"

TYPE_LABELS = {
    "recepcion": ("Recepción", "green"),
    "despacho": ("Despacho", "blue"),
    "entrada_manual": ("Entrada", "green"),
    "merma": ("Merma", "amber"),
    "devolucion": ("Devolución de obra", "green"),
    "devolucion_proveedor": ("Devolución a proveedor", "amber"),
    "conteo": ("Toma de inventario", "purple"),
}
LINES_KEY = "_dispatch_lines"
DONE_KEY = "_dispatch_done"


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

def stock_by_material() -> pd.DataFrame:
    """Entradas, salidas y stock actual de los materiales con movimientos o con stock mínimo."""
    columns = ["material_id", "material_name", "category", "unit", "min_stock", "entradas", "salidas", "stock"]
    levels = repo.stock_levels()
    if levels.empty:
        return pd.DataFrame(columns=columns)
    levels = levels.assign(
        entradas=levels["entradas"].astype(float), salidas=levels["salidas"].astype(float),
        stock=levels["stock"].astype(float), min_stock=levels["min_stock"].astype(float),
    )
    active = levels[(levels["entradas"] + levels["salidas"] > 0) | (levels["min_stock"] > 0)]
    return active[columns].reset_index(drop=True)


def stock_state(row: dict) -> tuple[str, str]:
    """Texto y color de la pastilla de stock de un material."""
    stock, minimum = float(row["stock"]), float(row.get("min_stock") or 0)
    if stock <= 0:
        return "Agotado", "red"
    if minimum > 0 and stock <= minimum:
        return f"{stock:g} · stock bajo", "amber"
    return f"{stock:g} en stock", "green"


def budget_status(site_id: str, material_id: str, extra: float, stage: str | None = None) -> dict | None:
    """Presupuesto de un material en una obra frente a lo ya despachado y lo que se quiere despachar.
    Con `stage` (nombre de etapa) se compara solo con el presupuesto y los despachos de esa etapa."""
    budgets = repo.list_budgets(site_id)
    row = budgets[budgets["material_id"] == material_id] if not budgets.empty else budgets
    used = repo.site_consumption(site_id, material_id)
    if stage:
        row = row[row["stage"].fillna("") == stage] if not row.empty else row
        used = used[used["stage"].fillna("") == stage] if not used.empty else used
    sent = float(used["quantity"].astype(float).sum()) if not used.empty else 0.0
    if row.empty:
        return {"budgeted": False, "planned": 0.0, "sent": sent, "after": sent + extra}
    planned = float(row["planned_qty"].astype(float).sum())
    return {"budgeted": True, "planned": planned, "sent": sent, "after": sent + extra, "over": sent + extra > planned + 1e-9}


# ---------------------------------------------------------------------------
# Despacho a obra (con vale de salida)
# ---------------------------------------------------------------------------

def _clear_dispatch_draft() -> None:
    st.session_state.pop(LINES_KEY, None)
    st.session_state.pop(DONE_KEY, None)
    for key in ("dispatch_site", "dispatch_person", "dispatch_other", "dispatch_note", "dispatch_material", "dispatch_qty", "dispatch_stage"):
        st.session_state.pop(key, None)


def _site_stages(site_id: str) -> list[str]:
    """Etapas con presupuesto en una obra (para elegir la etapa de un despacho)."""
    budgets = repo.list_budgets(site_id)
    return sorted({str(x) for x in budgets["stage"] if x}) if not budgets.empty and "stage" in budgets.columns else []


def _show_dispatch_result(code: str) -> None:
    vouchers = repo.list_dispatches()
    voucher = vouchers[vouchers["code"] == code]
    st.success(f"Despacho registrado: vale **{code}**. El stock del almacén ya se descontó.", icon=":material/check_circle:")
    if not voucher.empty:
        record = voucher.iloc[0].to_dict()
        lines = repo.list_dispatch_lines(record["id"])
        st.download_button(
            "Descargar el vale en PDF", data=dispatch_pdf(record, lines), file_name=f"{code}.pdf", mime="application/pdf",
            type="primary", width="stretch", icon=":material/picture_as_pdf:",
        )
        st.caption("Imprímelo para que quien recibe el material lo firme.")
    if st.button("Cerrar", width="stretch", key="dispatch_close"):
        _clear_dispatch_draft()
        st.rerun()


@st.dialog("Despachar material a una obra", width="large")
def dispatch_dialog(default_site_id: str | None = None) -> None:
    """Saca material del almacén hacia una obra y genera el vale. También se usa desde Obras."""
    done = st.session_state.get(DONE_KEY)
    if done:
        _show_dispatch_result(done)
        return

    forms.header(
        "Registrar un despacho",
        "El obrero pide el material en persona: indica la obra, quién lo pide y qué se lleva. Al confirmar se descuenta del almacén y se genera el vale de salida.",
    )
    sites = repo.list_project_sites()
    if sites.empty:
        ui.empty_state("Faltan obras", "Registra una obra (Trabajadores → Obras / Proyectos) para poder despachar material.", "🏗️")
        return
    levels = stock_by_material()
    available = levels[levels["stock"] > 0]
    if available.empty:
        ui.empty_state("No hay stock para despachar", "Recibe una orden de compra o registra una entrada para que haya material disponible.", "📦")
        return
    lines: list[dict] = st.session_state.setdefault(LINES_KEY, [])

    forms.section("1. Obra y solicitante", "Quién recibe el material queda anotado en el vale.")
    names = sites["name"].tolist()
    if default_site_id and "dispatch_site" not in st.session_state:
        matched = sites[sites["id"] == default_site_id]
        if not matched.empty:
            st.session_state["dispatch_site"] = matched.iloc[0]["name"]
    site_name = st.selectbox("Obra destino", names, key="dispatch_site", help="Adónde se envía el material.")
    site_id = sites.loc[sites["name"] == site_name, "id"].iloc[0]

    workers = repo.list_workers()
    workers = workers[workers["active"].fillna(True).astype(bool)] if not workers.empty else workers
    in_site = workers[workers["project_site_id"] == site_id]["full_name"].tolist() if not workers.empty else []
    others = [n for n in (workers["full_name"].tolist() if not workers.empty else []) if n not in in_site]
    person = st.selectbox("Solicitante", in_site + others + [OTHER_PERSON], key="dispatch_person",
                          help="Primero aparecen los trabajadores asignados a esa obra.")
    requested_by, worker_id = person, None
    if person == OTHER_PERSON:
        requested_by = st.text_input("Nombre del solicitante", placeholder="Ej. Juan Pérez", max_chars=forms.RULES["Nombre del solicitante"]["max"], key="dispatch_other")
    elif not workers.empty:
        worker_id = workers.loc[workers["full_name"] == person, "id"].iloc[0]
    stages = _site_stages(site_id)
    stage = None
    if stages:
        pick = st.selectbox("Etapa de la obra (opcional)", ["Sin etapa", *stages], key="dispatch_stage",
                            help="Para controlar lo despachado contra el presupuesto de esa etapa.")
        stage = None if pick == "Sin etapa" else pick
    note = st.text_input("Nota del vale (opcional)", placeholder="Ej. Para el vaciado de losa del piso 3", max_chars=500, key="dispatch_note")

    forms.section("2. Materiales", "Solo aparecen materiales con stock. Puedes agregar varios al mismo vale.")
    options = {f"{r['category']} · {r['material_name']}  (hay {r['stock']:g} {r['unit'] or ''})": r for r in available.to_dict("records")}
    choice = st.selectbox("Material", list(options), key="dispatch_material")
    material = options[choice]
    in_vale = sum(l["quantity"] for l in lines if l["material_id"] == material["material_id"])
    remaining = float(material["stock"]) - in_vale
    qty = st.number_input(f"Cantidad ({material['unit'] or 'unid.'})", min_value=0.0, value=1.0, step=1.0, key="dispatch_qty",
                          help=f"Disponible para este vale: {remaining:g}.")
    info = budget_status(site_id, material["material_id"], in_vale + qty, stage)
    if info and not info["budgeted"]:
        st.info("Este material no está en el presupuesto de la obra: el despacho se puede hacer, pero quedará fuera de presupuesto.", icon=":material/info:")
    elif info and info.get("over"):
        st.warning(
            f"Con este despacho la obra pasa lo presupuestado: previsto {info['planned']:g}, ya despachado {info['sent']:g}, quedaría en {info['after']:g}.",
            icon=":material/warning:",
        )
    elif info:
        st.caption(f"Presupuesto de la obra: {info['planned']:g} · ya despachado {info['sent']:g} · quedaría en {info['after']:g}.")

    if st.button(":material/add: Agregar al vale", width="stretch", key="dispatch_add"):
        issues = forms.validate({"Cantidad": qty})
        if qty > remaining + 1e-9:
            issues.append(f"Cantidad: solo quedan {remaining:g} {material['unit'] or 'unid.'} disponibles para este vale.")
        if not forms.errors(issues):
            existing = next((l for l in lines if l["material_id"] == material["material_id"]), None)
            if existing:
                existing["quantity"] += qty
            else:
                lines.append({"material_id": material["material_id"], "material_name": material["material_name"], "unit": material["unit"], "quantity": qty})
            st.rerun(scope="fragment")

    forms.section("3. Revisa y confirma", "Comprueba el material antes de registrar el despacho.")
    if not lines:
        st.caption("Todavía no agregaste materiales al vale.")
    for index, line in enumerate(lines):
        left, right = st.columns([6, 1], vertical_alignment="center")
        left.write(f"**{line['material_name']}** · {line['quantity']:g} {line['unit'] or ''}")
        if right.button(":material/close:", key=f"dispatch_del_{index}", help="Quitar del vale"):
            lines.pop(index)
            st.rerun(scope="fragment")

    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key="dispatch_cancel", width="stretch"):
        _clear_dispatch_draft()
        st.rerun()
    if save.button("Registrar despacho y generar vale", type="primary", width="stretch", disabled=not lines, key="dispatch_save"):
        issues = forms.validate({"Nota del vale (opcional)": note})
        if person == OTHER_PERSON:
            issues += forms.validate({"Nombre del solicitante": requested_by})
        if forms.errors(issues):
            return
        try:
            code = repo.create_dispatch(site_id, worker_id, (requested_by or "").strip() or None, note.strip() or None, lines, ui.current_actor(), stage)
        except ValueError as exc:
            st.error(f"No se pudo registrar el despacho: {exc}")
            return
        ui.log(f"Despacho {code} a «{site_name}»{f' · etapa {stage}' if stage else ''} ({len(lines)} material(es)) solicitado por {requested_by or 'sin indicar'}.")
        st.session_state[LINES_KEY] = []
        st.session_state[DONE_KEY] = code
        st.rerun(scope="fragment")


@st.dialog("Detalle del vale", width="large")
def voucher_dialog(voucher: dict) -> None:
    lines = repo.list_dispatch_lines(voucher["id"])
    st.markdown(f"**{voucher['code']}** · {voucher['site_name']}")
    st.caption(f"{clock.local(voucher['created_at'])} · registrado por {voucher.get('actor') or 'sistema'}")
    st.write(f"**Solicitado por:** {voucher.get('requested_by') or 'sin indicar'}")
    if voucher.get("stage"):
        st.write(f"**Etapa de la obra:** {voucher['stage']}")
    if voucher.get("note"):
        st.write(f"**Nota:** {voucher['note']}")
    st.dataframe(
        lines[["material_name", "unit", "quantity"]].rename(columns={"material_name": "Material", "unit": "Unidad", "quantity": "Cantidad"}),
        hide_index=True, width="stretch",
    )
    st.download_button(
        "Descargar el vale en PDF", data=dispatch_pdf(voucher, lines), file_name=f"{voucher['code']}.pdf", mime="application/pdf",
        type="primary", width="stretch", icon=":material/picture_as_pdf:",
    )
    st.link_button(
        "Enviar por correo", mailto_url(None, f"Vale de salida {voucher['code']} - {voucher['site_name']}", dispatch_text(voucher, lines)),
        width="stretch", icon=":material/mail:",
        help="Abre tu programa de correo con el mensaje escrito; adjunta el PDF descargado.",
    )
    attachments_ui.render("vale", voucher["id"], key=f"vale_{voucher['id']}")


# ---------------------------------------------------------------------------
# Otros movimientos: entrada de ajuste y merma
# ---------------------------------------------------------------------------

def _clear_movement_draft() -> None:
    for field in ("kind", "material", "qty", "note"):
        st.session_state.pop(f"move_{field}", None)


@st.dialog("Entrada de ajuste o merma")
def movement_dialog() -> None:
    """Entrada manual (ajuste de conteo, compra directa) o salida sin obra (merma, préstamo)."""
    forms.header("Registra una entrada, una merma o una devolución a proveedor", "Las recepciones de órdenes ya suman al stock solas, los despachos a obra tienen su propio vale y lo que vuelve de una obra se registra en «Devolver de una obra».")
    materials = repo.list_materials()
    if materials.empty:
        ui.empty_state("Faltan materiales", "Registra un material en el catálogo para comenzar a controlar el stock.")
        return
    stock = repo.stock_levels().set_index("material_id")["stock"].to_dict()

    forms.section("1. Tipo y material", "Una entrada suma stock; una merma o una devolución a proveedor lo descuentan.")
    kind = st.radio("Tipo de movimiento", [ENTRY, LOSS, SUPPLIER_RETURN], key="move_kind")
    options = {f"{r['category']} · {r['name']}": r for r in materials.to_dict("records")}
    choice = st.selectbox("Material", list(options), key="move_material", help="Verifica la unidad antes de indicar la cantidad.")
    material = options[choice]
    available = float(stock.get(material["id"], 0.0))
    st.caption(f"Stock actual: **{available:g}** {material['metric_label'] or ''}")

    forms.section("2. Cantidad y motivo", "Puedes usar decimales. Una merma debe estar cubierta por el stock actual.")
    qty = st.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, key="move_qty",
                          help=f"Unidad: {material['metric_label'] or 'unid.'}. Debe ser mayor que 0.")
    note = st.text_input("Nota (opcional)", placeholder="Ej. Ajuste por conteo / material dañado en transporte", max_chars=500, key="move_note")

    outgoing = kind != ENTRY
    after = available - qty if outgoing else available + qty
    before_col, after_col = st.columns(2)
    before_col.metric("Stock actual", f"{available:g} {material['metric_label'] or 'unid.'}")
    after_col.metric("Stock después", f"{after:g} {material['metric_label'] or 'unid.'}")
    if outgoing and qty > available:
        st.warning(f"Reduce la cantidad: solo hay {available:g} {material['metric_label'] or 'unid.'} disponibles.")
    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key="move_cancel", width="stretch"):
        _clear_movement_draft()
        st.rerun()
    if save.button("Guardar movimiento", type="primary", width="stretch"):
        issues = forms.validate({"Cantidad": qty, "Nota (opcional)": note})
        if forms.errors(issues):
            return
        try:
            repo.add_movement(
                material["id"], "entrada" if kind == ENTRY else "salida", qty, None, note.strip() or None, ui.current_actor(),
                movement_type="devolucion_proveedor" if kind == SUPPLIER_RETURN else None,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        verb = {ENTRY: "Entrada", LOSS: "Merma", SUPPLIER_RETURN: "Devolución a proveedor"}[kind]
        _clear_movement_draft()
        ui.flash(f"{verb} de {qty:g} × {material['name']} registrada.", ":material/inventory_2:")
        st.rerun()


# ---------------------------------------------------------------------------
# Devolución de material desde una obra
# ---------------------------------------------------------------------------

def held_by_site(site_id: str) -> pd.DataFrame:
    """Material que una obra tiene en su poder: despachado menos devuelto (solo lo mayor que 0)."""
    used = repo.site_consumption(site_id)
    columns = ["material_id", "material_name", "category", "unit", "held"]
    if used.empty:
        return pd.DataFrame(columns=columns)
    used = used.assign(quantity=used["quantity"].astype(float))
    rows = [
        {"material_id": mid, "material_name": g.iloc[0]["material_name"], "category": g.iloc[0]["category"], "unit": g.iloc[0]["unit"], "held": float(g["quantity"].sum())}
        for mid, g in used.groupby("material_id")
    ]
    held = pd.DataFrame(rows, columns=columns)
    held = held[held["held"] > 1e-9]
    return held.sort_values(["category", "material_name"]).reset_index(drop=True)


def _clear_return_draft() -> None:
    for key in list(st.session_state):
        if key.startswith("return_"):
            st.session_state.pop(key, None)


@st.dialog("Devolver material de una obra", width="large")
def return_dialog(default_site_id: str | None = None) -> None:
    """Lo que sobró en la obra vuelve al almacén y suma al stock. No se puede devolver más de lo que la obra recibió."""
    forms.header("Registrar una devolución", "El material que sobra en una obra vuelve al almacén. Queda anotado quién lo devuelve y de qué obra.")
    sites = repo.list_project_sites()
    if sites.empty:
        ui.empty_state("Faltan obras", "Registra una obra para poder devolver material.", "🏗️")
        return
    forms.section("1. Obra y quién devuelve", "Solo se puede devolver lo que la obra recibió por despacho.")
    names = sites["name"].tolist()
    if default_site_id and "return_site" not in st.session_state:
        matched = sites[sites["id"] == default_site_id]
        if not matched.empty:
            st.session_state["return_site"] = matched.iloc[0]["name"]
    site_name = st.selectbox("Obra de origen", names, key="return_site")
    site_id = sites.loc[sites["name"] == site_name, "id"].iloc[0]
    returned_by = st.text_input("Quién devuelve (opcional)", placeholder="Ej. Juan Pérez", max_chars=120, key="return_by")
    note = st.text_input("Nota (opcional)", placeholder="Ej. Sobró del vaciado de losa", max_chars=500, key="return_note")
    stages = _site_stages(site_id)
    stage = None
    if stages:
        pick = st.selectbox("Etapa de la que se devuelve (opcional)", ["Sin etapa", *stages], key="return_stage",
                            help="Descuenta lo devuelto del consumo de esa etapa en el presupuesto de la obra.")
        stage = None if pick == "Sin etapa" else pick

    held = held_by_site(site_id)
    forms.section("2. Qué se devuelve", "Escribe la cantidad en los materiales que vuelven; deja en 0 el resto.")
    if held.empty:
        ui.empty_state("Esta obra no tiene material por devolver", "Aún no se le despachó nada, o ya se devolvió todo.", "📦")
        return
    table = pd.DataFrame(
        {
            "Material": held["material_name"], "Unidad": held["unit"].fillna(""), "En la obra": held["held"].astype(float),
            "Devolver": 0.0,
        }
    )
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key=f"return_editor_{site_id}", disabled=["Material", "Unidad", "En la obra"],
        column_config={
            "En la obra": st.column_config.NumberColumn(format="%g"),
            "Devolver": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%g", help="No puede superar lo que hay en la obra."),
        },
    )
    chosen = [
        {"material_id": held.iloc[i]["material_id"], "name": held.iloc[i]["material_name"], "quantity": float(row["Devolver"] or 0), "limit": float(row["En la obra"])}
        for i, row in edited.iterrows() if float(row["Devolver"] or 0) > 0
    ]
    over = [c for c in chosen if c["quantity"] > c["limit"] + 1e-9]
    for c in over:
        st.warning(f"«{c['name']}»: la obra solo tiene {c['limit']:g}.", icon=":material/warning:")
    st.caption(f"{len(chosen)} material(es) a devolver.")

    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key="return_cancel", width="stretch"):
        _clear_return_draft()
        st.rerun()
    if save.button(":material/task_alt: Registrar devolución", type="primary", width="stretch", disabled=not chosen or bool(over), key="return_save"):
        issues = forms.validate({"Nota (opcional)": note})
        if forms.errors(issues):
            return
        try:
            repo.create_return(site_id, returned_by, note, [{"material_id": c["material_id"], "quantity": c["quantity"]} for c in chosen], ui.current_actor(), stage)
        except ValueError as exc:
            st.error(f"No se pudo registrar la devolución: {exc}")
            return
        ui.log(f"Devolución de {len(chosen)} material(es) desde «{site_name}» al almacén" + (f" (devuelve {returned_by.strip()})" if returned_by.strip() else "") + ".")
        _clear_return_draft()
        ui.flash(f"Devolución registrada: {len(chosen)} material(es) volvieron al almacén desde {site_name}.", ":material/undo:")
        st.rerun()


# ---------------------------------------------------------------------------
# Toma de inventario físico
# ---------------------------------------------------------------------------

@st.dialog("Toma de inventario físico", width="large")
def count_dialog() -> None:
    """Se cuenta lo que hay en estantería, se compara con el stock del sistema y las diferencias se ajustan con su motivo."""
    forms.header(
        "Contar el almacén",
        "Cuenta una categoría a la vez. Escribe lo que realmente hay en «Contado»; los materiales que dejes vacíos no se tocan. "
        "Cada diferencia genera un ajuste con su motivo y todo queda guardado como un conteo.",
    )
    levels = repo.stock_levels()
    if levels.empty:
        ui.empty_state("No hay materiales", "Registra materiales en el catálogo para poder contarlos.")
        return
    categories = sorted(levels["category"].dropna().unique().tolist())
    forms.section("1. Qué se cuenta", "Elige la categoría y, si quieres, solo los materiales que ya tienen movimientos.")
    category = st.selectbox("Categoría", categories, key="count_category")
    only_moved = st.checkbox("Solo materiales con movimientos o stock", value=True, key="count_only_moved")
    part = levels[levels["category"] == category].copy()
    for col in ("entradas", "salidas", "stock"):
        part[col] = part[col].astype(float)
    if only_moved:
        part = part[(part["entradas"] + part["salidas"] > 0)]
    part = part.sort_values("material_name").reset_index(drop=True)
    if part.empty:
        ui.empty_state("Nada que contar aquí", "Esta categoría no tiene materiales con movimientos. Desmarca el filtro para verlos todos.", "📦")
        return

    forms.section("2. Cantidades contadas", "Solo los materiales con «Contado» lleno se ajustan.")
    table = pd.DataFrame(
        {"Material": part["material_name"], "Unidad": part["unit"].fillna(""), "Sistema": part["stock"], "Contado": pd.Series([None] * len(part), dtype="float64"), "Motivo de la diferencia": ""}
    )
    edited = st.data_editor(
        table, hide_index=True, width="stretch", height=min(520, 80 + 36 * len(table)), key=f"count_editor_{category}_{int(only_moved)}",
        disabled=["Material", "Unidad", "Sistema"],
        column_config={
            "Sistema": st.column_config.NumberColumn(format="%g"),
            "Contado": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%g", help="Lo que realmente hay. Vacío = no se cuenta."),
            "Motivo de la diferencia": st.column_config.TextColumn(max_chars=200, help="Ej. rotura, error de despacho, conteo anterior mal hecho."),
        },
    )
    counted = edited[edited["Contado"].notna()]
    diffs = counted[(counted["Contado"] - counted["Sistema"]).abs() > 1e-9]
    c1, c2, c3 = st.columns(3)
    c1.metric("Contados", len(counted))
    c2.metric("Con diferencia", len(diffs))
    c3.metric("Sin diferencia", len(counted) - len(diffs))
    if len(diffs):
        view = diffs.assign(Diferencia=diffs["Contado"] - diffs["Sistema"])[["Material", "Sistema", "Contado", "Diferencia", "Motivo de la diferencia"]]
        st.dataframe(ui.tint_frame(view, signed=["Diferencia"]), hide_index=True, width="stretch")
        if (diffs["Motivo de la diferencia"].fillna("").str.strip() == "").any():
            st.caption("Conviene anotar el motivo de cada diferencia; sirve para saber después por qué se ajustó.")
    note = st.text_input("Nota del conteo (opcional)", placeholder="Ej. Conteo mensual de octubre", max_chars=500, key="count_note")

    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key="count_cancel", width="stretch"):
        st.rerun()
    if save.button(":material/task_alt: Guardar conteo y ajustar diferencias", type="primary", width="stretch", disabled=counted.empty, key="count_save"):
        if forms.errors(forms.validate({"Nota del conteo (opcional)": note})):
            return
        lines = [
            {"material_id": part.iloc[i]["material_id"], "counted_qty": float(row["Contado"]), "reason": row["Motivo de la diferencia"] or ""}
            for i, row in counted.iterrows()
        ]
        try:
            code = repo.create_inventory_count(lines, note.strip() or None, ui.current_actor())
        except ValueError as exc:
            st.error(f"No se pudo guardar el conteo: {exc}")
            return
        ui.log(f"Toma de inventario {code} ({category}): {len(counted)} contado(s), {len(diffs)} con diferencia.")
        ui.flash(f"Conteo {code} guardado: {len(counted)} material(es) contados, {len(diffs)} ajustado(s).", ":material/calculate:")
        st.rerun()


@st.dialog("Detalle del conteo", width="large")
def count_detail_dialog(count: dict) -> None:
    lines = repo.list_count_lines(count["id"])
    st.markdown(f"**{count['code']}**")
    st.caption(f"{clock.local(count['created_at'])} · registrado por {count.get('actor') or 'sistema'}")
    if count.get("note"):
        st.write(f"**Nota:** {count['note']}")
    st.dataframe(
        ui.tint_frame(lines[["material_name", "unit", "system_qty", "counted_qty", "difference", "reason"]].rename(
            columns={"material_name": "Material", "unit": "Unidad", "system_qty": "Sistema", "counted_qty": "Contado", "difference": "Diferencia", "reason": "Motivo"}
        ), signed=["Diferencia"]),
        hide_index=True, width="stretch",
    )
    attachments_ui.render("conteo", count["id"], key=f"conteo_{count['id']}")


# ---------------------------------------------------------------------------
# Pantalla
# ---------------------------------------------------------------------------

def render() -> None:
    if ui.page_header(
        "Almacén",
        "Inventario",
        "El material llega del proveedor al almacén y sale hacia las obras con un vale de despacho.",
        action_label=":material/add: Despachar a obra",
        action_key="new_dispatch_open",
    ):
        _clear_dispatch_draft()
        dispatch_dialog()
    b1, b2, b3, _ = st.columns([2, 2, 3.4, 2])
    if b1.button("Devolver de una obra", key="new_return_open", icon=":material/undo:", width="stretch"):
        _clear_return_draft()
        return_dialog()
    if b2.button("Toma de inventario", key="new_count_open", icon=":material/fact_check:", width="stretch"):
        count_dialog()
    if b3.button("Entrada, merma o devolución a proveedor", key="new_movement_open", icon=":material/tune:", width="stretch"):
        movement_dialog()

    stock = stock_by_material()
    totals = repo.dashboard_totals()
    low = int(((stock["min_stock"] > 0) & (stock["stock"] <= stock["min_stock"])).sum()) if not stock.empty else 0
    empty = int(((stock["stock"] <= 0) & (stock["entradas"] > 0)).sum()) if not stock.empty else 0
    ui.stat_grid(
        [
            ui.stat_card("📦", totals.get("materials_in_stock", 0), "En el almacén", "materiales con stock", tone="purple"),
            ui.stat_card("🚚", totals.get("dispatches_month", 0), "Despachos del mes", "vales de salida", tone="blue"),
            ui.stat_card("⬇️", f"{float(stock['entradas'].sum()) if not stock.empty else 0:,.0f}", "Entradas", "unidades recibidas", tone="green"),
            ui.stat_card("⚠️", low, "Stock bajo", "en o bajo el mínimo", warn=low > 0),
            ui.stat_card("🚫", empty, "Agotados", "ya se acabaron", warn=empty > 0),
        ]
    )

    tab_stock, tab_vouchers, tab_counts, tab_kardex, tab_moves = st.tabs([":material/inventory_2: Stock actual", ":material/receipt_long: Vales de salida", ":material/calculate: Conteos", ":material/menu_book: Kardex", ":material/swap_vert: Movimientos"])
    with tab_stock:
        _render_stock(stock)
    with tab_vouchers:
        _render_vouchers()
    with tab_counts:
        _render_counts()
    with tab_kardex:
        _render_kardex()
    with tab_moves:
        _render_movements()


def _clear_stock_search() -> None:
    st.session_state["stock_q"] = ""


@st.dialog("Stock mínimo")
def _min_stock_dialog() -> None:
    forms.header("Define cuánto es poco", "Por debajo de este nivel el tablero avisa y la sugerencia de compra repone el material. Es solo un aviso: no cambia las existencias.")
    materials = repo.list_materials()
    if materials.empty:
        ui.empty_state("Faltan materiales", "Registra un material en el catálogo para definir su stock mínimo.")
        return
    options = {f"{r['category']} · {r['name']}": r for r in materials.sort_values(["category", "name"]).to_dict("records")}
    choice = st.selectbox("Material", list(options), key="min_stock_material", help="Escribe para buscarlo en el catálogo.")
    material = options[choice]
    unit = material.get("metric_label") or "unid."
    current = float(material.get("min_stock") or 0)
    value = st.number_input(
        f"Stock mínimo ({unit})", min_value=0.0, max_value=max(100000000.0, current), step=1.0, value=current, key=f"min_stock_value_{material['id']}",
        help="Deja 0 si no quieres alerta para este material.",
    )
    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key="min_stock_cancel", width="stretch"):
        st.rerun()
    if save.button(":material/save: Guardar mínimo", key="min_stock_save", type="primary", width="stretch"):
        if forms.errors(forms.validate({"Stock mínimo (opcional)": value})):
            return
        try:
            repo.set_min_stock(material["id"], value)
        except Exception as exc:
            ui.db_error(exc, "No se pudo guardar el stock mínimo. Inténtalo de nuevo.")
            return
        if value != current:
            ui.log_change(
                f"Stock mínimo de «{material['name']}» definido", "material", material["id"],
                [{"field": "Stock mínimo", "before": current, "after": value}], icon=":material/tune:",
            )
        st.cache_data.clear()
        st.rerun()


def _min_stock_button() -> None:
    if st.button("Stock mínimo", key="min_stock_open", icon=":material/tune:", help="Define el nivel por debajo del cual un material se marca como stock bajo."):
        _min_stock_dialog()


def _render_stock(stock: pd.DataFrame) -> None:
    _min_stock_button()
    if stock.empty:
        ui.empty_state("Aún no hay stock", "Se llena al registrar una recepción en Órdenes de compra o una entrada de ajuste. Define un stock mínimo con «Stock mínimo» para que un material aparezca aquí.")
        return
    total = len(stock)
    query = st.text_input("Buscar", placeholder="Material o categoría…", key="stock_q")
    stock = ui.filter_df(stock, query, ["material_name", "category"])
    ui.result_count(len(stock), total, noun="materiales")
    if query:
        st.button(":material/filter_alt_off: Limpiar búsqueda", key="stock_clear", on_click=_clear_stock_search)
    if stock.empty:
        ui.empty_state("Sin coincidencias", "Prueba otro nombre o limpia la búsqueda para ver todo el inventario.", icon="🔎")
        return
    stock = ui.paginate(stock, "stock_list")
    for row in stock.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 2])
            with c1:
                st.markdown(
                    ui.row_name_sub(ui.avatar(row["material_name"]), row["material_name"], f"{row['category']} · {row['unit'] or 'sin unidad'}"),
                    unsafe_allow_html=True,
                )
            with c2:
                minimum = f" · mínimo {row['min_stock']:g}" if row["min_stock"] else ""
                st.markdown(f'<div class="mrp-row-sub">entradas {row["entradas"]:g} · despachado/merma {row["salidas"]:g}{minimum}</div>', unsafe_allow_html=True)
            with c3:
                text, color = stock_state(row)
                st.markdown(ui.pill(text, color), unsafe_allow_html=True)


def _render_vouchers() -> None:
    vouchers = repo.list_dispatches()
    if vouchers.empty:
        ui.empty_state("Aún no hay vales de salida", "Cada vez que despaches material a una obra se genera un vale que podrás reimprimir aquí.", "🧾")
        return
    total = len(vouchers)
    query = st.text_input("Buscar", placeholder="Código, obra o solicitante…", key="voucher_q")
    vouchers = ui.filter_df(vouchers, query, ["code", "site_name", "requested_by"])
    ui.result_count(len(vouchers), total, noun="vales")
    if vouchers.empty:
        ui.empty_state("Sin coincidencias", "Prueba con otro código, obra o nombre.", icon="🔎")
        return
    vouchers = ui.paginate(vouchers, "voucher_list")
    for row in vouchers.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 1.6])
            with c1:
                sub = f"{row['code']} · {clock.local(row['created_at'])} · {int(row['lines_count'])} material(es)"
                st.markdown(ui.row_name_sub(ui.avatar(row["site_name"]), row["site_name"], sub), unsafe_allow_html=True)
            with c2:
                who = row.get("requested_by") or "sin solicitante"
                st.markdown(ui.pill(who, "gray"), unsafe_allow_html=True)
            with c3:
                if st.button(":material/visibility: Ver / PDF", key=f"voucher_open_{row['id']}", width="stretch"):
                    voucher_dialog(row)


def _render_kardex() -> None:
    """Todas las entradas y salidas de un material con el saldo después de cada una."""
    levels = repo.stock_levels()
    used = levels[levels["entradas"].astype(float) + levels["salidas"].astype(float) > 0] if not levels.empty else levels
    if used.empty:
        ui.empty_state("Aún no hay movimientos", "El kardex aparece cuando un material tiene entradas o salidas.", "📒")
        return
    options = {f"{r['category']} · {r['material_name']}": r for r in used.sort_values(["category", "material_name"]).to_dict("records")}
    choice = st.selectbox("Material", list(options), key="kardex_material", help="Solo aparecen materiales con movimientos.")
    material = options[choice]
    moves = repo.list_movements(limit=100000, material_id=material["material_id"])
    table = kardex.build(moves, lambda movement_type, kind: TYPE_LABELS.get(movement_type, ("Entrada" if kind == "entrada" else "Salida",))[0])
    unit = material.get("unit") or ""
    c1, c2, c3 = st.columns(3)
    c1.metric("Entradas", f"{float(table['Entrada'].fillna(0).sum()):g} {unit}")
    c2.metric("Salidas", f"{float(table['Salida'].fillna(0).sum()):g} {unit}")
    final = float(table["Saldo"].iloc[-1]) if not table.empty else 0.0
    c3.metric("Saldo", f"{final:g} {unit}")
    if abs(final - float(material["stock"])) > 1e-6:
        st.warning(f"El saldo del kardex ({final:g}) no coincide con el stock actual ({float(material['stock']):g}). Revisa los movimientos.", icon=":material/warning:")
    st.dataframe(
        ui.tint_frame(table, good=["Entrada"], bad=["Salida"]), hide_index=True, width="stretch",
        column_config={c: st.column_config.NumberColumn(format="%g") for c in ("Entrada", "Salida", "Saldo")},
    )
    name = f"kardex_{material['material_name']}".replace(" ", "_")[:60]
    d1, d2, _ = st.columns([2, 2, 3])
    d1.download_button(":material/download: Excel", data=to_excel({"Kardex": table}), file_name=f"{name}.xlsx", width="stretch",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="kardex_xlsx")
    d2.download_button(":material/download: PDF", data=to_pdf(f"Kardex: {material['material_name']}", {f"{material['material_name']} ({unit})": table}), file_name=f"{name}.pdf",
                       mime="application/pdf", width="stretch", key="kardex_pdf")


def _render_counts() -> None:
    counts = repo.list_inventory_counts()
    if counts.empty:
        ui.empty_state("Aún no hay conteos", "Usa «Toma de inventario» para contar lo que hay en estantería y ajustar las diferencias del sistema.", "🧮")
        return
    for row in counts.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 1.6])
            with c1:
                sub = f"{clock.local(row['created_at'])} · {int(row['lines_count'])} contado(s)"
                st.markdown(ui.row_name_sub(ui.avatar(row["code"]), row["code"], sub), unsafe_allow_html=True)
            with c2:
                adjusted = int(row["adjusted_count"])
                st.markdown(ui.pill(f"{adjusted} ajuste(s)" if adjusted else "Sin diferencias", "amber" if adjusted else "green"), unsafe_allow_html=True)
            with c3:
                if st.button(":material/visibility: Ver detalle", key=f"count_open_{row['id']}", width="stretch"):
                    count_detail_dialog(row)


def _render_movements() -> None:
    moves = repo.list_movements(limit=300)
    if moves.empty:
        ui.empty_state("Aún no hay movimientos", "Las recepciones, despachos, entradas y mermas aparecerán aquí con su fecha y responsable.")
        return
    st.caption(f"{len(moves)} movimiento(s) reciente(s). Se muestran hasta los últimos 300.")
    rows = []
    for m in moves.to_dict("records"):
        sign = "+" if m["kind"] == "entrada" else "−"
        label = TYPE_LABELS.get(m.get("movement_type"), ("Entrada" if m["kind"] == "entrada" else "Salida", "gray"))[0]
        where = " · ".join(x for x in [m.get("voucher_code"), m.get("count_code"), m["site_name"], m.get("requested_by") and f"pidió {m['requested_by']}", m["order_code"], m["note"]] if x)
        rows.append(
            ui.activity_item(
                f"{sign}{float(m['quantity']):g} {m['material_name']}",
                f"{where} · {m['actor'] or 'sistema'}" if where else (m["actor"] or "sistema"),
                label,
                time_ago(str(m["created_at"]).replace(" ", "T")),
            )
        )
    st.markdown('<div class="mrp-panel">' + "".join(rows) + "</div>", unsafe_allow_html=True)
