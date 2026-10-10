"""CSS compartido y componentes visuales reutilizables (encabezado de página,
tarjetas de stat, lista de actividad, dona de estado) para que todos los
módulos se vean consistentes."""
import html
import math
import re
from typing import Callable

import pandas as pd
import streamlit as st

from db import repository as repo
from modules.guides import guide_for

from modules.ui_styles import CSS, DARK, LIGHT


def inject() -> None:
    palette = DARK if st.session_state.get("dark_mode") else LIGHT
    st.markdown("<style>:root {" + palette + "}" + CSS + "</style>", unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "", action_label: str | None = None, action_key: str | None = None) -> bool:
    """Título, contexto, ayuda y acción principal con la misma jerarquía."""
    content = f'<div class="mrp-eyebrow">{html.escape(eyebrow)}</div><div class="mrp-page-title">{html.escape(title)}</div>'
    if subtitle:
        content += f'<div class="mrp-page-subtitle">{html.escape(subtitle)}</div>'
    guide = guide_for(eyebrow, title)
    if not action_label:
        st.markdown(content, unsafe_allow_html=True)
        _guide_popover(guide)
        return False
    left, right = st.columns([3.5, 1.5], vertical_alignment="center")
    with left:
        st.markdown(content, unsafe_allow_html=True)
    with right:
        clicked = st.button(action_label, key=action_key, type="primary", width="stretch")
    _guide_popover(guide)
    return clicked


def empty_state(title: str, description: str, icon: str = "📦") -> None:
    st.markdown(
        f'<div class="mrp-empty"><div class="mrp-empty-icon">{html.escape(icon)}</div>'
        f'<div class="mrp-empty-title">{html.escape(title)}</div>'
        f'<div class="mrp-empty-copy">{html.escape(description)}</div></div>',
        unsafe_allow_html=True,
    )


def result_count(shown: int, total: int, noun: str = "registros") -> None:
    text = f"{shown} de {total} {noun}" if shown != total else f"{total} {noun}"
    st.markdown(f'<div class="mrp-result-count">{html.escape(text)}</div>', unsafe_allow_html=True)


