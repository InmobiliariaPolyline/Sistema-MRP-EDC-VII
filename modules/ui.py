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

from modules import ui_styles
from utils import audit as audit_text
from utils import contact as contact_utils
from utils import icons


def inject() -> None:
    sheets = ui_styles.bundle()  # se relee solo si cambió algún .css (ver ui_styles)
    palette = sheets["dark"] if st.session_state.get("dark_mode") else sheets["light"]
    # al cambiar de pantalla se alterna el nombre de la animación de entrada: así se reproduce de nuevo solo al navegar
    palette += "--mrp-enter:" + ("mrpUpB" if st.session_state.get("_mrp_nav", 0) % 2 else "mrpUpA") + ";"
    extra = sheets["dark_extra"] if st.session_state.get("dark_mode") else ""
    st.markdown("<style>" + sheets["font"] + "</style><style>:root {" + palette + "}" + sheets["css"] + extra + "</style>", unsafe_allow_html=True)


# icono del rótulo de cada sección según la palabra que contiene (para el encabezado de página y de los paneles)
_EYEBROW_ICONS = (
    ("orden", "receipt"), ("pedido", "receipt"), ("compra", "truck"), ("proveedor", "factory"), ("almac", "box"), ("inventario", "box"),
    ("obra", "building"), ("personal", "helmet"), ("trabajador", "helmet"), ("material", "layers"), ("catálogo", "layers"), ("ayuda", "bulb"),
    ("anális", "chart"), ("report", "chart"), ("portafolio", "chart"), ("historial", "clock"), ("respaldo", "shield"), ("seguridad", "shield"),
    ("informaci", "info"), ("sistema", "info"), ("centro", "home"), ("resumen", "home"), ("ubicaci", "pin"), ("asistencia", "calendar"),
)


def eyebrow_html(text: str, extra: str = "") -> str:
    """El rótulo pequeño sobre un título, con un icono que sigue a su tema."""
    low = text.lower()
    name = next((icon for key, icon in _EYEBROW_ICONS if key in low), None)
    icon = icons.svg(name, 13, 2.2) if name else ""
    return f'<div class="mrp-eyebrow{" has-ico" if icon else ""}{extra}">{icon}{html.escape(text)}</div>'


