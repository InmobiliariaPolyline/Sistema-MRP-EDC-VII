"""Dibujo del Manual de usuario: capítulos, procedimientos con maquetas fieles de los formularios, flujo, glosario y preguntas.

El contenido está en `modules/manual_data.py`; los estilos, en `modules/styles/47_manual.css`. Aquí solo se convierte
ese contenido en HTML (funciones puras, fáciles de probar) y se arma la pantalla con Streamlit.

La pieza central es la **maqueta**: una réplica del formulario o la pantalla real con los mismos títulos, campos y botones,
y números que remiten a los pasos de al lado. Quien lee el manual ve exactamente lo que va a encontrar."""
from __future__ import annotations

import html
import unicodedata

import streamlit as st

from modules import manual_data as data
from modules import ui
from modules.help_ui import callouts_html, inline
from utils.icons import svg

CHAPTER_KEY = "manual_chapter"
TONE = {"good": "green", "warn": "amber", "info": "blue", "accent": "purple", "bad": "red", "gray": "gray"}
MENU_ICONS = {
    "Dashboard": "home", "Órdenes de compra": "order", "Proveedores": "truck", "Materiales": "box", "Inventario": "layers",
    "Obras": "building", "Asistencia": "calendar", "Trabajadores": "user", "Reportes": "list", "Historial": "clock",
    "Respaldo": "shield", "Sistema": "info", "Manual de Usuario": "bulb",
}
FAQ_CHAPTER = {"id": "faq", "title": "Preguntas y glosario", "icon": "search", "summary": "Respuestas rápidas y el significado de cada término."}


def chapters() -> list[dict]:
    """Todos los capítulos en orden, con el de preguntas y glosario al final."""
    return [*data.CHAPTERS, FAQ_CHAPTER]


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


# ---------------------------------------------------------------------------------------------------------------------
# Maqueta de un formulario o pantalla
# ---------------------------------------------------------------------------------------------------------------------

def _mark(n) -> str:
    return f'<span class="mrp-mock-mark">{int(n)}</span>' if n else ""


def field_html(field: dict) -> str:
    """Un campo del formulario: etiqueta, caja con su valor o texto de ayuda, y la marca del paso."""
    kind = field.get("kind", "text")
    label, value, placeholder = field["field"], field.get("value"), field.get("placeholder")
    if kind == "check":
        checked = " on" if field.get("checked") else ""
        return (
            f'<div class="mrp-mock-field"><div class="mrp-mock-check"><span class="mrp-mock-box{checked}">'
            f'{svg("check", 12, 3.2) if checked else ""}</span><span>{esc(label)}</span>{_mark(field.get("mark"))}</div></div>'
        )
    shown = f"<span>{esc(value)}</span>" if value not in (None, "") else f'<span class="ph">{esc(placeholder or "")}</span>'
    extra = ""
    classes = "mrp-mock-input"
    if kind == "select":
        classes += " mrp-mock-select"
        extra = '<span class="mrp-mock-chev"></span>'
    elif kind == "number":
        classes += " mrp-mock-number"
        extra = '<span class="mrp-mock-step"><i>−</i><i>+</i></span>'
    elif kind == "date":
        extra = f'<span class="mrp-mock-ico">{svg("calendar", 15, 2)}</span>'
    elif kind == "password":
        shown = '<span class="dots">••••••••</span>'
        extra = f'<span class="mrp-mock-ico">{svg("lock", 15, 2)}</span>'
    elif kind == "textarea":
        classes += " tall"
    if field.get("disabled"):
        classes += " disabled"
    return (
        f'<div class="mrp-mock-field"><div class="mrp-mock-label">{esc(label)}{_mark(field.get("mark"))}</div>'
        f'<div class="{classes}">{shown}{extra}</div></div>'
    )


def _cell(value) -> str:
    if isinstance(value, dict) and "pill" in value:
        return f'<span class="mrp-pill mrp-pill-{TONE.get(value.get("tone", "gray"), "gray")}">{esc(value["pill"])}</span>'
    return esc(value)


