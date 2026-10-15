"""Generación de reportes descargables: Excel (openpyxl) y PDF (fpdf2) a
partir de DataFrames ya preparados (con encabezados legibles)."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from fpdf import FPDF

from utils import money


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
    expected = str(order.get("expected_date") or "")
    if expected and expected not in ("None", "nan", "NaT"):
        line("Entrega prometida:", f"{expected[8:10]}/{expected[5:7]}/{expected[:4]}")
    line("Moneda:", money.CURRENCY_NAMES.get(order.get("currency") or money.BASE))
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

    sym = money.symbol(order.get("currency"))
    tax_rate = float(order.get("tax_rate") or 0)
    if tax_rate:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(sum(widths[:4]), 7, "Subtotal", border=1, align="R")
        pdf.cell(widths[4], 7, f"{total:,.2f}", border=1, align="R")
        pdf.ln()
        pdf.cell(sum(widths[:4]), 7, f"IGV ({tax_rate:.0%})", border=1, align="R")
        pdf.cell(widths[4], 7, f"{total * tax_rate:,.2f}", border=1, align="R")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(sum(widths[:4]), 9, _latin1(f"TOTAL ({sym})"), border=1, align="R")
    pdf.cell(widths[4], 9, f"{total * (1 + tax_rate):,.2f}", border=1, align="R")
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
    tax_rate = float(order.get("tax_rate") or 0)
    cur = order.get("currency") or money.BASE
    if tax_rate:
        lines += ["", f"Subtotal: {money.fmt(total, cur)}", f"IGV ({tax_rate:.0%}): {money.fmt(total * tax_rate, cur)}"]
    lines += ["", f"Total: {money.fmt(total * (1 + tax_rate), cur)}"]
    expected = str(order.get("expected_date") or "")
    if expected and expected not in ("None", "nan", "NaT"):
        lines.append(f"Fecha de entrega solicitada: {expected[8:10]}/{expected[5:7]}/{expected[:4]}")
    if order.get("site_name"):
        lines.append(f"Entrega en: {order['site_name']}")
    if order.get("notes"):
        lines.append(f"Notas: {order['notes']}")
    lines.append("¿Me confirman disponibilidad y fecha de entrega? Gracias.")
    return "\n".join(lines)


def dispatch_pdf(voucher: dict, lines: pd.DataFrame) -> bytes:
    """Vale de salida (despacho de almacén a obra), con espacio para las firmas."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, _latin1(f"Vale de salida {voucher['code']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 6, _latin1(f"Fecha: {str(voucher['created_at'])[:16].replace('T', ' ')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    def line(label: str, value) -> None:
        if not value:
            return
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(34, 6, _latin1(label))
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _latin1(str(value)), new_x="LMARGIN", new_y="NEXT")

    line("Obra destino:", voucher.get("site_name"))
    line("Solicitado por:", voucher.get("requested_by"))
    line("Registrado por:", voucher.get("actor"))
    line("Nota:", voucher.get("note"))
    pdf.ln(4)

    widths = [110, 30, 40]
    heads = ["Material", "Unidad", "Cantidad"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(239, 236, 253)
    for head, w in zip(heads, widths):
        pdf.cell(w, 8, _latin1(head), border=1, fill=True, align="R" if head == "Cantidad" else "L")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    total_lines = 0
    for row in lines.to_dict("records"):
        total_lines += 1
        cells = [_latin1(str(row["material_name"]))[:62], _latin1(str(row.get("unit") or ""))[:16], f"{float(row['quantity']):,.2f}"]
        for i, (value, w) in enumerate(zip(cells, widths)):
            pdf.cell(w, 7, value, border=1, align="R" if i == 2 else "L")
        pdf.ln()
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 8, f"{total_lines} material(es) despachado(s)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    pdf.ln(22)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 6, "______________________________", new_x="RIGHT")
    pdf.cell(0, 6, "______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 5, _latin1("Entrega (almacén)"))
    pdf.cell(0, 5, _latin1("Recibe (" + (voucher.get("requested_by") or "solicitante") + ")"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def dispatch_text(voucher: dict, lines: pd.DataFrame) -> str:
    """Texto del vale de salida para el cuerpo de un correo o mensaje."""
    out = [f"Vale de salida {voucher['code']} · {str(voucher['created_at'])[:10]}", f"Obra: {voucher.get('site_name')}"]
    if voucher.get("stage"):
        out.append(f"Etapa: {voucher['stage']}")
    if voucher.get("requested_by"):
        out.append(f"Solicitado por: {voucher['requested_by']}")
    out.append("")
    for row in lines.to_dict("records"):
        unit = f" {row['unit']}" if row.get("unit") else ""
        out.append(f"- {row['material_name']}: {float(row['quantity']):g}{unit}")
    if voucher.get("note"):
        out += ["", f"Nota: {voucher['note']}"]
    return "\n".join(out)


def site_report_pdf(site: dict, prog: dict, materials: pd.DataFrame, stages: list[dict], vouchers: pd.DataFrame, workers: int) -> bytes:
    """Reporte imprimible de una obra: costo previsto frente a lo pedido, recibido y despachado, por material y por etapa.

    `materials`: tabla de `obras.progress_by_material`; `stages`: [{"stage", "budget", "dispatched"}] (en soles);
    `vouchers`: vales de la obra. Los importes van en soles y sin IGV."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    usable = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _latin1(f"Reporte de obra: {site['name']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 6, _latin1(f"{site.get('address') or 'sin direccion registrada'}   -   Generado el {datetime.now():%d/%m/%Y %H:%M}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    def heading(text: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _latin1(text), new_x="LMARGIN", new_y="NEXT")

    def table(columns: list[str], rows: list[list[str]], weights: list[float], right_from: int = 1) -> None:
        widths = [w / sum(weights) * usable for w in weights]

        def head() -> None:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(239, 236, 253)
            for i, (col, w) in enumerate(zip(columns, widths)):
                pdf.cell(w, 7, _latin1(col), border=1, fill=True, align="R" if i >= right_from else "L")
            pdf.ln()

        head()
        pdf.set_font("Helvetica", "", 8)
        for row in rows:
            if pdf.get_y() > pdf.h - 20:
                pdf.add_page()
                head()
                pdf.set_font("Helvetica", "", 8)
            for i, (value, w) in enumerate(zip(row, widths)):
                limit = max(int(w / 1.7), 4)
                text = _latin1(value)
                pdf.cell(w, 6, text if len(text) <= limit else text[: limit - 1] + "~", border=1, align="R" if i >= right_from else "L")
            pdf.ln()
        pdf.ln(3)

    def pct(value) -> str:
        return "-" if value is None else f"{value * 100:.0f} %"

    planned, ordered = float(prog.get("planned") or 0), float(prog.get("ordered") or 0)
    received = float(materials["Recibido $"].sum()) if not materials.empty else 0.0
    dispatched = float(materials["Despachado $"].sum()) if not materials.empty else 0.0
    heading("Resumen (S/, sin IGV)")
    table(
        ["Presupuesto", "Pedido", "Recibido", "Despachado (valorizado)", "Disponible (presupuesto - pedido)", "Avance de despacho", "Trabajadores", "Vales"],
        [[f"{planned:,.2f}", f"{ordered:,.2f}", f"{received:,.2f}", f"{dispatched:,.2f}", f"{planned - ordered:,.2f}", pct(prog.get("pct_consumed")), str(workers), str(len(vouchers))]],
        [1, 1, 1, 1.4, 1.8, 1.2, 1, 0.7], right_from=0,
    )

    heading(f"Materiales ({len(materials)})")
    if materials.empty:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 7, "Sin materiales presupuestados ni movimientos.", new_x="LMARGIN", new_y="NEXT")
    else:
        rows = [
            [
                str(m["Material"]), str(m.get("Unidad") or ""), f"{m['Presupuesto']:,.2f}", f"{m['Pedido']:,.2f}", f"{m['Recibido']:,.2f}",
                f"{m['Despachado']:,.2f}", f"{m['Presupuesto $']:,.2f}", f"{m['Gasto pedido $']:,.2f}", f"{m['Despachado $']:,.2f}",
                ("Fuera de presupuesto" if not m["Presupuesto"] else ("EXCEDE" if m["Pedido"] > m["Presupuesto"] + 1e-9 else "")),
            ]
            for m in materials.to_dict("records")
        ]
        table(
            ["Material", "Unidad", "Presup.", "Pedido", "Recibido", "Despach.", "Presup. S/", "Pedido S/", "Despach. S/", "Estado"],
            rows, [4, 1.6, 1.2, 1.2, 1.2, 1.2, 1.5, 1.5, 1.5, 2.2], right_from=2,
        )

    if stages:
        heading("Por etapa")
        table(
            ["Etapa", "Presupuesto S/", "Despachado S/", "Avance"],
            [[st_["stage"] or "Sin etapa", f"{st_['budget']:,.2f}", f"{st_['dispatched']:,.2f}", pct(min(st_["dispatched"] / st_["budget"], 1.0) if st_["budget"] else None)] for st_ in stages],
            [4, 2, 2, 1.5],
        )

    heading(f"Vales de salida ({len(vouchers)})")
    if vouchers.empty:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 7, "Aun no se despacho material a esta obra.", new_x="LMARGIN", new_y="NEXT")
    else:
        table(
            ["Vale", "Fecha", "Etapa", "Solicitado por", "Materiales"],
            [
                [str(v["code"]), str(v["created_at"])[:10], str(v.get("stage") or ""), str(v.get("requested_by") or ""), str(int(v["lines_count"]))]
                for v in vouchers.to_dict("records")
            ],
            [1.5, 1.5, 2, 3, 1.2], right_from=4,
        )
    return bytes(pdf.output())
