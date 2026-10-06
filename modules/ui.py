"""CSS compartido y componentes visuales reutilizables (encabezado de página,
tarjetas de stat, lista de actividad, dona de estado) para que todos los
módulos se vean consistentes."""
import html
import re
from typing import Callable

import pandas as pd
import streamlit as st

from db import repository as repo
from modules.guides import guide_for

# Modo oscuro: se invierte toda la página (luminosidad) conservando el tono, y
# se vuelve a invertir lo que no debe cambiar (imágenes). Los fondos se aclaran
# un poco antes de invertir para que el resultado sea gris oscuro y no negro.
_DARK_CSS = """
<style>
/* Se invierte la luminosidad de toda la página conservando el tono; los
   valores de abajo son los colores CLAROS previos a invertir (el resultado es
   un gris azulado oscuro con buen contraste). */
html { filter: invert(1) hue-rotate(180deg); }
img, video { filter: invert(1) hue-rotate(180deg); }
.stApp { background: #D9DBE6 !important; }
section[data-testid="stSidebar"] { background: #E6E8F1 !important; }
.mrp-stat-card, .mrp-panel, .mrp-card { background: #C9CCDB !important; border-color: rgba(0,0,0,.18) !important; }
/* contenedores con borde (filas de lista): más claros que el fondo y con borde visible */
div[data-testid="stVerticalBlock"] { border-color: rgba(0,0,0,.28) !important; }
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]:has(.mrp-row) { background: #D0D3E1; }
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]:has(.mrp-row):hover { background: #C4C8DA; }
/* campos: algo más claros que el fondo para distinguirlos */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] { background: #C2C6D8 !important; }
div[data-testid="stExpander"] { background: #D0D3E1; border-color: rgba(0,0,0,.25) !important; }
button[kind="secondary"], button[kind="secondaryFormSubmit"] { background: #CDD0DF !important; }
/* textos secundarios: más oscuros antes de invertir = más claros al verlos */
.mrp-row-sub, .mrp-activity-sub, .mrp-stat-caption, .mrp-stat-label, .mrp-page-subtitle,
.mrp-sidebar-section, .mrp-brand-sub, div[data-testid="stCaptionContainer"] { color: #3A3F52 !important; }
.mrp-row-name, .mrp-activity-name, .mrp-stat-value, .mrp-page-title, .mrp-panel-title { color: #0B0D16 !important; }
/* el menú del sidebar vive en un iframe con fondo blanco: que adopte el del sidebar */
section[data-testid="stSidebar"] iframe { mix-blend-mode: multiply; }
</style>
"""

