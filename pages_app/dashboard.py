"""Panel principal: totales generales del sistema."""
import streamlit as st

from db import repository as repo


def render(user: dict) -> None:
    st.header(f"Hola, {user['name']} 👋")
    st.caption("Resumen general del sistema MRP.")

    totals = repo.dashboard_totals()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Materiales en catálogo", totals["materials"])
    c2.metric("Proveedores registrados", totals["suppliers"])
    c3.metric("Proveedores con algo disponible", totals["suppliers_with_available"])
    c4.metric("Materiales sin proveedor", totals["materials_without_supplier"])

    if totals["materials"] and totals["materials_without_supplier"]:
        st.warning(
            f"Hay {totals['materials_without_supplier']} material(es) que ningún proveedor ofrece todavía. "
            "Revísalos en el módulo de Proveedores."
        )
