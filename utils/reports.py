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


def order_pdf(order: dict, items: pd.DataFrame, supplier: dict | None = None) -> bytes:
    """PDF de una sola orden de compra, listo para imprimir o mandar al proveedor."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, _latin1(f"Orden de compra {order['code']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 6, _latin1(f"Fecha: {str(order['created_at'])[:10]}   -   Estado: {order['status']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    def line(label: str, value) -> None:
        if not value:
            return
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(32, 6, _latin1(label))
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _latin1(str(value)), new_x="LMARGIN", new_y="NEXT")

    line("Proveedor:", order["supplier_name"])
    if supplier:
        line("Contacto:", supplier.get("contact_name"))
        line("Teléfono:", supplier.get("phone"))
        line("Correo:", supplier.get("email"))
    line("Obra destino:", order.get("site_name"))
    line("Notas:", order.get("notes"))
    pdf.ln(4)

    widths = [80, 22, 28, 28, 32]
    heads = ["Material", "Unidad", "Cantidad", "Precio unit.", "Subtotal"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(239, 236, 253)
    for head, w in zip(heads, widths):
        pdf.cell(w, 8, _latin1(head), border=1, fill=True, align="L" if head in ("Material", "Unidad") else "R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    total = 0.0
    for row in items.to_dict("records"):
        subtotal = float(row["quantity"]) * float(row["unit_price"])
        total += subtotal
        cells = [
            _latin1(str(row["material_name"]))[:48],
            _latin1(str(row.get("unit") or ""))[:12],
            f"{float(row['quantity']):,.2f}",
            f"{float(row['unit_price']):,.2f}",
            f"{subtotal:,.2f}",
        ]
        for i, (value, w) in enumerate(zip(cells, widths)):
            pdf.cell(w, 7, value, border=1, align="L" if i < 2 else "R")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(sum(widths[:4]), 9, "TOTAL", border=1, align="R")
    pdf.cell(widths[4], 9, f"{total:,.2f}", border=1, align="R")
    pdf.ln(18)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(80, 6, "______________________________", new_x="RIGHT")
    pdf.cell(0, 6, "______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(80, 5, "Autoriza")
    pdf.cell(0, 5, "Recibe proveedor", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def order_whatsapp_text(order: dict, items: pd.DataFrame) -> str:
    """Texto del pedido para abrir en WhatsApp."""
    lines = [f"Hola {order['supplier_name']}, quisiera hacer el siguiente pedido ({order['code']}):", ""]
    total = 0.0
    for row in items.to_dict("records"):
        subtotal = float(row["quantity"]) * float(row["unit_price"])
        total += subtotal
        unit = f" {row['unit']}" if row.get("unit") else ""
        lines.append(f"- {row['material_name']}: {float(row['quantity']):g}{unit} x {float(row['unit_price']):,.2f} = {subtotal:,.2f}")
    lines += ["", f"Total: {total:,.2f}"]
    if order.get("site_name"):
        lines.append(f"Entrega en: {order['site_name']}")
    if order.get("notes"):
        lines.append(f"Notas: {order['notes']}")
    lines.append("¿Me confirman disponibilidad y fecha de entrega? Gracias.")
    return "\n".join(lines)