def page_header(eyebrow: str, title: str, subtitle: str = "", action_label: str | None = None, action_key: str | None = None) -> bool:
    """Título, contexto, ayuda y acción principal con la misma jerarquía."""
    guide = guide_for(eyebrow, title)
    low = eyebrow.lower()
    tile = (guide or {}).get("icon") or next((icon for key, icon in _EYEBROW_ICONS if key in low), "box")
    text = f'{eyebrow_html(eyebrow)}<div class="mrp-page-title">{html.escape(title)}</div>'
    if subtitle:
        text += f'<div class="mrp-page-subtitle">{html.escape(subtitle)}</div>'
    content = f'<div class="mrp-ph"><div class="mrp-ph-ico">{icons.svg(tile, 26, 1.8)}</div><div class="mrp-ph-text">{text}</div></div>'
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
        f'<div class="mrp-empty"><div class="mrp-empty-icon">{icons.render_tokens(html.escape(icon), 30, 1.6)}</div>'
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
    """Gráficos con la misma tipografía y colores que el resto de la interfaz."""
    dark = st.session_state.get("dark_mode", False)
    text = "#EEF1FC" if dark else "#141A33"
    muted = "#A7B2CE" if dark else "#5C6685"
    grid = "rgba(167,178,206,.16)" if dark else "rgba(20,26,51,.07)"
    fig.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        font=dict(family="Inter, sans-serif", color=text, size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#1B2442" if dark else "#FFFFFF", font=dict(family="Inter, sans-serif", color=text), bordercolor=grid),
    )
    fig.update_layout(
        colorway=["#7C66FF", "#18B4CC", "#E0951A", "#3DB87A", "#E5596B", "#5B8DEF"],
        transition=dict(duration=600, easing="cubic-in-out"),
        legend=dict(font=dict(color=muted), bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_traces(root_color="rgba(0,0,0,0)", pathbar=dict(visible=False), selector=dict(type="treemap"))
    fig.update_xaxes(gridcolor=grid, zerolinecolor=grid, linecolor=grid, tickfont=dict(color=muted))
    fig.update_yaxes(gridcolor=grid, zerolinecolor=grid, linecolor=grid, tickfont=dict(color=muted))
    return fig


def guide_button(title: str) -> None:
    """Botón «Cómo usar» de un módulo cuyo encabezado no es page_header."""
    _guide_popover(guide_for("", title))


def _guide_popover(guide: dict | None) -> None:
    """Botón «Cómo usar» que abre la ventana de ayuda de la pantalla (ver `modules/help_ui.py`)."""
    from modules import help_ui

    help_ui.help_button(guide)


def tip(text: str) -> None:
    """Consejo breve con ejemplo, para el inicio de un formulario."""
    st.markdown(f'<div class="mrp-tip">{icons.svg("bulb", 16, 2)}<span>{html.escape(text)}</span></div>', unsafe_allow_html=True)


def spark(values: list[float], color: str = "currentColor") -> str:
    """Mini gráfico de línea (SVG) para una tarjeta de estadística."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pts = [(i / (len(vals) - 1) * 100, 28 - (v - lo) / span * 24) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,32 {line} 100,32"
    return (
        f'<svg class="mrp-spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">'
        f'<polygon points="{area}" fill="{color}" opacity=".12"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>'
    )


def stat_card(icon: str, value, label: str, caption: str = "", warn: bool = False, tone: str = "purple", trend: list[float] | None = None) -> str:
    """Tarjeta de estadística. `tone`: purple, green, amber, blue, red o teal."""
    klass = f"mrp-stat-card mrp-tone-{'amber' if warn else tone}"
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 1000 or (isinstance(value, str) and value.isdigit() and len(value) < 4):
        value = f'<span class="mrp-count" style="--to:{int(value)}"></span>'   # los números enteros chicos «suben» hasta su valor
    caption_html = f'<div class="mrp-stat-caption">{caption}</div>' if caption else ""
    spark_html = spark(trend or [], "var(--tone)")
    return (
        f'<div class="{klass}">'
        f'<div class="mrp-stat-top">'
        f'<div class="mrp-stat-label">{label}</div>'
        f'<div class="mrp-icon-badge">{icons.render_tokens(icon, 20, 1.8)}</div>'
        f"</div>"
        f'<div class="mrp-stat-value">{value}</div>'
        f"{caption_html}{spark_html}"
        f"</div>"
    )


def stat_grid(cards: list[str]) -> None:
    st.markdown(f'<div class="mrp-stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def hero(eyebrow: str, title: str, subtitle: str = "", chips: list[str] | None = None) -> None:
    """Banner principal de una pantalla (se usa en el dashboard)."""
    chips_html = "".join(f'<span class="mrp-hero-chip">{icons.render_tokens(html.escape(c), 14, 2)}</span>' for c in (chips or []))
    st.markdown(
        f'<div class="mrp-hero"><div class="mrp-hero-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="mrp-hero-title">{html.escape(title)}</div>'
        + (f'<div class="mrp-hero-sub">{html.escape(subtitle)}</div>' if subtitle else "")
        + (f'<div class="mrp-hero-chips">{chips_html}</div>' if chips_html else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def timeline_item(icon: str, name: str, sub: str, when: str = "", tone: str = "") -> str:
    """Elemento de una línea de tiempo (actividad reciente)."""
    when_html = f'<div class="mrp-timeline-when">{when}</div>' if when else ""
    return (
        '<div class="mrp-timeline-item">'
        f'<div class="mrp-timeline-dot">{icons.render_tokens(icon, 16, 2)}</div>'
        f'<div class="mrp-timeline-body"><div class="mrp-activity-name">{name}</div><div class="mrp-activity-sub">{sub}</div></div>'
        f"{when_html}</div>"
    )


def go(label: str) -> None:
    """Navega a un módulo del menú (para botones de acceso rápido)."""
    st.session_state["mrp_active_route"] = label
    st.session_state["_mrp_nav"] = st.session_state.get("_mrp_nav", 0) + 1


def activity_item(name: str, sub: str, badge: str, when: str = "") -> str:
    when_html = f'<div class="mrp-activity-when">{icons.render_tokens(str(when), 13, 2)}</div>' if when else ""
    return (
        '<div class="mrp-activity-item">'
        f'<div><div class="mrp-activity-name">{name}</div><div class="mrp-activity-sub">{sub}</div></div>'
        f'<div style="text-align:right;">'
        f'<div class="mrp-activity-badge">{icons.render_tokens(str(badge), 14, 2)}</div>{when_html}'
        f"</div>"
        "</div>"
    )


def panel_header(eyebrow: str, title: str) -> None:
    """Encabezado a usar dentro de un `with st.container(border=True):`."""
    st.markdown(f'{eyebrow_html(eyebrow)}<div class="mrp-panel-title">{title}</div>', unsafe_allow_html=True)


def avatar(name: str, logo: str | None = None) -> str:
    """Círculo con la inicial del nombre; con `logo` (data URL de utils/logo.py) muestra la imagen del proveedor."""
    if logo and str(logo).startswith("data:image/"):
        return f'<div class="mrp-avatar mrp-logo"><img src="{html.escape(str(logo), quote=True)}" alt="{html.escape(name or "Logotipo", quote=True)}" loading="lazy"></div>'
    initial = (name or "?").strip()[:1].upper() or "?"
    return f'<div class="mrp-avatar">{initial}</div>'


def pill(text: str, color: str = "purple") -> str:
    return f'<span class="mrp-pill mrp-pill-{color}">{icons.render_tokens(text, 12, 2.2)}</span>'


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


def db_error(exc: Exception, fallback: str) -> None:
    """Muestra un error de base de datos con su causa real cuando se puede explicar.

    Un `42501` («row-level security») significa que Supabase tiene RLS activo en esa tabla y
    rechaza la escritura: se indica la tabla y el comando que lo arregla. Para cualquier otro
    error se muestra el mensaje de siempre y, debajo, el detalle técnico para poder diagnosticarlo."""
    code = str(getattr(exc, "code", "") or "")
    detail = str(getattr(exc, "message", None) or exc)
    if code == "42501" or "row-level security" in detail.lower():
        match = re.search(r'table "([\w]+)"', detail)
        table = match.group(1) if match else "la tabla"
        st.error(
            f"Supabase bloqueó el guardado: la tabla «{table}» tiene la seguridad por fila (RLS) activa. "
            "Esto lo arregla el administrador de la base ejecutando en el SQL Editor de Supabase el archivo "
            f"`db/migrations/037_disable_rls_all.sql` (o solo `alter table {table} disable row level security;`).",
            icon=":material/lock:",
        )
    else:
        st.error(fallback)
    st.caption(f"Detalle técnico: {code + ' · ' if code else ''}{detail[:200]}")


def log(summary: str) -> None:
    """Anota una acción en el historial sin mostrar aviso (para cuando la pantalla ya muestra el resultado)."""
    try:
        repo.log_action(current_actor(), summary)
    except Exception:  # el historial nunca debe romper la acción en sí
        pass


def log_change(
    summary: str, entity_type: str, entity_id: str | None, changes: list[dict], icon: str | None = None, flash_message: bool = False,
) -> None:
    """Anota en el historial una edición con lo que cambió (antes → después). Si no cambió nada, no anota.
    El texto del resumen ya incluye los cambios, así que se lee igual aunque no exista el detalle estructurado.
    Con `icon` además deja un aviso en pantalla (toast) con el resumen."""
    if not changes:
        return
    text = f"{summary} ({audit_text.describe(changes)})"
    if icon or flash_message:
        st.session_state["_flash"] = (summary, icon or ":material/edit:")
    try:
        repo.log_action(current_actor(), text, entity_type, entity_id, changes)
    except Exception:  # el historial nunca debe romper la acción en sí
        pass


def flash(message: str, icon: str = ":material/check_circle:", log: bool = True) -> None:
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


def _toast_icon(token: str) -> str:
    """Los avisos (toast) llevan un icono Material; un emoji conocido se traduce y cualquier otro valor cae en una marca de éxito."""
    if str(token).startswith(":material/"):
        return token
    return icons.material(token, ":material/check_circle:")


def signed(value: float, text: str | None = None, good_when_positive: bool = True) -> str:
    """Un número que cambia de color en tiempo real según su signo: verde si es favorable, rojo si no, gris si es cero."""
    number = float(value or 0)
    if number == 0:
        tone = "zero"
    else:
        tone = "pos" if (number > 0) == good_when_positive else "neg"
    return f'<span class="mrp-num mrp-num-{tone}">{html.escape(text if text is not None else f"{number:,.2f}")}</span>'


def tint_frame(df: pd.DataFrame, signed: list[str] | None = None, good: list[str] | None = None, bad: list[str] | None = None):
    """La tabla con colores según el valor: `signed` (verde si es positivo, rojo si es negativo), `good` (verde si es mayor que
    cero) y `bad` (rojo si es mayor que cero). Los ceros y los vacíos quedan sin color."""
    # en modo oscuro la tabla se invierte por CSS (ver dark_extra.css): con estos colores base queda verde y rojo claro
    green, red = "#16794A", "#C0343F"

    def paint(colors: tuple[str, str]):
        def one(value):
            try:
                number = float(value)
            except (TypeError, ValueError):
                return ""
            if number != number or number == 0:
                return ""
            return f"color: {colors[0] if number > 0 else colors[1]}; font-weight: 700"
        return one

    styler = df.style
    for columns, colors in ((signed, (green, red)), (good, (green, "")), (bad, (red, ""))):
        present = [c for c in (columns or []) if c in df.columns]
        if present:
            styler = styler.map(paint(colors), subset=present)
    return styler


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        st.toast(item[0], icon=_toast_icon(item[1]))


@st.dialog("Confirmar eliminación")
def _confirm_dialog(message: str, on_confirm: Callable[[], None]) -> None:
    st.write(message)
    c1, c2 = st.columns(2)
    if c1.button(":material/close: Cancelar", width="stretch"):
        st.rerun()
    if c2.button(":material/delete: Sí, eliminar", type="primary", width="stretch"):
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


def contact_links(
    phone: str | None, email: str | None, contact: str | None = None, company: str | None = None, audience: str = "supplier",
    site: str | None = None, role: str | None = None,
) -> str:
    """Botones de contacto rápido con el aspecto de lo que representan: llamar (celeste), WhatsApp (verde), Gmail y Outlook.
    WhatsApp, Gmail y Outlook se despliegan con mensajes ya escritos (cotizar, disponibilidad, precios, seguimiento, entrega,
    comprobantes): al elegir uno se abre la aplicación con el texto listo. El sistema no envía nada: lo revisa y envía la persona."""
    presets = contact_utils.messages(contact, company, audience, site, role)
    head = "Mensaje para tu equipo" if audience == "worker" else "Elige un mensaje"
    buttons = []
    if phone:
        buttons.append(f'<a class="mrp-cbtn call" href="tel:{contact_utils.dial_number(phone)}">{icons.svg("phone", 16, 2.1)}<span>Llamar</span></a>')
        if contact_utils.whatsapp_number(phone):
            items = "".join(
                f'<a href="{html.escape(contact_utils.whatsapp_url(phone, p["whatsapp"]), quote=True)}" target="_blank" rel="noopener">'
                f'<b>{html.escape(p["label"])}</b><small>{html.escape(p["hint"])}</small></a>'
                for p in presets
            )
            buttons.append(_menu("wa", icons.brand("whatsapp", 18), "WhatsApp", "Abrir WhatsApp con un mensaje listo", items, head))
    if email:
        gmail = "".join(
            f'<a href="{html.escape(contact_utils.gmail_url(email, p["subject"], p["body"]), quote=True)}" target="_blank" rel="noopener">'
            f'<b>{html.escape(p["label"])}</b><small>{html.escape(p["hint"])}</small></a>'
            for p in presets
        )
        outlook = "".join(
            f'<a href="{html.escape(contact_utils.outlook_url(email, p["subject"], p["body"]), quote=True)}" target="_blank" rel="noopener">'
            f'<b>{html.escape(p["label"])}</b><small>{html.escape(p["hint"])}</small></a>'
            for p in presets
        ) + (
            f'<a class="app" href="{html.escape(contact_utils.mailto_url(email, presets[0]["subject"], presets[0]["body"]), quote=True)}">'
            f'<b>Abrir en la app de correo</b><small>Con el programa instalado en este equipo</small></a>'
        )
        buttons.append(_menu("gmail", icons.brand("gmail", 18), "Gmail", "Redactar en Gmail con un mensaje listo", gmail))
        buttons.append(_menu("outlook", icons.brand("outlook", 18), "Outlook", "Redactar en Outlook con un mensaje listo", outlook))
    if not buttons:
        return '<div class="mrp-row-sub">Sin datos de contacto</div>'
    return '<div class="mrp-contact">' + "".join(buttons) + "</div>"


def _menu(kind: str, icon_html: str, label: str, title: str, items: str, head: str = "Elige un mensaje") -> str:
    """Botón que despliega una lista de mensajes (HTML puro con <details>, sin JavaScript propio)."""
    return (
        f'<details class="mrp-menu {kind}"><summary class="mrp-cbtn {kind}" title="{html.escape(title, quote=True)}">{icon_html}<span>{label}</span>'
        f'<i class="mrp-menu-chev"></i></summary><div class="mrp-menu-list"><div class="mrp-menu-head">{html.escape(head)}</div>{items}</div></details>'
    )
