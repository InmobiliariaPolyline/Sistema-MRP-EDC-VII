"""Generación de reportes descargables: Excel (openpyxl) y PDF (fpdf2) a partir de DataFrames ya preparados.

Todos los PDF usan `utils/pdf_style.BrandPDF` (fuente Inter, colores de la app, portada, tablas, tarjetas e iconos)."""
from __future__ import annotations

import io


import pandas as pd

from utils import money
from utils.pdf_style import TONES, BrandPDF
from utils.pdf_style import MUTED as MUTED_TEXT
from utils.pdf_style import PAPER as PAPER_COLOR
from utils import clock


def _cell_text(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _date(value, with_time: bool = False) -> str:
    """«2026-10-12T09:30:00» → «12/10/2026» (o «12/10/2026 09:30»)."""
    text = str(value or "")
    if len(text) < 10 or text in ("None", "nan", "NaT"):
        return ""
    text = clock.local(text)
    out = f"{text[8:10]}/{text[5:7]}/{text[:4]}"
    return f"{out} {text[11:16]}" if with_time and len(text) >= 16 else out


ORDER_STATUS = {
    "pendiente": ("Pendiente", "warn"), "enviada": ("Enviada", "info"), "parcial": ("Recibida parcial", "accent"),
    "recibida": ("Recibida", "good"), "cancelada": ("Cancelada", "bad"),
}


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


def to_pdf(title: str, sections: dict[str, pd.DataFrame], label: str = "Reporte del sistema", theme: str = "blue", style: str = "poster", icon: str = "chart") -> bytes:
    """Un PDF horizontal con portada y una tabla por conjunto de datos (números a la derecha, filas alternadas,
    encabezado que se repite en cada página y total de filas por sección)."""
    pdf = BrandPDF(title[:70], orientation="L", theme=theme, style=style)
    total_rows = sum(len(df) for df in sections.values())
    pdf.add_page()
    pdf.cover(
        label, title,
        [("Generado", f"{clock.now():%d/%m/%Y %H:%M}"), ("Contenido", f"{len(sections)} conjunto(s) · {total_rows:,} registro(s)")], icon=icon,
    )
    if len(sections) > 1:
        pdf.index_card([(name, len(df)) for name, df in sections.items()])
    for heading, df in sections.items():
        pdf.section(heading, "list", f"{len(df):,}")
        if style == "minimal" and "Saldo" in df.columns and len(df) >= 2:
            balances = [float(v) for v in df["Saldo"] if v == v and v is not None]
            if len(balances) >= 2:
                top = pdf.get_y()
                pdf.box(pdf.l_margin, top, pdf.usable, 40, fill=PAPER_COLOR)
                pdf.font(7.6, semi=True, color=pdf.accent_dark)
                pdf.set_xy(pdf.l_margin + 5, top + 3)
                pdf.cell(80, 4, "EVOLUCIÓN DEL SALDO")
                pdf.font(7.6, color=MUTED_TEXT)
                pdf.set_xy(pdf.w - pdf.r_margin - 85, top + 3)
                pdf.cell(80, 4, f"{len(balances)} movimientos · saldo final {balances[-1]:,.0f}", align="R")
                pdf.linechart(pdf.l_margin + 3, top + 8, pdf.usable - 6, 30, balances, tone="good")
                pdf.set_y(top + 45)
        if df.empty:
            pdf.font(9, color=MUTED_TEXT)
            pdf.cell(0, 7, "Sin registros.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
            continue
        columns = [str(c) for c in df.columns]
        raw_rows = list(df.itertuples(index=False, name=None))
        rows = [[_cell_text(v) for v in row] for row in raw_rows]
        numeric = [all(_is_number(r[i]) or r[i] is None or (isinstance(r[i], float) and r[i] != r[i]) for r in raw_rows[:200]) and any(_is_number(r[i]) for r in raw_rows[:200]) for i in range(len(columns))]
        weights = [min(max(len(columns[i]) * 0.9, *(len(r[i]) for r in rows[:200])) + 2, 40) for i in range(len(columns))]
        # valores con color según su signo: entradas y diferencias a favor en verde, salidas y faltantes en rojo
        green, red = TONES["good"][0], TONES["bad"][0]
        colors = {}
        for c, name in enumerate(columns):
            if name not in ("Entrada", "Salida", "Diferencia"):
                continue
            for r, raw in enumerate(raw_rows):
                try:
                    number = float(raw[c])
                except (TypeError, ValueError):
                    continue
                if number == number and number != 0:
                    colors[(r, c)] = red if name == "Salida" or (name == "Diferencia" and number < 0) else green
        pdf.table(columns, rows, weights, ["R" if n else "L" for n in numeric], row_h=6.2, size=7.6, colors=colors)
    return bytes(pdf.output())


def order_pdf(order: dict, items: pd.DataFrame, supplier: dict | None = None, company: dict | None = None) -> bytes:
    """Orden de compra lista para imprimir o mandar al proveedor: portada con estado, tarjetas del proveedor y de «facturar a»
    (razón social y RUC de la empresa), entrega y pago, tabla de materiales (con lo recibido), importes como en una factura
    (valor de venta, IGV 18 % e importe total), notas y firmas. Es el valor exacto del trato: la compra y el pago se hacen fuera del
    sistema y la condición de pago es informativa."""
    supplier, company = supplier or {}, company or {}
    status_text, status_tone = ORDER_STATUS.get(order.get("status"), (str(order.get("status") or ""), "gray"))
    currency = order.get("currency") or money.BASE
    tax_rate = float(order.get("tax_rate") or 0)
    include = bool(order.get("prices_include_tax")) and tax_rate > 0
    pdf = BrandPDF("Orden de compra", order["code"], theme="violet", style="band")
    pdf.add_page()
    meta = [("Fecha de emisión", _date(order["created_at"]))]
    if _date(order.get("expected_date")):
        meta.append(("Entrega prometida", _date(order["expected_date"])))
    meta.append(("Moneda", money.CURRENCY_NAMES.get(currency, currency)))
    pdf.cover("Orden de compra", order["code"], meta, (status_text, status_tone), icon="order")

    # proveedor y comprador (a quién facturar), lado a lado
    gap, half = 4.0, (pdf.usable - 4.0) / 2
    y0 = pdf.get_y()
    h1 = pdf.info_card(
        [("Razón social", order["supplier_name"], "building"), ("RUC", supplier.get("ruc"), "list"), ("Contacto", supplier.get("contact_name"), "user"),
         ("Teléfono", supplier.get("phone"), "phone"), ("Correo", supplier.get("email"), "mail")],
        columns=1, title="Proveedor", w=half,
    )
    pdf.logo(supplier.get("logo"), pdf.l_margin + half - 19, y0 + 4, 14)     # el logotipo del proveedor, arriba a la derecha de su tarjeta
    pdf.set_y(y0)
    buyer = company.get("trade_name") or company.get("legal_name")
    h2 = pdf.info_card(
        [("Razón social", company.get("legal_name"), "building"), ("Nombre comercial", company.get("trade_name") if company.get("legal_name") != company.get("trade_name") else None, "layers"),
         ("RUC", company.get("ruc"), "list"), ("Dirección fiscal", company.get("fiscal_address"), "pin")]
        or [("Facturar a", buyer, "building")],
        columns=1, title="Facturar a", x=pdf.l_margin + half + gap, w=half,
    ) if buyer else 0.0
    pdf.set_y(y0 + max(h1, h2) + 5)

    due = money.due_date(order["created_at"], order.get("payment_terms"))
    pdf.info_card(
        [("Obra destino", order.get("site_name") or "Sin obra destino", "pin"), ("Entrega prometida", _date(order.get("expected_date")), "calendar"),
         ("Condición de pago", order.get("payment_terms"), "coin"), ("Pago pactado hasta el", f"{due:%d/%m/%Y}" if due else None, "clock"),
         ("Enviada el", _date(order.get("sent_at"), True), "truck"), ("Tratamiento del IGV", money.TAX_MODES[money.tax_mode(tax_rate, include)][0].replace(" (18 %)", ""), "scale")],
        columns=3, title="Entrega y pago",
    )

    ordered_value = sum(float(r["quantity"]) * float(r["unit_price"]) for r in items.to_dict("records"))
    received_value = sum(min(float(r.get("received_qty") or 0), float(r["quantity"])) * float(r["unit_price"]) for r in items.to_dict("records"))
    share = received_value / ordered_value if ordered_value else 0.0
    status = order.get("status")
    pdf.timeline(
        [
            ("Emitida", _date(order["created_at"]), "done"),
            ("Enviada", _date(order.get("sent_at")) or "Pendiente", "done" if _date(order.get("sent_at")) else ("current" if status == "pendiente" else "todo")),
            ("Recepción", "Completa" if status == "recibida" else f"Parcial · {share:.0%}" if status == "parcial" else (f"Prometida {_date(order.get('expected_date'))}" if _date(order.get("expected_date")) else "Por recibir"),
             "done" if status == "recibida" else "current" if status in ("enviada", "parcial") else "todo"),
            ("Pago pactado", f"hasta el {due:%d/%m/%Y}" if due else (order.get("payment_terms") or "Informativo"), "todo"),
        ],
        title="Seguimiento del pedido",
    )
    if status == "cancelada":
        pdf.watermark("Cancelada", "bad")

    pdf.section("Materiales del pedido", "box", len(items))
    rows, tones, subtotal = [], {}, 0.0
    for index, row in enumerate(items.to_dict("records")):
        qty, price = float(row["quantity"]), float(row["unit_price"])
        received = float(row.get("received_qty") or 0)
        line_total = qty * price
        subtotal += line_total
        if received >= qty - 1e-9 and qty > 0:
            tones[index] = {4: "good"}
        elif received > 0:
            tones[index] = {4: "warn"}
        rows.append([str(index + 1), row["material_name"], row.get("unit") or "", f"{qty:,.2f}", f"{received:,.2f}" if received else "—", f"{price:,.2f}", f"{line_total:,.2f}"])
    price_label = "Precio c/IGV" if include else "Precio unit."
    pdf.table(["N.º", "Material", "Unidad", "Cantidad", "Recibido", price_label, "Subtotal"], rows, [0.7, 5.0, 1.3, 1.5, 1.5, 2.0, 1.9], ["L", "L", "L", "R", "R", "R", "R"], tones=tones)

    amounts = money.amounts(subtotal, tax_rate, order.get("exchange_rate") or 1, include)
    sym = money.symbol(currency)
    detail = [("Valor de venta", f"{sym} {amounts['net']:,.2f}")]
    if tax_rate:
        detail.append((f"IGV ({tax_rate:.0%})", f"{sym} {amounts['tax']:,.2f}"))
    else:
        detail.append(("IGV", "Exonerado / inafecto"))
    stamp_y = pdf.get_y()
    pdf.totals(detail, ("Importe total", f"{sym} {amounts['total']:,.2f}"))
    free = pdf.usable - 78      # el sello va centrado en el hueco que deja el cuadro de totales
    pdf.stamp(status_text, tone=status_tone if status_tone != "gray" else "accent", center=(pdf.l_margin + free / 2 - 2, stamp_y + 13),
              size=11.5, sub=f"{order['code']} · {_date(order['created_at'])}", icon="x" if status == "cancelada" else "check")
    if currency != money.BASE and float(order.get("exchange_rate") or 0) > 0:
        pdf.font(8, color=MUTED_TEXT)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 5, f"Equivale a {money.symbol(money.BASE)} {amounts['total_base']:,.2f} al tipo de cambio {float(order['exchange_rate']):g}.", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    pdf.note_box("Notas del pedido", order.get("notes"))
    pdf.signatures([("Autoriza", company.get("legal_name")), ("Recibe proveedor", order["supplier_name"])])
    return bytes(pdf.output())


def order_whatsapp_text(order: dict, items: pd.DataFrame, company: dict | None = None) -> str:
    """Texto del pedido para WhatsApp o correo: líneas, valor de venta, IGV e importe total, entrega, condición de pago y a quién facturar."""
    company = company or {}
    lines = [f"Hola {order['supplier_name']}, quisiera hacer el siguiente pedido ({order['code']}):", ""]
    subtotal = 0.0
    for row in items.to_dict("records"):
        line_total = float(row["quantity"]) * float(row["unit_price"])
        subtotal += line_total
        unit = f" {row['unit']}" if row.get("unit") else ""
        lines.append(f"- {row['material_name']}: {float(row['quantity']):g}{unit} x {float(row['unit_price']):,.2f} = {line_total:,.2f}")
    tax_rate = float(order.get("tax_rate") or 0)
    cur = order.get("currency") or money.BASE
    amounts = money.amounts(subtotal, tax_rate, order.get("exchange_rate") or 1, bool(order.get("prices_include_tax")))
    lines.append("")
    if tax_rate:
        lines += [f"Valor de venta: {money.fmt(amounts['net'], cur)}", f"IGV ({tax_rate:.0%}): {money.fmt(amounts['tax'], cur)}"]
        if order.get("prices_include_tax"):
            lines.append("(Los precios indicados ya incluyen IGV.)")
    lines.append(f"Importe total: {money.fmt(amounts['total'], cur)}")
    expected = str(order.get("expected_date") or "")
    if expected and expected not in ("None", "nan", "NaT"):
        lines.append(f"Fecha de entrega solicitada: {expected[8:10]}/{expected[5:7]}/{expected[:4]}")
    if order.get("payment_terms"):
        lines.append(f"Condición de pago: {order['payment_terms']}")
    if order.get("site_name"):
        lines.append(f"Entrega en: {order['site_name']}")
    if order.get("notes"):
        lines.append(f"Notas: {order['notes']}")
    if company.get("legal_name") and company.get("ruc"):
        lines.append(f"Facturar a: {company['legal_name']} · RUC {company['ruc']}")
    lines.append("¿Me confirman disponibilidad y fecha de entrega? Gracias.")
    return "\n".join(lines)


def dispatch_pdf(voucher: dict, lines: pd.DataFrame) -> bytes:
    """Vale de salida (despacho de almacén a obra): portada, datos del despacho, materiales entregados y tres firmas."""
    pdf = BrandPDF("Vale de salida", voucher["code"], theme="teal", style="ticket")
    pdf.add_page()
    stage = voucher.get("stage")
    pdf.cover(
        "Vale de salida de almacén", voucher["code"],
        [("Fecha y hora", _date(voucher["created_at"], True)), ("Obra", str(voucher.get("site_name") or ""))],
        (f"Etapa: {stage}", "info") if stage else None, icon="truck",
    )
    pdf.info_card(
        [("Obra destino", voucher.get("site_name"), "building"), ("Etapa de la obra", stage, "layers"),
         ("Solicitado por", voucher.get("requested_by"), "user"), ("Registrado por", voucher.get("actor"), "sign"),
         ("Fecha y hora", _date(voucher["created_at"], True), "calendar"), ("Materiales", f"{len(lines)} línea(s)", "box")],
        columns=2, title="Datos del despacho",
    )
    pdf.section("Materiales entregados", "box", len(lines))
    rows = [[str(i + 1), r["material_name"], r.get("unit") or "", f"{float(r['quantity']):,.2f}", ""] for i, r in enumerate(lines.to_dict("records"))]
    pdf.table(["N.º", "Material", "Unidad", "Cantidad", "Verif."], rows, [0.8, 6.4, 1.5, 1.7, 1.0], ["L", "L", "L", "R", "L"], row_h=7.6, size=8.6)
    pdf.font(7, color=MUTED_TEXT)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 4, "Quien recibe marca cada casilla al verificar el material.", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.note_box("Nota del vale", voucher.get("note"), icon="note", tone="info")
    pdf.signatures(
        [("Entrega (almacén)", voucher.get("actor")), ("Recibe", voucher.get("requested_by")), ("V.° B.° de obra", None)],
        seal={"text": "Entregado", "tone": "teal", "r": 15, "sub": _date(voucher["created_at"])},
    )
    pdf.font(7.2, color=MUTED_TEXT)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 4, "Con su firma, quien recibe confirma haber verificado la cantidad y el estado del material.", align="C")
    return bytes(pdf.output())


def dispatch_text(voucher: dict, lines: pd.DataFrame) -> str:
    """Texto del vale de salida para el cuerpo de un correo o mensaje."""
    out = [f"Vale de salida {voucher['code']} · {clock.local(voucher['created_at'], False)}", f"Obra: {voucher.get('site_name')}"]
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
    pdf = BrandPDF("Reporte de obra", site["name"], orientation="L", theme="amber", style="stripe")
    pdf.add_page()
    pdf.cover(
        "Reporte de obra", site["name"],
        [("Dirección", str(site.get("address") or "Sin dirección registrada")), ("Generado", f"{clock.now():%d/%m/%Y %H:%M}")],
        (f"{workers} trabajador(es)", "gray"), icon="building",
    )
    planned, ordered = float(prog.get("planned") or 0), float(prog.get("ordered") or 0)
    received = float(materials["Recibido $"].sum()) if not materials.empty else 0.0
    dispatched = float(materials["Despachado $"].sum()) if not materials.empty else 0.0
    consumed = prog.get("pct_consumed")
    over = int(((materials["Pedido"] > materials["Presupuesto"] + 1e-9) & (materials["Presupuesto"] > 0)).sum()) if not materials.empty else 0
    pdf.font(8, color=MUTED_TEXT)
    pdf.cell(0, 5, "Importes en soles y sin IGV. «Pedido» es el valor de las órdenes: la compra y el pago se hacen fuera del sistema. Lo despachado se valora al precio presupuestado (o al promedio pedido).", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.kpis(
        [
            {"label": "Presupuesto", "value": f"S/ {planned:,.0f}", "sub": "costo previsto", "icon": "coin"},
            {"label": "Pedido", "value": f"S/ {ordered:,.0f}", "sub": f"{ordered / planned * 100:.0f} % del presupuesto" if planned else "sin presupuesto", "icon": "order", "tone": "warn" if planned and ordered > planned else "info"},
            {"label": "Recibido", "value": f"S/ {received:,.0f}", "sub": "en almacén", "icon": "box", "tone": "teal"},
            {"label": "Despachado", "value": f"S/ {dispatched:,.0f}", "sub": "valorizado", "icon": "truck", "tone": "good"},
            {"label": "Saldo", "value": f"S/ {planned - ordered:,.0f}", "sub": "presupuesto − pedido", "icon": "scale", "tone": "warn" if planned - ordered < 0 else "accent"},
            {"label": "Avance", "value": f"{consumed * 100:.0f} %" if consumed is not None else "—", "sub": f"{over} sobre lo presupuestado" if over else "dentro de lo previsto", "icon": "chart", "fraction": consumed or 0, "tone": "warn" if over else "accent"},
        ]
    )

    top = pdf.get_y()
    card_h = 44.0
    if top + card_h > pdf.h - 20:
        pdf.add_page()
        top = pdf.get_y()
    pdf.box(pdf.l_margin, top, pdf.usable, card_h, fill=PAPER_COLOR)
    pdf.font(8, semi=True, color=pdf.accent_dark)
    pdf.set_xy(pdf.l_margin + 5, top + 3.4)
    pdf.cell(100, 4, "COMPARACIÓN DE IMPORTES (S/, SIN IGV)")
    pdf.hbars(
        pdf.l_margin + 5, top + 10, pdf.usable * 0.64,
        [("Presupuesto", planned, "accent", f"S/ {planned:,.0f}"), ("Pedido", ordered, "warn" if planned and ordered > planned else "info", f"S/ {ordered:,.0f}"),
         ("Recibido", received, "teal", f"S/ {received:,.0f}"), ("Despachado", dispatched, "good", f"S/ {dispatched:,.0f}")],
        row_h=8.4, label_w=30,
    )
    ring_x = pdf.l_margin + pdf.usable * 0.64 + (pdf.usable * 0.36) / 2 + 4
    share_dispatched = dispatched / planned if planned else None
    pdf.donut(ring_x, top + card_h / 2 + 1, 15, share_dispatched, tone="good" if share_dispatched is not None and share_dispatched <= 1 else "warn",
              label=f"{share_dispatched * 100:.0f} %" if share_dispatched is not None else "—", sub="despachado")
    pdf.font(7.2, color=MUTED_TEXT)
    pdf.set_xy(ring_x - 30, top + card_h - 6)
    pdf.cell(60, 3, "del presupuesto de la obra", align="C")
    pdf.set_y(top + card_h + 5)

    pdf.section("Materiales", "box", len(materials))
    if materials.empty:
        pdf.font(9, color=MUTED_TEXT)
        pdf.cell(0, 7, "Sin materiales presupuestados ni movimientos.", new_x="LMARGIN", new_y="NEXT")
    else:
        rows, tones = [], {}
        for index, m in enumerate(materials.to_dict("records")):
            if not m["Presupuesto"]:
                state, tone = "Fuera de presupuesto", "warn"
            elif m["Pedido"] > m["Presupuesto"] + 1e-9:
                state, tone = "Sobre lo presupuestado", "warn"
            elif m["Despachado"] >= m["Presupuesto"] - 1e-9:
                state, tone = "Completo", "good"
            elif m["Pedido"] == 0:
                state, tone = "Sin pedir", "gray"
            else:
                state, tone = f"{m['Pedido'] / m['Presupuesto'] * 100:.0f} % pedido", "info"
            tones[index] = {9: tone}
            rows.append(
                [str(m["Material"]), str(m.get("Unidad") or ""), f"{m['Presupuesto']:,.2f}", f"{m['Pedido']:,.2f}", f"{m['Recibido']:,.2f}", f"{m['Despachado']:,.2f}",
                 f"{m['Presupuesto $']:,.2f}", f"{m['Pedido $']:,.2f}", f"{m['Despachado $']:,.2f}", state]
            )
        pdf.table(
            ["Material", "Unidad", "Presup.", "Pedido", "Recibido", "Despach.", "Presup. S/", "Pedido S/", "Despach. S/", "Estado"], rows,
            [4.2, 1.5, 1.3, 1.3, 1.3, 1.3, 1.6, 1.6, 1.6, 2.5], ["L", "L", "R", "R", "R", "R", "R", "R", "R", "L"], tones=tones, row_h=7.0,
        )

    if stages:
        pdf.section("Avance por etapa", "layers", len(stages))
        for st_ in stages:
            if pdf.get_y() > pdf.h - 34:
                pdf.add_page()
            fraction = min(st_["dispatched"] / st_["budget"], 1.0) if st_["budget"] else None
            y = pdf.get_y()
            pdf.box(pdf.l_margin, y, pdf.usable, 11.5, fill=PAPER_COLOR)
            pdf.font(9, semi=True)
            pdf.set_xy(pdf.l_margin + 4, y + 1.2)
            pdf.cell(70, 4.4, pdf.fit(st_["stage"] or "Sin etapa", 68))
            pdf.font(8, color=MUTED_TEXT)
            pdf.set_xy(pdf.l_margin + 4, y + 5.6)
            pdf.cell(110, 4, f"Presupuesto S/ {st_['budget']:,.2f}   ·   Despachado S/ {st_['dispatched']:,.2f}")
            pdf.progress(pdf.l_margin + 150, y + 4.6, pdf.usable - 190, fraction, h=2.6, tone="good" if fraction is not None and fraction < 1 else "accent")
            pdf.font(9, bold=True)
            pdf.set_xy(pdf.w - pdf.r_margin - 34, y + 3.2)
            pdf.cell(30, 5, f"{fraction * 100:.0f} %" if fraction is not None else "—", align="R")
            pdf.set_y(y + 13.5)
        pdf.ln(2)

    pdf.section("Vales de salida", "truck", len(vouchers))
    if vouchers.empty:
        pdf.font(9, color=MUTED_TEXT)
        pdf.cell(0, 7, "Aún no se despachó material a esta obra.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.table(
            ["Vale", "Fecha", "Etapa", "Solicitado por", "Materiales"],
            [[str(v["code"]), _date(v["created_at"], True), str(v.get("stage") or "—"), str(v.get("requested_by") or "—"), str(int(v["lines_count"]))] for v in vouchers.to_dict("records")],
            [1.4, 1.8, 2, 3, 1.1], ["L", "L", "L", "L", "R"],
        )
    return bytes(pdf.output())


