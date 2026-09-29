"""CSS compartido y componentes visuales reutilizables (encabezado de página,
tarjetas de stat, lista de actividad, dona de estado) para que todos los
módulos se vean consistentes."""
import streamlit as st

_CSS = """
<style>
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
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    html = f'<div class="mrp-eyebrow">{eyebrow}</div><div class="mrp-page-title">{title}</div>'
    if subtitle:
        html += f'<div class="mrp-page-subtitle">{subtitle}</div>'
    st.markdown(html, unsafe_allow_html=True)


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


def activity_item(name: str, sub: str, badge: str) -> str:
    return (
        '<div class="mrp-activity-item">'
        f'<div><div class="mrp-activity-name">{name}</div><div class="mrp-activity-sub">{sub}</div></div>'
        f'<div class="mrp-activity-badge">{badge}</div>'
        "</div>"
    )


def activity_list(items: list[str]) -> str:
    return "".join(items) if items else '<div class="mrp-activity-sub">Todavía no hay actividad.</div>'
