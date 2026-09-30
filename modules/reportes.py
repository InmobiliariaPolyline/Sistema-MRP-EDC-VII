"""Módulo de Reportes: todavía no implementado."""
import streamlit as st

from modules import ui


def render() -> None:
    ui.page_header("Análisis", "Reportes")
    st.info(
        "Próximamente: reportes exportables (Excel/PDF) del catálogo de materiales, "
        "proveedores y trabajadores, en un solo lugar."
    )
