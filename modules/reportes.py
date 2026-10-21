"""Módulo de Reportes: elige qué datos incluir y descárgalos en Excel (una
hoja por conjunto de datos) o en PDF (una tabla por conjunto de datos)."""
from datetime import timedelta

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, inventario, ui
from modules.ordenes import STATUSES
from modules.proveedores import supplier_ratings
from utils.reports import to_excel, to_pdf
from utils import clock


def _pick(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Selecciona y renombra columnas (las que falten quedan vacías)."""
    return df.reindex(columns=list(mapping)).rename(columns=mapping).reset_index(drop=True)


def _materials() -> pd.DataFrame:
    return _pick(
        repo.list_materials(),
        {"category": "Categoría", "name": "Material", "density": "Densidad (kg/m³)", "metric_label": "Métrica"},
    )


def _suppliers() -> pd.DataFrame:
    return _pick(
        repo.list_suppliers(),
        {"name": "Proveedor", "ruc": "RUC", "contact_name": "Contacto", "phone": "Teléfono", "email": "Correo", "notes": "Notas"},
    )


def _offers() -> pd.DataFrame:
    df = _pick(
        repo.list_offers(),
        {"supplier_name": "Proveedor", "category": "Categoría", "material_name": "Material", "available": "Disponible", "price": "Precio"},
    )
    df["Disponible"] = df["Disponible"].map(lambda v: "Sí" if v else "No")
    return df


def _workers() -> pd.DataFrame:
    df = _pick(
        repo.list_workers(),
        {
            "full_name": "Nombre",
            "document_id": "Documento",
            "phone": "Teléfono",
            "position": "Puesto",
            "group_name": "Cuadrilla",
            "site_name": "Obra",
            "site_address": "Dirección de la obra",
            "username": "Acceso al sistema",
        },
    )
    return df


def _orders() -> pd.DataFrame:
    df = _pick(
        repo.list_orders(),
        {
            "code": "Código",
            "created_at": "Fecha",
            "supplier_name": "Proveedor",
            "site_name": "Obra",
            "status": "Estado",
            "expected_date": "Entrega prometida",
            "currency": "Moneda",
            "items_count": "Líneas",
            "payment_terms": "Condición de pago",
            "net": "Valor de venta",
            "tax": "IGV",
            "total": "Importe total",
        },
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v, False) if v is not None and v == v else "")
    df["Entrega prometida"] = df["Entrega prometida"].map(lambda v: str(v)[:10] if v is not None and v == v else "")
    df["Estado"] = df["Estado"].map(lambda v: STATUSES.get(v, (v,))[0] if v is not None else "")
    df["Condición de pago"] = df["Condición de pago"].map(lambda v: v if isinstance(v, str) else "")
    return df


def _order_items() -> pd.DataFrame:
    return _pick(
        repo.list_order_items(),
        {
            "order_code": "Orden",
            "material_name": "Material",
            "unit": "Unidad",
            "quantity": "Cantidad",
            "received_qty": "Recibido",
            "unit_price": "Precio unit.",
            "subtotal": "Subtotal",
        },
    )


def _stock() -> pd.DataFrame:
    return _pick(
        inventario.stock_by_material(),
        {"category": "Categoría", "material_name": "Material", "unit": "Unidad", "entradas": "Entradas", "salidas": "Salidas", "stock": "Stock"},
    )


def _movements() -> pd.DataFrame:
    df = _pick(
        repo.list_movements(limit=5000),
        {
            "created_at": "Fecha", "material_name": "Material", "kind": "Tipo", "movement_type": "Motivo", "quantity": "Cantidad",
            "site_name": "Obra", "stage": "Etapa", "voucher_code": "Vale", "order_code": "Orden", "count_code": "Conteo", "actor": "Registró", "note": "Nota",
        },
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    df["Motivo"] = df["Motivo"].map(lambda v: inventario.TYPE_LABELS.get(v, (v or "",))[0] if v == v else "")
    return df


def _vouchers() -> pd.DataFrame:
    df = _pick(
        repo.list_dispatches(limit=5000),
        {"code": "Vale", "created_at": "Fecha", "site_name": "Obra", "stage": "Etapa", "requested_by": "Solicitó", "actor": "Registró", "lines_count": "Materiales", "note": "Nota"},
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    return df


def _voucher_lines() -> pd.DataFrame:
    moves = repo.list_movements(limit=20000)
    moves = moves[moves["voucher_code"].notna()] if not moves.empty else moves
    df = _pick(
        moves,
        {"voucher_code": "Vale", "created_at": "Fecha", "site_name": "Obra", "stage": "Etapa", "material_name": "Material", "unit": "Unidad", "quantity": "Cantidad", "requested_by": "Solicitó"},
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    return df.sort_values(["Vale", "Material"]).reset_index(drop=True) if not df.empty else df


def _price_history() -> pd.DataFrame:
    df = _pick(
        repo.list_price_history(limit=5000),
        {"recorded_at": "Fecha", "supplier_name": "Proveedor", "material_name": "Material", "price": "Precio", "source": "Origen"},
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    return df


def _budgets() -> pd.DataFrame:
    budgets = repo.list_budgets()
    sites = repo.list_project_sites().set_index("id")["name"].to_dict() if not budgets.empty else {}
    if not budgets.empty:
        budgets = budgets.assign(
            site_name=budgets["project_site_id"].map(sites),
            amount=budgets["planned_qty"].astype(float) * budgets["planned_unit_price"].astype(float),
        )
    return _pick(
        budgets,
        {
            "site_name": "Obra", "stage": "Etapa", "category": "Categoría", "material_name": "Material", "unit": "Unidad",
            "planned_qty": "Cantidad prevista", "planned_unit_price": "Precio unit. estimado", "amount": "Importe previsto",
        },
    )


def _counts() -> pd.DataFrame:
    df = _pick(
        repo.list_inventory_counts(limit=1000),
        {"code": "Conteo", "created_at": "Fecha", "actor": "Registró", "lines_count": "Materiales contados", "adjusted_count": "Con ajuste", "note": "Nota"},
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    return df


def _receipts() -> pd.DataFrame:
    receipts = repo.list_receipts()
    codes = repo.list_orders().set_index("id")["code"].to_dict() if not receipts.empty else {}
    if not receipts.empty:
        receipts = receipts.assign(order_code=receipts["order_id"].map(codes))
    df = _pick(
        receipts,
        {"received_at": "Fecha", "order_code": "Orden", "document_ref": "Guía o factura", "delivered_by": "Entregó", "notes": "Observaciones", "actor": "Registró"},
    )
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    return df


def _ratings() -> pd.DataFrame:
    return _pick(
        supplier_ratings(),
        {
            "supplier_name": "Proveedor", "orders": "Órdenes", "timed": "Con fecha prometida", "on_time": "A tiempo", "on_time_pct": "% a tiempo",
            "avg_delay_days": "Atraso promedio (días)", "fill_pct": "% cantidades completas", "score": "Nota", "label": "Calificación",
        },
    ).round(1)


def _audit() -> pd.DataFrame:
    df = _pick(repo.list_audit(limit=3000), {"created_at": "Fecha", "actor": "Usuario", "summary": "Acción"})
    df["Fecha"] = df["Fecha"].map(lambda v: clock.local(v) if v is not None and v == v else "")
    return df


def _attendance() -> pd.DataFrame:
    today = clock.today()
    return _pick(
        repo.list_attendance((today - timedelta(days=90)).isoformat(), today.isoformat()),
        {"work_date": "Fecha", "worker_name": "Trabajador", "site_name": "Obra", "status": "Estado", "note": "Nota"},
    )


DATASETS = {
    "Materiales": _materials,
    "Proveedores": _suppliers,
    "Catálogo y precios por proveedor": _offers,
    "Trabajadores": _workers,
    "Órdenes de compra": _orders,
    "Detalle de órdenes": _order_items,
    "Stock actual": _stock,
    "Movimientos de inventario": _movements,
    "Asistencia (últimos 90 días)": _attendance,
    "Vales de salida": _vouchers,
    "Detalle de vales de salida": _voucher_lines,
    "Historial de precios": _price_history,
    "Presupuestos de obra": _budgets,
    "Conteos de inventario": _counts,
    "Recepciones de órdenes": _receipts,
    "Calificación de proveedores": _ratings,
    "Historial de cambios": _audit,
}
BASIC = [
    "Materiales", "Proveedores", "Catálogo y precios por proveedor", "Trabajadores", "Órdenes de compra", "Detalle de órdenes",
    "Stock actual", "Movimientos de inventario", "Asistencia (últimos 90 días)",
]


@st.cache_data(ttl=300, max_entries=8, show_spinner=False)
def _excel_file(frames: dict) -> bytes:
    return to_excel(frames)


@st.cache_data(ttl=300, max_entries=8, show_spinner=False)
def _pdf_file(frames: dict) -> bytes:
    return to_pdf("Reporte Sistema MRP", frames)


def _choose_basic() -> None:
    st.session_state["report_datasets"] = list(BASIC)


def _choose_all() -> None:
    st.session_state["report_datasets"] = list(DATASETS)


def _choose_none() -> None:
    st.session_state["report_datasets"] = []


def render() -> None:
    ui.page_header(
        "Análisis",
        "Reportes",
        "Descarga la información del sistema en Excel o PDF para compartirla o archivarla.",
    )

    with st.container(border=True):
        forms.section("1. Elige el contenido", "Excel crea una hoja por conjunto. PDF reúne los conjuntos en un documento.")
        selected = st.multiselect(
            "Datos a incluir",
            list(DATASETS),
            default=list(BASIC),
            key="report_datasets",
            help="Puedes quitar conjuntos con la × y añadirlos desde el desplegable. Vales, historial de precios, presupuestos, conteos, recepciones, calificación e historial de cambios se agregan desde aquí.",
        )
        basic_col, all_col, none_col = st.columns(3)
        basic_col.button("Los básicos", on_click=_choose_basic, width="stretch")
        all_col.button("Seleccionar todo", on_click=_choose_all, width="stretch")
        none_col.button("Limpiar selección", on_click=_choose_none, width="stretch")

    if not selected:
        ui.empty_state("Elige qué quieres consultar", "Selecciona uno o varios conjuntos para ver la información y descargar tu reporte.", "📄")
        return

    frames = {name: DATASETS[name]() for name in selected}

    total = sum(len(df) for df in frames.values())
    ui.stat_grid([
        ui.stat_card("📄", len(frames), "Conjuntos", "incluidos en el reporte"),
        ui.stat_card("📋", total, "Registros", "total de filas incluidas"),
        ui.stat_card("🗂️", sum(not df.empty for df in frames.values()), "Con información", "conjuntos con registros"),
    ])
    forms.section("2. Descarga tu reporte", "Los archivos incluyen todos los registros; la vista previa muestra como máximo 50.")
    with st.spinner("Preparando los archivos…"):
        excel = _excel_file(frames)
        pdf = _pdf_file(frames)

    stamp = f"{clock.now():%Y%m%d_%H%M}"
    c1, c2, _ = st.columns([2, 2, 3])
    c1.download_button(
        ":material/download: Descargar Excel",
        data=excel,
        file_name=f"reporte_mrp_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        width="stretch",
    )
    c2.download_button(
        ":material/download: Descargar PDF",
        data=pdf,
        file_name=f"reporte_mrp_{stamp}.pdf",
        mime="application/pdf",
        width="stretch",
    )

    forms.section("3. Revisa la vista previa", "Abre cada conjunto para comprobar sus datos antes de compartir el archivo.")
    for name, df in frames.items():
        with st.expander(f"{name} ({len(df)})"):
            if df.empty:
                st.caption("Sin registros.")
            else:
                st.dataframe(df.head(50), hide_index=True, width="stretch")
                if len(df) > 50:
                    st.caption(f"Mostrando 50 de {len(df)}; el archivo descargado incluye todos.")
