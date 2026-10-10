"""Módulo de Reportes: elige qué datos incluir y descárgalos en Excel (una
hoja por conjunto de datos) o en PDF (una tabla por conjunto de datos)."""
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, inventario, ui
from modules.ordenes import STATUSES
from utils.reports import to_excel, to_pdf


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
        {"name": "Proveedor", "contact_name": "Contacto", "phone": "Teléfono", "email": "Correo", "notes": "Notas"},
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
            "items_count": "Líneas",
            "total": "Total",
        },
    )
    df["Fecha"] = df["Fecha"].map(lambda v: str(v)[:10] if v is not None and v == v else "")
    df["Estado"] = df["Estado"].map(lambda v: STATUSES.get(v, (v,))[0] if v is not None else "")
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
        {"created_at": "Fecha", "material_name": "Material", "kind": "Tipo", "quantity": "Cantidad", "site_name": "Obra", "order_code": "Orden", "actor": "Registró", "note": "Nota"},
    )
    df["Fecha"] = df["Fecha"].map(lambda v: str(v)[:16].replace("T", " ") if v is not None and v == v else "")
    return df


def _attendance() -> pd.DataFrame:
    today = date.today()
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
}


@st.cache_data(ttl=300, max_entries=8, show_spinner=False)
def _excel_file(frames: dict) -> bytes:
    return to_excel(frames)


@st.cache_data(ttl=300, max_entries=8, show_spinner=False)
def _pdf_file(frames: dict) -> bytes:
    return to_pdf("Reporte Sistema MRP", frames)


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
            default=list(DATASETS),
            key="report_datasets",
            help="Puedes quitar conjuntos con la × y añadirlos desde el desplegable.",
        )
        all_col, none_col = st.columns(2)
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

    stamp = f"{datetime.now():%Y%m%d_%H%M}"
    c1, c2, _ = st.columns([2, 2, 3])
    c1.download_button(
        "⬇ Descargar Excel",
        data=excel,
        file_name=f"reporte_mrp_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        width="stretch",
    )
    c2.download_button(
        "⬇ Descargar PDF",
        data=pdf,
        file_name=f"reporte_mrp_{stamp}.pdf",
        mime="application/pdf",
        width="stretch",
    )

    st.write("")
    forms.section("3. Revisa la vista previa", "Abre cada conjunto para comprobar sus datos antes de compartir el archivo.")
    for name, df in frames.items():
        with st.expander(f"{name} ({len(df)})"):
            if df.empty:
                st.caption("Sin registros.")
            else:
                st.dataframe(df.head(50), hide_index=True, width="stretch")
                if len(df) > 50:
                    st.caption(f"Mostrando 50 de {len(df)}; el archivo descargado incluye todos.")
