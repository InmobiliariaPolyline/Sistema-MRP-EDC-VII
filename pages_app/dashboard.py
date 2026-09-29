"""Panel principal: totales generales del sistema, en tarjetas."""
import streamlit as st

from db import repository as repo
from pages_app import ui


def render(user: dict) -> None:
    st.header(f"Hola, {user['name']} 👋")
    st.caption("Resumen general del sistema MRP.")

    totals = repo.dashboard_totals()

    ui.stat_grid(
        [
            ui.stat_card("📦", totals["materials"], "Materiales en catálogo"),
            ui.stat_card("🏭", totals["suppliers"], "Proveedores registrados"),
            ui.stat_card("✅", totals["suppliers_with_available"], "Proveedores con algo disponible"),
            ui.stat_card(
                "⚠️",
                totals["materials_without_supplier"],
                "Materiales sin proveedor",
                warn=totals["materials_without_supplier"] > 0,
            ),
        ]
    )

    if totals["materials"] and totals["materials_without_supplier"]:
        st.warning(
            f"Hay {totals['materials_without_supplier']} material(es) que ningún proveedor ofrece todavía. "
            "Revísalos en el módulo de Proveedores."
        )