_CSS = """
<style>
/* ---------------------------------------------------------------------
   Pulido global: tipografía, botones, inputs, alertas, expander, modal.
   Se aplica a TODA la app (login incluido) porque ui.inject() corre antes
   de la pantalla de login en app.py.
   ------------------------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Bordes de cualquier st.container(border=True): esquinas más suaves y
   un tono de borde más discreto que el gris default. border-radius y
   border-color no hacen nada visible si el bloque no tiene borde, así que
   es seguro aplicarlo a todos los stVerticalBlock sin distinguirlos. */
div[data-testid="stVerticalBlock"] {
    border-radius: 12px;
    border-color: rgba(17, 24, 39, 0.08) !important;
}

/* Filas de lista (st.container(border=True) que contienen un .mrp-row):
   se resaltan al pasar el mouse. No hay selector propio para los
   contenedores con borde, pero este es el único que cubre solo esos. */
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]:has(.mrp-row) {
    transition: box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]:has(.mrp-row):hover {
    border-color: rgba(108, 92, 231, 0.45) !important;
    background: #FBFAFF;
    box-shadow: 0 6px 18px rgba(108, 92, 231, 0.10);
}

/* Validación en vivo (live_validation.py) y consejos de formulario */
.mrp-live {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    max-width: 78%;
    font-size: 12px;
    font-weight: 600;
    margin-top: 4px;
    line-height: 1.3;
}
.mrp-live-count { font-variant-numeric: tabular-nums; white-space: nowrap; opacity: 0.85; }
.mrp-tip {
    background: #F4F3FB;
    border: 1px dashed rgba(108, 92, 231, 0.35);
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 12.5px;
    color: #4B2FD1;
    margin-bottom: 8px;
}

/* Botones */
button[kind="primary"], button[kind="primaryFormSubmit"] {
    background: linear-gradient(135deg, #6C5CE7, #4B2FD1) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
    filter: brightness(1.08);
    box-shadow: 0 6px 16px rgba(108, 92, 231, 0.28);
    transform: translateY(-1px);
}
button[kind="secondary"], button[kind="secondaryFormSubmit"] {
    border-radius: 10px !important;
    border: 1px solid rgba(17, 24, 39, 0.14) !important;
    font-weight: 600 !important;
    transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}
button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover {
    border-color: #6C5CE7 !important;
    color: #6C5CE7 !important;
}

/* Inputs, selects y textareas (BaseWeb, atributos estables entre versiones) */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
    border-radius: 10px !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"]:focus-within {
    border-color: #6C5CE7 !important;
    box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.14) !important;
}

/* Checkbox: el cuadrito toma el morado de marca al marcarse */
label[data-baseweb="checkbox"] span:first-child {
    transition: all 0.15s ease;
    border-radius: 6px !important;
}

/* Alertas (st.info / st.success / st.warning / st.error) */
div[data-testid="stAlertContainer"] {
    border-radius: 12px !important;
    border: 1px solid transparent !important;
}
div[data-testid="stAlertContainer"]:has(div[data-testid="stAlertContentInfo"]) {
    background: #EFECFD !important;
    border-color: rgba(108, 92, 231, 0.18) !important;
}
div[data-testid="stAlertContainer"]:has(div[data-testid="stAlertContentSuccess"]) {
    background: #E3F9E9 !important;
    border-color: rgba(31, 146, 84, 0.2) !important;
}
div[data-testid="stAlertContainer"]:has(div[data-testid="stAlertContentWarning"]) {
    background: #FDEFD9 !important;
    border-color: rgba(214, 138, 12, 0.22) !important;
}
div[data-testid="stAlertContainer"]:has(div[data-testid="stAlertContentError"]) {
    background: #FCE9E9 !important;
    border-color: rgba(214, 69, 69, 0.2) !important;
}

/* Expander */
div[data-testid="stExpander"] {
    border-radius: 12px !important;
    border: 1px solid rgba(17, 24, 39, 0.08) !important;
    overflow: hidden;
}

/* Modal (st.dialog) */
div[data-testid="stDialog"] div[role="dialog"] {
    border-radius: 18px !important;
}

/* Scrollbar discreto */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(17, 24, 39, 0.16); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: rgba(108, 92, 231, 0.4); }

/* Encabezado de página: eyebrow + título grande */
.mrp-eyebrow {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6C5CE7;
    margin-bottom: 4px;
}
.mrp-page-title {
    font-size: 30px;
    font-weight: 800;
    margin: 0 0 4px 0;
    line-height: 1.2;
}
.mrp-page-subtitle {
    color: #6B7280;
    font-size: 14px;
    margin-bottom: 8px;
}

/* Tarjetas de estadística */
.mrp-stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin: 18px 0 8px 0;
}
.mrp-stat-card {
    background: #FFFFFF;
    border: 1px solid rgba(17,24,39,0.06);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 1px 3px rgba(17,24,39,0.04);
}
.mrp-stat-card .mrp-stat-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 14px;
}
.mrp-stat-card .mrp-stat-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #9095A6;
}
.mrp-stat-card .mrp-icon-badge {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: #EFECFD;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
}
.mrp-stat-card.mrp-warn .mrp-icon-badge {
    background: #FDEFD9;
}
.mrp-stat-card .mrp-stat-value {
    font-size: 30px;
    font-weight: 800;
    line-height: 1.1;
    color: #1F2333;
}
.mrp-stat-card .mrp-stat-caption {
    font-size: 12.5px;
    color: #9095A6;
    margin-top: 6px;
}

/* Paneles (contenedores generales tipo "card" para secciones) */
.mrp-panel {
    background: #FFFFFF;
    border: 1px solid rgba(17,24,39,0.06);
    border-radius: 16px;
    padding: 20px 22px;
    box-shadow: 0 1px 3px rgba(17,24,39,0.04);
    height: 100%;
}
.mrp-panel-title {
    font-size: 18px;
    font-weight: 800;
    margin: 2px 0 14px 0;
}

/* Lista de actividad reciente */
.mrp-activity-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid rgba(17,24,39,0.06);
}
.mrp-activity-item:last-child { border-bottom: none; }
.mrp-activity-name { font-weight: 700; font-size: 14px; color: #1F2333; }
.mrp-activity-sub { font-size: 12.5px; color: #9095A6; }
.mrp-activity-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 999px;
    background: #EFECFD;
    color: #6C5CE7;
    white-space: nowrap;
}
.mrp-activity-when {
    font-size: 11px;
    color: #B4B8C4;
    margin-top: 4px;
    white-space: nowrap;
}

/* Rótulo de sección arriba del menú lateral */
.mrp-sidebar-section {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #B4B8C4;
    margin: 4px 0 8px 4px;
}

/* Tarjetas de lista genéricas (proveedores, usuarios, materiales) */
.mrp-card {
    background: #FFFFFF;
    border: 1px solid rgba(17,24,39,0.06);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(17,24,39,0.04);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(17,24,39,0.06);
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.2rem;
}
.mrp-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}
.mrp-brand-badge {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: #6C5CE7;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
}
.mrp-brand-name { font-weight: 800; font-size: 16px; line-height: 1.1; color: #1F2333; }
.mrp-brand-sub { font-size: 12px; color: #9095A6; }

/* Avatar circular con inicial (proveedores, usuarios) */
.mrp-avatar {
    width: 38px;
    height: 38px;
    min-width: 38px;
    border-radius: 50%;
    background: #EFECFD;
    color: #6C5CE7;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
}
.mrp-row {
    display: flex;
    align-items: center;
    gap: 12px;
}
.mrp-row-name { font-weight: 700; font-size: 15px; color: #1F2333; }
.mrp-row-sub { font-size: 12.5px; color: #9095A6; }

/* Pastillas de estado / rol */
.mrp-pill {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 999px;
    white-space: nowrap;
}
.mrp-pill-purple { background: #EFECFD; color: #6C5CE7; }
.mrp-pill-green { background: #E3F9E9; color: #1F9254; }
.mrp-pill-red { background: #FCE9E9; color: #D64545; }
.mrp-pill-gray { background: #EEF0F4; color: #6B7280; }
.mrp-pill-amber { background: #FDEFD9; color: #B7740A; }
.mrp-pill-blue { background: #E3EFFD; color: #2563B8; }

/* Enlaces de contacto rápido (llamar / WhatsApp / correo) */
.mrp-links { display: flex; flex-wrap: wrap; gap: 6px; }
a.mrp-link {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    background: #F4F3FB;
    color: #4B2FD1 !important;
    text-decoration: none !important;
    white-space: nowrap;
    transition: background 0.15s ease, transform 0.15s ease;
}
a.mrp-link:hover { background: #EFECFD; transform: translateY(-1px); }

/* Móvil: menos relleno, tarjetas de stats en 2 columnas, títulos más chicos */
@media (max-width: 640px) {
    div[data-testid="stMainBlockContainer"] { padding: 3.5rem 1rem 4rem 1rem; }
    .mrp-page-title { font-size: 24px; }
    .mrp-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .mrp-stat-card { padding: 14px; }
    .mrp-stat-card .mrp-stat-value { font-size: 24px; }
    .mrp-panel { padding: 16px; }
}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    if st.session_state.get("dark_mode"):
        st.markdown(_DARK_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "", action_label: str | None = None, action_key: str | None = None) -> bool:
    """Encabezado de página. Si se pasa `action_label`, dibuja un botón
    primario a la derecha (tipo "+ Crear...") y devuelve True si se clickeó."""
    html = f'<div class="mrp-eyebrow">{eyebrow}</div><div class="mrp-page-title">{title}</div>'
    if subtitle:
        html += f'<div class="mrp-page-subtitle">{subtitle}</div>'

    guide = guide_for(eyebrow, title)

    if not action_label:
        st.markdown(html, unsafe_allow_html=True)
        _guide_popover(guide)
        return False

    col1, col2 = st.columns([4, 1.3])
    with col1:
        st.markdown(html, unsafe_allow_html=True)
        _guide_popover(guide)
    with col2:
        st.write("")
        st.write("")
        clicked = st.button(action_label, key=action_key, type="primary", use_container_width=True)
    return clicked


def _guide_popover(guide: str | None) -> None:
    if guide:
        with st.popover("❓ Cómo usar"):
            st.markdown(guide)


def tip(text: str) -> None:
    """Consejo breve con ejemplo, para el inicio de un formulario."""
    st.markdown(f'<div class="mrp-tip">💡 {text}</div>', unsafe_allow_html=True)


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
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Sí, eliminar", type="primary", use_container_width=True):
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