def paginate(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Dibuja solo una página; conserva siempre una página válida al filtrar."""
    if len(df) <= 20:
        return df
    size_col, page_col = st.columns([1, 2])
    size = size_col.selectbox("Por página", [20, 50, 100], key=f"{key}_size")
    pages = max(1, math.ceil(len(df) / size))
    page_key = f"{key}_page"
    if st.session_state.get(page_key, 1) > pages:
        st.session_state[page_key] = 1
    page = page_col.selectbox("Página", list(range(1, pages + 1)), format_func=lambda n: f"{n} de {pages}", key=page_key)
    start = (page - 1) * size
    st.caption(f"Mostrando {start + 1}–{min(start + size, len(df))} de {len(df)}. Usa el buscador para localizar un registro.")
    return df.iloc[start:start + size]


def chart_theme(fig):
    """Mantiene legibles también los gráficos, sin invertir el mapa."""
    dark = st.session_state.get("dark_mode", False)
    fig.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        font=dict(family="Inter, sans-serif", color="#F1F4FC" if dark else "#20263B", size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _guide_popover(guide: str | None) -> None:
    if guide:
        with st.popover("❓ Cómo usar"):
            st.markdown(guide)


def tip(text: str) -> None:
    """Consejo breve con ejemplo, para el inicio de un formulario."""
    st.markdown(f'<div class="mrp-tip">💡 {html.escape(text)}</div>', unsafe_allow_html=True)


def stat_card(icon: str, value, label: str, caption: str = "", warn: bool = False) -> str:
    klass = "mrp-stat-card mrp-warn" if warn else "mrp-stat-card"
    caption_html = f'<div class="mrp-stat-caption">{caption}</div>' if caption else ""
    return (
        f'<div class="{klass}">'
        f'<div class="mrp-stat-top">'
        f'<div class="mrp-stat-label">{label}</div>'
        f'<div class="mrp-icon-badge">{icon}</div>'
        f"</div>"
        f'<div class="mrp-stat-value">{value}</div>'
        f"{caption_html}"
        f"</div>"
    )


def stat_grid(cards: list[str]) -> None:
    st.markdown(f'<div class="mrp-stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def activity_item(name: str, sub: str, badge: str, when: str = "") -> str:
    when_html = f'<div class="mrp-activity-when">{when}</div>' if when else ""
    return (
        '<div class="mrp-activity-item">'
        f'<div><div class="mrp-activity-name">{name}</div><div class="mrp-activity-sub">{sub}</div></div>'
        f'<div style="text-align:right;">'
        f'<div class="mrp-activity-badge">{badge}</div>{when_html}'
        f"</div>"
        "</div>"
    )


def activity_list(items: list[str]) -> str:
    return "".join(items) if items else '<div class="mrp-activity-sub">Todavía no hay actividad.</div>'


def panel_header(eyebrow: str, title: str) -> None:
    """Encabezado a usar dentro de un `with st.container(border=True):`."""
    st.markdown(
        f'<div class="mrp-eyebrow">{eyebrow}</div><div class="mrp-panel-title">{title}</div>',
        unsafe_allow_html=True,
    )


def avatar(name: str) -> str:
    initial = (name or "?").strip()[:1].upper() or "?"
    return f'<div class="mrp-avatar">{initial}</div>'


def pill(text: str, color: str = "purple") -> str:
    return f'<span class="mrp-pill mrp-pill-{color}">{text}</span>'


def row_name_sub(avatar_html: str, name: str, sub: str) -> str:
    return (
        f'<div class="mrp-row">{avatar_html}'
        f'<div><div class="mrp-row-name">{name}</div><div class="mrp-row-sub">{sub}</div></div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Avisos, confirmaciones, búsqueda y contacto
# ---------------------------------------------------------------------------

def current_actor() -> str:
    """Nombre de quien tiene la sesión iniciada (para el historial)."""
    user = st.session_state.get("auth_user") or {}
    return user.get("name") or user.get("username") or "Sistema"


def flash(message: str, icon: str = "✅", log: bool = True) -> None:
    """Deja un aviso (toast) para mostrarse en la próxima recarga: sirve para
    confirmar una acción justo antes de un st.rerun(), que de otro modo se
    llevaría el mensaje. Cada aviso es una acción ya hecha, así que también
    se anota en el historial de cambios (quién y cuándo)."""
    st.session_state["_flash"] = (message, icon)
    if log:
        try:
            repo.log_action(current_actor(), message)
        except Exception:  # el historial nunca debe romper la acción en sí
            pass


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        st.toast(item[0], icon=item[1])


@st.dialog("Confirmar eliminación")
def _confirm_dialog(message: str, on_confirm: Callable[[], None]) -> None:
    st.write(message)
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", width="stretch"):
        st.rerun()
    if c2.button("Sí, eliminar", type="primary", width="stretch"):
        on_confirm()
        st.rerun()


def confirm_delete(message: str, on_confirm: Callable[[], None]) -> None:
    """Abre un modal de confirmación; `on_confirm` solo corre si el usuario
    acepta (debería borrar y dejar su propio flash())."""
    _confirm_dialog(message, on_confirm)


def filter_df(df: pd.DataFrame, query: str, columns: list[str]) -> pd.DataFrame:
    """Filtra filas cuyo texto contenga `query` (sin importar mayúsculas) en
    alguna de las columnas dadas."""
    q = (query or "").strip().lower()
    if not q or df.empty:
        return df

    def norm(value) -> str:
        if value is None or (isinstance(value, float) and value != value):
            return ""
        return str(value).lower()

    mask = pd.Series(False, index=df.index)
    for col in columns:
        mask |= df[col].map(norm).str.contains(q, regex=False)
    return df[mask]


def contact_links(phone: str | None, email: str | None) -> str:
    """Enlaces de contacto rápido: llamar (tel:), WhatsApp (wa.me) y correo."""
    parts = []
    if phone:
        dial = re.sub(r"[^\d+]", "", phone)
        wa = re.sub(r"\D", "", phone)
        parts.append(f'<a class="mrp-link" href="tel:{dial}">📞 Llamar</a>')
        if wa:
            parts.append(f'<a class="mrp-link" href="https://wa.me/{wa}" target="_blank" rel="noopener">💬 WhatsApp</a>')
    if email:
        parts.append(f'<a class="mrp-link" href="mailto:{html.escape(email, quote=True)}">✉️ Correo</a>')
    if not parts:
        return '<div class="mrp-row-sub">Sin datos de contacto</div>'
    return '<div class="mrp-links">' + "".join(parts) + "</div>"
