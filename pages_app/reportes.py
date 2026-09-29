"""Módulo de Reportes: todavía no implementado."""
import streamlit as st

from pages_app import ui


def render() -> None:
    ui.page_header("Análisis", "Reportes")
    st.info(
        "Próximamente: reportes combinados (ej. PDF con catálogo de materiales "
        "y proveedores) más allá de los Excel que ya puedes exportar en cada módulo."
    )
