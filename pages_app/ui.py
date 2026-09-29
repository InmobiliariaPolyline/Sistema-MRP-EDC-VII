"""CSS compartido y componentes visuales reutilizables (tarjetas de stat,
tarjetas de lista) para que todos los módulos se vean consistentes."""
import streamlit as st

_CSS = """
<style>
/* Tarjetas de estadística del Dashboard */
.mrp-stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
}
.mrp-stat-card {
    background: linear-gradient(155deg, rgba(47,128,237,0.16), rgba(255,255,255,0.03));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 18px 20px;
    display: flex;
    align-items: center;
    gap: 14px;
}
.mrp-stat-card .mrp-icon {
    font-size: 28px;
    line-height: 1;
}
.mrp-stat-card .mrp-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.1;
}
.mrp-stat-card .mrp-label {
    font-size: 13px;
    opacity: 0.72;
}
.mrp-stat-card.mrp-warn {
    background: linear-gradient(155deg, rgba(237,168,47,0.18), rgba(255,255,255,0.03));
}

/* Tarjetas de lista (proveedores, usuarios, materiales) */
.mrp-card {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.02);
}

/* Sidebar: separar el menú del resto y afinar el logo */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.2rem;
}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def stat_card(icon: str, value, label: str, warn: bool = False) -> str:
    klass = "mrp-stat-card mrp-warn" if warn else "mrp-stat-card"
    return (
        f'<div class="{klass}">'
        f'<div class="mrp-icon">{icon}</div>'
        f'<div><div class="mrp-value">{value}</div><div class="mrp-label">{label}</div></div>'
        f"</div>"
    )


def stat_grid(cards: list[str]) -> None:
    st.markdown(f'<div class="mrp-stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