def _row_html(row: dict) -> str:
    """Una fila de la maqueta (ver el docstring de `manual_data` para los tipos)."""
    mark = row.get("mark")
    if "sec" in row:
        return f'<div class="mrp-mock-sec">{esc(row["sec"])}</div>'
    if "field" in row:
        return field_html(row)
    if "fields" in row:
        return f'<div class="mrp-mock-cols c{len(row["fields"])}">{"".join(field_html(f) for f in row["fields"])}</div>'
    if "tabs" in row:
        tabs = "".join(f'<span class="mrp-mock-tab{" on" if i == row.get("active", 0) else ""}">{esc(t)}</span>' for i, t in enumerate(row["tabs"]))
        return f'<div class="mrp-mock-tabs">{tabs}{_mark(mark)}</div>'
    if "note" in row:
        return f'<div class="mrp-mock-note {esc(row.get("tone", "info"))}">{inline(row["note"])}{_mark(mark)}</div>'
    if "pills" in row:
        pills = "".join(f'<span class="mrp-pill mrp-pill-{TONE.get(t, "gray")}">{esc(text)}</span>' for text, t in row["pills"])
        return f'<div class="mrp-mock-pills">{pills}{_mark(mark)}</div>'
    if "stats" in row:
        cells = "".join(f'<div><span class="k">{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in row["stats"])
        return f'<div class="mrp-mock-stats c{len(row["stats"])}">{cells}{_mark(mark)}</div>'
    if "lines" in row:
        items = "".join(f'<div class="mrp-mock-line"><span>{esc(a)}</span><b>{esc(b)}</b><i>✕</i></div>' for a, b in row["lines"])
        return f'<div class="mrp-mock-lines">{items}</div>'
    if "table" in row:
        table = row["table"]
        head = "".join(f"<th>{esc(c)}</th>" for c in table["cols"])
        body = "".join("<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in r) + "</tr>" for r in table["rows"])
        return f'<div class="mrp-mock-tablewrap"><table class="mrp-mock-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{_mark(table.get("mark"))}</div>'
    if "buttons" in row:
        buttons = []
        for button in row["buttons"]:
            text, style, *rest = button
            buttons.append(f'<span class="mrp-mock-btn {esc(style)}">{esc(text)}{_mark(rest[0]) if rest else ""}</span>')
        return f'<div class="mrp-mock-btns">{"".join(buttons)}</div>'
    if "menu" in row:
        groups = []
        for group, items in row["menu"]:
            entries = "".join(
                f'<div class="mrp-mock-item{" on" if item == row.get("active") else ""}">{svg(MENU_ICONS.get(item, "info"), 15, 2)}<span>{esc(item)}</span></div>'
                for item in items
            )
            groups.append(f'<div class="mrp-mock-group">{esc(group)}</div>{entries}')
        return f'<div class="mrp-mock-menu">{"".join(groups)}{_mark(mark)}</div>'
    if "signatures" in row:
        lines = "".join(f'<div><span class="line"></span><span class="who">{esc(s)}</span></div>' for s in row["signatures"])
        return f'<div class="mrp-mock-sign">{lines}{_mark(mark)}</div>'
    if "caption" in row:
        return f'<div class="mrp-mock-caption">{esc(row["caption"])}</div>'
    raise ValueError(f"Fila de maqueta desconocida: {list(row)}")


def mock_html(mock: dict) -> str:
    """La maqueta completa: ventana con barra de título y las filas del formulario."""
    rows = "".join(_row_html(row) for row in mock["rows"])
    return (
        '<div class="mrp-mock"><div class="mrp-mock-bar"><span class="mrp-mock-dots"><i></i><i></i><i></i></span>'
        f'<span class="mrp-mock-title">{esc(mock["title"])}</span></div><div class="mrp-mock-body">{rows}</div>'
        '<div class="mrp-mock-foot">Así se ve en el sistema · los números te remiten a los pasos</div></div>'
    )


# ---------------------------------------------------------------------------------------------------------------------
# Bloques ilustrados
# ---------------------------------------------------------------------------------------------------------------------

def flow_html() -> str:
    cards = "".join(
        f'<div class="mrp-man-flow-card"><span class="mrp-man-flow-no">{i}</span><span class="mrp-man-flow-ico">{svg(s["icon"], 24, 1.8)}</span>'
        f'<div class="mrp-man-flow-title">{esc(s["title"])}</div><div class="mrp-man-flow-text">{esc(s["text"])}</div></div>'
        for i, s in enumerate(data.FLOW, start=1)
    )
    return f'<div class="mrp-man-flow">{cards}</div>'


def compare_html() -> str:
    def column(kind: str, title: str, icon: str, items: list[str]) -> str:
        lis = "".join(f'<li><span class="mrp-man-bullet">{svg(icon, 14, 3)}</span><span>{inline(t)}</span></li>' for t in items)
        return f'<div class="mrp-man-compare-card {kind}"><div class="mrp-man-compare-head">{title}</div><ul>{lis}</ul></div>'

    return (
        '<div class="mrp-man-compare">'
        + column("yes", "Lo que sí hace", "check", data.DOES)
        + column("no", "Lo que no hace", "x", data.DOES_NOT)
        + "</div>"
    )


def roadmap_html() -> str:
    items = "".join(
        f'<li><span class="mrp-man-road-no">{i}</span><div><div class="mrp-man-road-title">{esc(s["title"])}</div>'
        f'<div class="mrp-man-road-text">{inline(s["text"])}</div><span class="mrp-help-where">{svg("pin", 13, 2.2)}{esc(s["where"])}</span></div></li>'
        for i, s in enumerate(data.ROADMAP, start=1)
    )
    return f'<ol class="mrp-man-road">{items}</ol>'


def states_html() -> str:
    states = [
        ("Pendiente", "warn", "Creada, todavía no enviada al proveedor."),
        ("Enviada", "info", "Ya se comunicó al proveedor (WhatsApp, correo o llamada)."),
        ("Recibida parcial", "accent", "Llegó solo una parte del material."),
        ("Recibida", "good", "Llegó todo: ya está en el stock."),
    ]
    cards = "".join(
        f'<div class="mrp-man-state"><span class="mrp-pill mrp-pill-{TONE[t]}">{esc(name)}</span><div>{esc(text)}</div></div>' for name, t, text in states
    )
    return (
        f'<div class="mrp-man-states-title">Los estados de una orden</div><div class="mrp-man-states">{cards}</div>'
        '<div class="mrp-man-states-note"><span class="mrp-pill mrp-pill-red">Cancelada</span> Una orden que no continúa se cancela; nunca se borra si ya recibió material.</div>'
    )


def stock_html() -> str:
    legend = [
        ("44 en stock", "good", "Hay material por encima del mínimo."),
        ("12 · stock bajo", "warn", "Está en o bajo el stock mínimo: conviene reponer."),
        ("Agotado", "bad", "Ya no queda nada."),
    ]
    cards = "".join(f'<div class="mrp-man-state"><span class="mrp-pill mrp-pill-{TONE[t]}">{esc(name)}</span><div>{esc(text)}</div></div>' for name, t, text in legend)
    return f'<div class="mrp-man-states-title">Cómo leer el stock</div><div class="mrp-man-states three">{cards}</div>'


def glossary_html() -> str:
    cards = "".join(f'<div class="mrp-man-term"><div class="mrp-man-term-name">{esc(name)}</div><div class="mrp-man-term-def">{inline(text)}</div></div>' for name, text in data.GLOSSARY)
    return f'<div class="mrp-man-glossary">{cards}</div>'


BLOCKS = {"flow": flow_html, "compare": compare_html, "roadmap": roadmap_html, "states": states_html, "stock": stock_html}


# ---------------------------------------------------------------------------------------------------------------------
# Procedimientos y capítulos
# ---------------------------------------------------------------------------------------------------------------------

def steps_html(steps: list[dict]) -> str:
    items = "".join(
        f'<li><span class="mrp-mock-mark big">{i}</span><div><div class="mrp-man-step-title">{esc(s["title"])}</div>'
        f'<div class="mrp-man-step-text">{inline(s["text"])}</div></div></li>'
        for i, s in enumerate(steps, start=1)
    )
    return f'<ol class="mrp-man-steps">{items}</ol>'


def proc_head_html(chapter_no: int, index: int, proc: dict) -> str:
    where = f'<span class="mrp-help-where">{svg("pin", 13, 2.2)}{esc(proc["where"])}</span>' if proc.get("where") else ""
    return (
        f'<div class="mrp-man-proc-head"><span class="mrp-man-proc-no">{chapter_no}.{index}</span>'
        f'<div class="mrp-man-proc-text"><div class="mrp-man-proc-title">{esc(proc["title"])}</div>'
        f'<div class="mrp-man-proc-goal">{inline(proc["goal"])}</div></div>{where}</div>'
    )


def chapter_head_html(position: int, total: int, chapter: dict, procedures: int) -> str:
    chips = f'<div class="mrp-help-meta"><span class="mrp-help-chip">{procedures} procedimientos</span></div>' if procedures else ""
    return (
        '<div class="mrp-help-hero mrp-man-hero">'
        f'<div class="mrp-help-badge">{svg(chapter["icon"], 26, 1.8)}</div><div class="mrp-help-hero-text">'
        f'<div class="mrp-help-kicker">Capítulo {position} de {total}</div><div class="mrp-help-title">{esc(chapter["title"])}</div>'
        f'<div class="mrp-help-summary">{inline(chapter["summary"])}</div>{chips}</div></div>'
    )


def _plain(text: str) -> str:
    """Minúsculas y sin tildes, para buscar sin importar acentos."""
    return "".join(c for c in unicodedata.normalize("NFD", str(text).lower()) if unicodedata.category(c) != "Mn")


def search(query: str) -> list[tuple[int, int, dict, dict]]:
    """Procedimientos que contienen todas las palabras de la búsqueda: [(n.º de capítulo, n.º de procedimiento, capítulo, procedimiento)]."""
    words = _plain(query).split()
    if not words:
        return []
    found = []
    for c_no, chapter in enumerate(data.CHAPTERS, start=1):
        for p_no, proc in enumerate(chapter["procedures"], start=1):
            haystack = _plain(
                " ".join([proc["title"], proc["goal"], proc.get("where", ""), chapter["title"]] + [f"{s['title']} {s['text']}" for s in proc["steps"]]
                         + proc.get("tips", []) + proc.get("warnings", []) + proc.get("not_does", []))
            )
            if all(w in haystack for w in words):
                found.append((c_no, p_no, chapter, proc))
    return found


def render_procedure(chapter_no: int, index: int, proc: dict) -> None:
    with st.container(border=True, key=f"man_proc_{chapter_no}_{index}"):
        st.markdown(proc_head_html(chapter_no, index, proc), unsafe_allow_html=True)
        extras = callouts_html({"tips": proc.get("tips", []), "warnings": proc.get("warnings", []), "not_does": proc.get("not_does", [])})
        if proc.get("mock"):
            left, right = st.columns([5, 6], gap="large")
            with left:
                st.markdown(mock_html(proc["mock"]), unsafe_allow_html=True)
            with right:
                st.markdown(steps_html(proc["steps"]) + extras, unsafe_allow_html=True)
        else:
            st.markdown(steps_html(proc["steps"]) + extras, unsafe_allow_html=True)


def _go(chapter_id: str) -> None:
    st.session_state[CHAPTER_KEY] = chapter_id


def render_chapter(position: int, chapter: dict) -> None:
    all_chapters = chapters()
    if chapter["id"] == "faq":
        st.markdown(chapter_head_html(position, len(all_chapters), chapter, 0), unsafe_allow_html=True)
        st.markdown('<div class="mrp-man-h">Preguntas frecuentes</div>', unsafe_allow_html=True)
        for question, answer in data.FAQ:
            with st.expander(question):
                st.markdown(answer)
        st.markdown('<div class="mrp-man-h">Glosario</div>', unsafe_allow_html=True)
        st.markdown(glossary_html(), unsafe_allow_html=True)
    else:
        st.markdown(chapter_head_html(position, len(all_chapters), chapter, len(chapter["procedures"])), unsafe_allow_html=True)
        for block in chapter.get("blocks", []):
            if block == "flow":
                st.markdown('<div class="mrp-man-h">El recorrido de una compra</div>', unsafe_allow_html=True)
            if block == "roadmap":
                st.markdown('<div class="mrp-man-h">Tu ruta para empezar</div>', unsafe_allow_html=True)
            st.markdown(BLOCKS[block](), unsafe_allow_html=True)
        if chapter["procedures"]:
            st.markdown('<div class="mrp-man-h">Paso a paso</div>', unsafe_allow_html=True)
        for index, proc in enumerate(chapter["procedures"], start=1):
            render_procedure(position, index, proc)
    prev_col, _, next_col = st.columns([1.4, 3, 1.4])
    if position > 1:
        previous = all_chapters[position - 2]
        prev_col.button(f"← {previous['title']}", key=f"man_prev_{chapter['id']}", on_click=_go, args=(previous["id"],), width="stretch")
    if position < len(all_chapters):
        following = all_chapters[position]
        next_col.button(f"{following['title']} →", key=f"man_next_{chapter['id']}", on_click=_go, args=(following["id"],), type="primary", width="stretch")


def render() -> None:
    ui.page_header(
        "Ayuda",
        "Manual de usuario",
        "Aprende el sistema de principio a fin: cada procedimiento muestra el formulario tal como lo verás y los pasos para completarlo.",
    )
    all_chapters = chapters()
    ids = [c["id"] for c in all_chapters]
    if st.session_state.get(CHAPTER_KEY) not in ids:
        st.session_state[CHAPTER_KEY] = ids[0]
    titles = {c["id"]: f"{i}. {c['title']}" for i, c in enumerate(all_chapters, start=1)}
    st.segmented_control("Capítulo", ids, format_func=titles.get, key=CHAPTER_KEY, required=True, label_visibility="collapsed")
    query = st.text_input("Buscar en el manual", placeholder="Buscar un procedimiento: «recepción», «IGV», «vale», «presupuesto»…", key="manual_query", max_chars=80)
    if query.strip():
        results = search(query)
        ui.result_count(len(results), sum(len(c["procedures"]) for c in data.CHAPTERS), noun="procedimientos")
        if not results:
            ui.empty_state("Sin resultados", "Prueba con otra palabra, o limpia la búsqueda para ver los capítulos.", icon="🔎")
            return
        for c_no, p_no, _chapter, proc in results:
            render_procedure(c_no, p_no, proc)
        return
    chapter = next(c for c in all_chapters if c["id"] == st.session_state[CHAPTER_KEY])
    render_chapter(ids.index(chapter["id"]) + 1, chapter)
