"""Módulo de Reportes: elige qué datos incluir y descárgalos en Excel (una
hoja por conjunto de datos) o en PDF (una tabla por conjunto de datos)."""
from datetime import datetime

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import ui
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
            "unit_price": "Precio unit.",
            "subtotal": "Subtotal",
        },
    )


DATASETS = {
    "Materiales": _materials,
    "Proveedores": _suppliers,
    "Catálogo y precios por proveedor": _offers,
    "Trabajadores": _workers,
    "Órdenes de compra": _orders,
    "Detalle de órdenes": _order_items,
}


def render() -> None:
    ui.page_header(
        "Análisis",
        "Reportes",
        "Descarga la información del sistema en Excel o PDF para compartirla o archivarla.",
    )

    with st.container(border=True):
        ui.panel_header("Contenido", "¿Qué quieres incluir?")
        selected = st.multiselect(
            "Datos a incluir",
            list(DATASETS),
            default=list(DATASETS),
            label_visibility="collapsed",
        )

    if not selected:
        st.info("Elige al menos un conjunto de datos para generar el reporte.")
        return

    frames = {name: DATASETS[name]() for name in selected}

    ui.stat_grid([ui.stat_card("📄", len(df), name, "registros") for name, df in frames.items()])

    stamp = f"{datetime.now():%Y%m%d_%H%M}"
    c1, c2, _ = st.columns([2, 2, 3])
    c1.download_button(
        "⬇ Descargar Excel",
        data=to_excel(frames),
        file_name=f"reporte_mrp_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
    c2.download_button(
        "⬇ Descargar PDF",
        data=to_pdf("Reporte Sistema MRP", frames),
        file_name=f"reporte_mrp_{stamp}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.write("")
    st.markdown('<div class="mrp-eyebrow">Vista previa</div>', unsafe_allow_html=True)
    for name, df in frames.items():
        with st.expander(f"{name} ({len(df)})"):
            if df.empty:
                st.caption("Sin registros.")
            else:
                st.dataframe(df.head(50), hide_index=True, use_container_width=True)
                if len(df) > 50:
                    st.caption(f"Mostrando 50 de {len(df)}; el archivo descargado incluye todos.")
