"""Ventana de ayuda «Cómo usar»: una guía por pantalla, dibujada siempre igual.

La ventana abre con un encabezado (icono, nombre de la pantalla y para qué sirve) y tres pestañas:

    Paso a paso           los pasos agrupados por tarea, numerados y con «dónde está» cada cosa
    Ejemplo               un caso real contado en pocos pasos
    Consejos y avisos     consejos, cosas a tener en cuenta y lo que el sistema NO hace

El contenido vive en `modules/guides.py` como datos; los estilos, en `modules/styles/45_help.css`."""
from __future__ import annotations

import html
import re

import streamlit as st

from utils.icons import svg

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`(.+?)`")
_ITALIC = re.compile(r"(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])")


def inline(text: str) -> str:
    """Texto de una guía a HTML seguro: se escapa todo y solo se admiten `**negrita**`, `*cursiva*` y `` `código` ``."""
    out = html.escape(str(text or ""), quote=False)
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return _ITALIC.sub(r"<em>\1</em>", out)


def count_steps(guide: dict) -> int:
    return sum(len(section["steps"]) for section in guide.get("sections", []))


def hero_html(guide: dict) -> str:
    chips = [f"{count_steps(guide)} pasos"]
    if guide.get("example"):
        chips.append("con ejemplo")
    if guide.get("warnings"):
        chips.append("con avisos")
    chips_html = "".join('<span class="mrp-help-chip">' + html.escape(c) + "</span>" for c in chips)
    return (
        '<div class="mrp-help-hero">'
        f'<div class="mrp-help-badge">{svg(guide.get("icon", "info"), 26, 1.8)}</div>'
        '<div class="mrp-help-hero-text">'
        '<div class="mrp-help-kicker">Guía rápida</div>'
        f'<div class="mrp-help-title">{html.escape(guide.get("title", ""))}</div>'
        f'<div class="mrp-help-summary">{inline(guide.get("summary", ""))}</div>'
        f'<div class="mrp-help-meta">{chips_html}</div>'
        "</div></div>"
    )


def steps_html(guide: dict) -> str:
    """Los pasos de la guía, agrupados por tarea y numerados de corrido (1, 2, 3…)."""
    parts, number = [], 0
    sections = guide.get("sections", [])
    for index, section in enumerate(sections, start=1):
        label = f"Parte {index} de {len(sections)}" if len(sections) > 1 else "Pasos"
        parts.append(
            f'<div class="mrp-help-sec"><span class="mrp-help-sec-no">{html.escape(label)}</span>'
            f'<span class="mrp-help-sec-title">{html.escape(section["title"])}</span></div><ol class="mrp-help-steps">'
        )
        for step in section["steps"]:
            number += 1
            where = f'<span class="mrp-help-where">{svg("pin", 13, 2.2)}{html.escape(step["where"])}</span>' if step.get("where") else ""
            parts.append(
                f'<li><span class="mrp-help-num">{number}</span><div class="mrp-help-card">'
                f'<div class="mrp-help-st">{html.escape(step["title"])}</div>'
                f'<div class="mrp-help-tx">{inline(step["text"])}</div>{where}</div></li>'
            )
        parts.append("</ol>")
    return "".join(parts)


def example_html(guide: dict) -> str:
    example = guide.get("example")
    if not example:
        return ""
    items = "".join(f'<li><span class="mrp-help-dot"></span><div>{inline(step)}</div></li>' for step in example["steps"])
    return (
        '<div class="mrp-help-example">'
        f'<div class="mrp-help-example-head">{svg("bulb", 18, 2)}<span>Ejemplo</span></div>'
        f'<div class="mrp-help-example-title">{inline(example["title"])}</div>'
        f'<ol class="mrp-help-timeline">{items}</ol></div>'
    )


def callouts_html(guide: dict) -> str:
    blocks = []
    for kind, icon, heading, key in (
        ("tip", "bulb", "Consejo", "tips"),
        ("warn", "alert", "Ten en cuenta", "warnings"),
        ("no", "info", "Lo que el sistema no hace", "not_does"),
    ):
        for text in guide.get(key, []):
            blocks.append(
                f'<div class="mrp-help-callout mrp-help-{kind}"><span class="mrp-help-callout-ico">{svg(icon, 18, 2)}</span>'
                f'<div><div class="mrp-help-callout-head">{heading}</div><div class="mrp-help-tx">{inline(text)}</div></div></div>'
            )
    return "".join(blocks)


@st.dialog("Cómo usar", width="large")
def help_dialog(guide: dict) -> None:
    st.markdown(hero_html(guide), unsafe_allow_html=True)
    names = ["Paso a paso"]
    if guide.get("example"):
        names.append("Ejemplo")
    extras = callouts_html(guide)
    if extras:
        names.append("Consejos y avisos")
    tabs = st.tabs(names)
    with tabs[0]:
        st.markdown(steps_html(guide), unsafe_allow_html=True)
    for name, tab in zip(names[1:], tabs[1:]):
        with tab:
            st.markdown(example_html(guide) if name == "Ejemplo" else extras, unsafe_allow_html=True)
    if st.button("Entendido", key="help_close", type="primary", width="stretch"):
        st.rerun()


def help_button(guide: dict | None) -> None:
    """Botón «Cómo usar» de una pantalla; al pulsarlo abre su guía."""
    if not guide:
        return
    if st.button("Cómo usar", key=f"help_open_{guide.get('title', 'guia')}", icon=":material/help:", help="Explica esta pantalla paso a paso."):
        help_dialog(guide)
