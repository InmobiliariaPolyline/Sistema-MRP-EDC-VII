"""Módulo de Órdenes de compra: todavía no implementado."""
import streamlit as st

from pages_app import ui


def render() -> None:
    ui.page_header("Compras", "Órdenes de compra")
    st.info(
        "Próximamente: registrar pedidos hechos a un proveedor sobre materiales "
        "específicos, con cantidad, fecha y estado del pedido."
    )
