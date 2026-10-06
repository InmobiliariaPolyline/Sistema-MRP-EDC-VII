"""Generación de reportes descargables: Excel (openpyxl) y PDF (fpdf2) a
partir de DataFrames ya preparados (con encabezados legibles)."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from fpdf import FPDF


def _cell_text(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _latin1(text: str) -> str:
    """Las fuentes base del PDF solo cubren latin-1: tildes y ñ sí, pero otros
    símbolos (guiones largos, comillas tipográficas) se sustituyen."""
    replacements = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "·": "-"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def to_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Un libro de Excel con una hoja por dataset."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe_name = name[:31]  # límite de Excel para el nombre de hoja
            df.to_excel(writer, sheet_name=safe_name, index=False)
            ws = writer.sheets[safe_name]
            for column_cells in ws.columns:
                longest = max((len(_cell_text(c.value)) for c in column_cells), default=8)
                ws.column_dimensions[column_cells[0].column_letter].width = min(max(longest + 2, 10), 50)
            ws.freeze_panes = "A2"
    return buffer.getvalue()


def to_pdf(title: str, sections: dict[str, pd.DataFrame]) -> bytes:
    """Un PDF horizontal con una tabla por dataset."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _latin1(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, _latin1(f"Generado el {datetime.now():%d/%m/%Y %H:%M}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    usable_width = pdf.w - pdf.l_margin - pdf.r_margin

    for heading, df in sections.items():
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, _latin1(f"{heading} ({len(df)})"), new_x="LMARGIN", new_y="NEXT")

        if df.empty:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 7, "Sin registros.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
            continue

        columns = list(df.columns)
        rows = [[_latin1(_cell_text(v)) for v in row] for row in df.itertuples(index=False, name=None)]
        # ancho proporcional al contenido más largo de cada columna
        weights = [
            min(max(len(_latin1(str(col))), *(len(r[i]) for r in rows[:200])) + 2, 40) for i, col in enumerate(columns)
        ]
        widths = [w / sum(weights) * usable_width for w in weights]

        def draw_header() -> None:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(239, 236, 253)
            for col, w in zip(columns, widths):
                pdf.cell(w, 7, _latin1(str(col))[:40], border=1, fill=True)
            pdf.ln()

        draw_header()
        pdf.set_font("Helvetica", "", 8)
        for row in rows:
            if pdf.get_y() > pdf.h - 20:
                pdf.add_page()
                draw_header()
                pdf.set_font("Helvetica", "", 8)
            for value, w in zip(row, widths):
                max_chars = max(int(w / 1.7), 4)
                pdf.cell(w, 6, value if len(value) <= max_chars else value[: max_chars - 1] + "~", border=1)
            pdf.ln()
        pdf.ln(5)

    return bytes(pdf.output())
