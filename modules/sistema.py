"""Módulo Sistema: qué es este sistema, en qué versión está, con qué datos y en qué entorno corre.

Sirve para saber si Streamlit Cloud ya redesplegó, para dar soporte (hay un resumen listo para copiar) y para dejar
claro cómo se trata el dinero: las compras se pagan fuera del sistema, con el RUC de la empresa; aquí solo se
registran para consulta y para tesorería."""
from __future__ import annotations

import platform
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core.version import APP_VERSION
from db import repository as repo
from db.client import using_service_key
from db.repository import USING_LOCAL
from modules import ui

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
FLOW = [
    ("Proveedor", "Se registra con su catálogo y precios."),
    ("Orden de compra", "El administrador pide el material; el pago se hace aparte."),
    ("Recepción", "Llega el material: guía o factura, quién entregó y observaciones."),
    ("Almacén", "Entra al stock. Se cuenta, se corrige y se devuelve lo que sobra."),
    ("Despacho a obra", "Sale con un vale firmado y se compara con el presupuesto."),
]


def changelog_entries(limit: int = 8, path: Path = CHANGELOG) -> list[dict]:
    """Los últimos parches del registro de cambios: [{"version", "title", "date"}] (el más nuevo primero)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for match in re.finditer(r"^## Parche (\d+)\s+—\s+(.+?)(?:\s+·\s+(\d{4}-\d{2}-\d{2}))?\s*$", text, re.M):
        out.append({"version": f"parche {match.group(1)}", "title": match.group(2).strip(), "date": match.group(3) or ""})
        if len(out) >= limit:
            break
    return out


def environment() -> dict:
    """Datos del entorno donde corre la app (sin secretos)."""
    if USING_LOCAL:
        data, security = "Base local de prueba (SQLite)", ("Solo para pruebas", "warn")
    elif using_service_key():
        data, security = "Supabase (Postgres)", ("Base protegida con clave de servicio", "good")
    else:
        data, security = "Supabase (Postgres)", ("Modo abierto: falta la clave de servicio", "bad")
    return {
        "version": APP_VERSION, "data": data, "security": security[0], "security_tone": security[1],
        "streamlit": st.__version__, "pandas": pd.__version__, "python": platform.python_version(),
        "system": platform.system(), "now": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def support_text(info: dict) -> str:
    """Resumen para pegar en un mensaje de soporte."""
    return "\n".join(
        [
            f"Sistema MRP · {info['version']}",
            f"Datos: {info['data']} · {info['security']}",
            f"Streamlit {info['streamlit']} · pandas {info['pandas']} · Python {info['python']} ({info['system']})",
            f"Consultado el {info['now']}",
        ]
    )


def render() -> None:
    info = environment()
    ui.page_header("Información", "Sistema", "Versión, entorno y datos del sistema, y cómo se trata el dinero.")

    ui.stat_grid(
        [
            ui.stat_card("🧩", info["version"], "Versión", "la que está desplegada ahora", tone="purple"),
            ui.stat_card("🗄️", "Local" if USING_LOCAL else "Supabase", "Base de datos", info["data"]),
            ui.stat_card("🔒", "Protegida" if info["security_tone"] == "good" else ("Abierta" if info["security_tone"] == "bad" else "Prueba"), "Seguridad", info["security"], warn=info["security_tone"] == "bad"),
            ui.stat_card("🕒", info["now"], "Hora del sistema", f"Streamlit {info['streamlit']}"),
        ]
    )

    st.markdown('<div class="mrp-eyebrow">Para qué sirve</div><div class="mrp-panel-title">Compras, almacén y obras en un solo lugar</div>', unsafe_allow_html=True)
    st.write(
        "El sistema ayuda al administrador a **comunicarse con los proveedores**, **controlar el almacén** y **repartir el material a las obras**, "
        "dejando todo registrado: quién pidió qué, a qué precio, cuándo llegó y adónde se despachó."
    )
    ui.tip(
        "Sobre el dinero: el sistema no cobra ni paga nada (no usa tarjetas ni cuentas bancarias). Las compras las paga el administrador por fuera, con el RUC de la empresa. "
        "Las cifras que ves son lo comprado o comprometido en las órdenes: un registro para consulta y para tesorería, no una pérdida."
    )

    st.markdown('<div class="mrp-eyebrow">Cómo fluye</div><div class="mrp-panel-title">De la compra a la obra</div>', unsafe_allow_html=True)
    cols = st.columns(len(FLOW))
    for index, (col, (title, text)) in enumerate(zip(cols, FLOW), start=1):
        with col, st.container(border=True):
            st.markdown(f"**{index}. {title}**")
            st.caption(text)

    st.markdown('<div class="mrp-eyebrow">Datos</div><div class="mrp-panel-title">Lo que hay registrado</div>', unsafe_allow_html=True)
    totals = repo.dashboard_totals()
    orders = repo.list_orders()
    ui.stat_grid(
        [
            ui.stat_card("📦", totals.get("materials", 0), "Materiales", "en el catálogo"),
            ui.stat_card("🏭", totals.get("suppliers", 0), "Proveedores"),
            ui.stat_card("🧾", len(orders), "Órdenes de compra", f"{totals.get('orders_open', 0)} abiertas"),
            ui.stat_card("🚚", len(repo.list_dispatches(limit=100000)), "Vales de salida", f"{totals.get('dispatches_month', 0)} este mes"),
            ui.stat_card("🏗️", len(repo.list_project_sites()), "Obras"),
        ]
    )

    st.markdown('<div class="mrp-eyebrow">Novedades</div><div class="mrp-panel-title">Últimos cambios del sistema</div>', unsafe_allow_html=True)
    entries = changelog_entries()
    if entries:
        for entry in entries:
            with st.container(border=True):
                left, right = st.columns([5, 1.4], vertical_alignment="center")
                left.markdown(f"**{entry['title']}**")
                right.markdown(ui.pill(entry["version"], "purple") + (f"<br><span class='mrp-row-sub'>{entry['date']}</span>" if entry["date"] else ""), unsafe_allow_html=True)
        st.caption("El detalle completo está en el archivo CHANGELOG.md del proyecto.")
    else:
        st.caption("El registro de cambios no está disponible en este entorno.")

    st.markdown('<div class="mrp-eyebrow">Soporte</div><div class="mrp-panel-title">Información técnica</div>', unsafe_allow_html=True)
    st.caption("Si necesitas ayuda, copia este resumen y envíalo junto con la descripción del problema (no incluye contraseñas ni claves).")
    st.code(support_text(info), language=None)
