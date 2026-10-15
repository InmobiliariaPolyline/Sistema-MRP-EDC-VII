"""Estilo común de los PDF del sistema: fuente Inter, colores de la app, encabezado y pie, tarjetas, tablas,
indicadores, etiquetas de estado e iconos vectoriales (dibujados, no emojis).

Todos los documentos (orden de compra, vale de salida, reportes, reporte de obra, kardex) se arman con `BrandPDF`
para verse como una sola familia y respetar los mismos márgenes, colores y tipografía."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from core.version import APP_VERSION

FONTS = Path(__file__).resolve().parent / "fonts"

# Colores de la app (modules/styles/palette_light.css)
ACCENT = (107, 87, 245)
ACCENT_DARK = (90, 63, 240)
SOFT = (238, 234, 255)
TEXT = (20, 26, 51)
MUTED = (92, 102, 133)
BORDER = (226, 229, 241)
PAPER = (247, 248, 253)
WHITE = (255, 255, 255)
TONES = {
    "good": ((22, 121, 74), (230, 247, 238)),
    "bad": ((192, 52, 63), (253, 236, 238)),
    "warn": ((148, 96, 15), (255, 243, 218)),
    "info": ((36, 89, 168), (232, 241, 255)),
    "teal": ((14, 138, 138), (225, 246, 245)),
    "accent": (ACCENT, SOFT),
    "gray": (MUTED, (238, 240, 247)),
}

# Iconos de 24 × 24 con trazo (se pintan del color pedido). Formas simples: caben en un PDF y no dependen de ninguna fuente.
_ICONS = {
    "order": '<rect x="5" y="3" width="14" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/>',
    "truck": '<rect x="2" y="6" width="12" height="10" rx="1"/><path d="M14 9 L19 9 L22 12 L22 16 L14 16 Z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    "box": '<path d="M12 3 L21 7.5 L21 16.5 L12 21 L3 16.5 L3 7.5 Z"/><polyline points="3,7.5 12,12 21,7.5"/><line x1="12" y1="12" x2="12" y2="21"/>',
    "building": '<rect x="5" y="3" width="14" height="18" rx="1"/><line x1="9" y1="7" x2="10" y2="7"/><line x1="14" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="10" y2="11"/><line x1="14" y1="11" x2="15" y2="11"/><rect x="10" y="15" width="4" height="6"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21 C4 16 8 14 12 14 C16 14 20 16 20 21"/>',
    "phone": '<rect x="7" y="2" width="10" height="20" rx="2"/><line x1="11" y1="18" x2="13" y2="18"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><polyline points="3,7 12,13 21,7"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>',
    "coin": '<circle cx="12" cy="12" r="9"/><path d="M15 9 C14 8 13 7.5 12 7.5 C10.5 7.5 9.5 8.3 9.5 9.5 C9.5 12 14.5 11 14.5 14 C14.5 15.2 13.5 16.5 12 16.5 C10.8 16.5 9.8 16 9 15"/><line x1="12" y1="6" x2="12" y2="18"/>',
    "pin": '<path d="M12 21 L6 11 C4.5 8 6.5 4 12 4 C17.5 4 19.5 8 18 11 Z"/><circle cx="12" cy="10" r="2"/>',
    "check": '<circle cx="12" cy="12" r="9"/><polyline points="8,12.5 11,15.5 16,9"/>',
    "alert": '<path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="14"/><line x1="12" y1="17" x2="12" y2="17.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><polyline points="12,7 12,12 16,14"/>',
    "note": '<path d="M5 21 L5 5 C5 4 6 3 7 3 L17 3 C18 3 19 4 19 5 L19 15 L13 21 Z"/><polyline points="13,21 13,15 19,15"/>',
    "chart": '<line x1="4" y1="20" x2="20" y2="20"/><rect x="6" y="12" width="3" height="8"/><rect x="11" y="7" width="3" height="13"/><rect x="16" y="4" width="3" height="16"/>',
    "layers": '<polyline points="3,9 12,4 21,9 12,14 3,9"/><polyline points="3,13 12,18 21,13"/>',
    "list": '<line x1="9" y1="6" x2="20" y2="6"/><line x1="9" y1="12" x2="20" y2="12"/><line x1="9" y1="18" x2="20" y2="18"/><circle cx="5" cy="6" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="5" cy="18" r="1"/>',
    "sign": '<path d="M4 20 C8 20 8 12 11 12 C13 12 12 17 14 17 C16 17 17 14 20 14"/><line x1="4" y1="22" x2="20" y2="22"/>',
    "undo": '<polyline points="9,5 4,10 9,15"/><path d="M4 10 L15 10 C18 10 20 12 20 15 C20 18 18 20 15 20 L11 20"/>',
    "scale": '<line x1="12" y1="4" x2="12" y2="20"/><line x1="7" y1="20" x2="17" y2="20"/><path d="M4 8 L20 8"/><path d="M4 8 L2 14 L7 14 Z"/><path d="M20 8 L17 14 L22 14 Z"/>',
}


def _rgb(color: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % color


def _safe(text) -> str:
    """Texto para el PDF: sin None/NaN y con los espacios raros normalizados (la fuente Inter cubre el resto)."""
    if text is None or (isinstance(text, float) and text != text):
        return ""
    return str(text).replace(" ", " ").replace("\t", " ").replace("\r", "").strip()


class BrandPDF(FPDF):
    """PDF con la identidad del sistema. `kind`: tipo de documento ('Orden de compra'…), mostrado en el encabezado de las
    páginas siguientes junto a `code`."""

    def __init__(self, kind: str, code: str = "", orientation: str = "P", margin: float = 14.0):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.kind, self.code = kind, code
        self.set_margins(margin, margin + 8, margin)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()
        self.set_title(f"{kind} {code}".strip())
        self.set_creator("Sistema MRP")
        self.add_font("Inter", "", str(FONTS / "Inter_Regular.ttf"))
        self.add_font("Inter", "B", str(FONTS / "Inter_Bold.ttf"))
        self.add_font("InterSB", "", str(FONTS / "Inter_SemiBold.ttf"))
        self._cover_done = False

    # --------------------------------------------------------------------------------------------- ancho útil
    @property
    def usable(self) -> float:
        return self.w - self.l_margin - self.r_margin

    # --------------------------------------------------------------------------------------------- texto
    def font(self, size: float = 9, bold: bool = False, semi: bool = False, color: tuple[int, int, int] = TEXT) -> None:
        if semi:
            self.set_font("InterSB", "", size)
        else:
            self.set_font("Inter", "B" if bold else "", size)
        self.set_text_color(*color)

    def fit(self, text, width: float) -> str:
        """Recorta el texto con «…» para que quepa en `width` mm con la fuente actual."""
        text = _safe(text)
        if self.get_string_width(text) <= width:
            return text
        while text and self.get_string_width(text + "…") > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def wrap(self, text, width: float, max_lines: int = 3) -> list[str]:
        """Parte un texto en líneas de hasta `width` mm (con «…» si no cabe en `max_lines`)."""
        words, lines, current = _safe(text).split(), [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if self.get_string_width(trial) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self.fit(lines[-1] + " …", width)
        return lines or [""]

    # --------------------------------------------------------------------------------------------- iconos y formas
    def icon(self, name: str, x: float, y: float, size: float = 5, color: tuple[int, int, int] = ACCENT, weight: float = 2.0) -> None:
        body = _ICONS[name]
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
            f'<g fill="none" stroke="{_rgb(color)}" stroke-width="{weight}" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>'
        )
        self.image(io.BytesIO(svg.encode("utf-8")), x=x, y=y, w=size, h=size)

    def chip(self, x: float, y: float, text: str, tone: str = "gray", size: float = 7.5, h: float = 5.4, align: str = "L") -> float:
        """Etiqueta redondeada de color. Devuelve su ancho. `align='R'` ancla `x` al borde derecho."""
        fg, bg = TONES[tone]
        self.font(size, semi=True, color=fg)
        width = self.get_string_width(_safe(text)) + 5
        left = x - width if align == "R" else x
        self.set_fill_color(*bg)
        self.rect(left, y, width, h, style="F", round_corners=True, corner_radius=h / 2)
        self.set_xy(left, y)
        self.cell(width, h, _safe(text), align="C")
        return width

    def box(self, x: float, y: float, w: float, h: float, fill: tuple[int, int, int] = WHITE, border: tuple[int, int, int] | None = BORDER, radius: float = 2.5) -> None:
        self.set_fill_color(*fill)
        if border:
            self.set_draw_color(*border)
            self.set_line_width(0.25)
            self.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=radius)
        else:
            self.rect(x, y, w, h, style="F", round_corners=True, corner_radius=radius)

    def progress(self, x: float, y: float, w: float, fraction: float | None, h: float = 2.2, tone: str = "accent") -> None:
        """Barra de avance (0 a 1)."""
        fg, _ = TONES[tone]
        self.set_fill_color(*BORDER)
        self.rect(x, y, w, h, style="F", round_corners=True, corner_radius=h / 2)
        if fraction and fraction > 0:
            self.set_fill_color(*fg)
            self.rect(x, y, max(min(fraction, 1.0) * w, h), h, style="F", round_corners=True, corner_radius=h / 2)

    # --------------------------------------------------------------------------------------------- portada y páginas
    def cover(self, label: str, title: str, meta: list[tuple[str, str]] | None = None, chip: tuple[str, str] | None = None, icon: str = "order") -> None:
        """Banda superior de la primera página: tipo de documento, título grande, datos a la derecha y, si se pide, una etiqueta de estado."""
        top, band = 0.0, 32.0
        self.set_fill_color(*ACCENT_DARK)
        self.rect(0, top, self.w, band, style="F")
        self.set_fill_color(*ACCENT)
        self.rect(self.w * 0.55, top, self.w * 0.45, band, style="F")
        self.set_fill_color(*ACCENT_DARK)
        self.rect(self.w * 0.55 - 8, top, 16, band, style="F")  # transición suave entre los dos tonos
        # marca
        self.set_fill_color(255, 255, 255)
        self.rect(self.l_margin, 8, 11, 11, style="F", round_corners=True, corner_radius=2.6)
        self.icon(icon, self.l_margin + 2.1, 10.1, 6.8, ACCENT_DARK, 2.2)
        self.font(7.5, semi=True, color=(214, 208, 255))
        self.set_xy(self.l_margin + 14, 8.2)
        self.cell(60, 4, _safe(label).upper())
        self.font(17, bold=True, color=WHITE)
        self.set_xy(self.l_margin + 14, 12.4)
        self.cell(110, 8, self.fit(title, 110))
        # datos a la derecha
        right = self.w - self.r_margin
        y = 6.4
        for key, value in (meta or [])[:3]:
            self.font(7, color=(214, 208, 255))
            self.set_xy(right - 62, y)
            self.cell(62, 3.4, _safe(key).upper(), align="R")
            self.font(9, semi=True, color=WHITE)
            self.set_xy(right - 62, y + 3.2)
            self.cell(62, 4.2, self.fit(value, 62), align="R")
            y += 7.8
        if chip:
            self.chip(self.l_margin + 14, 22.4, chip[0], chip[1])
        self.set_y(band + 7)
        self._cover_done = True

    def header(self) -> None:
        if not self._cover_done:
            return  # la primera página lleva portada
        self.set_fill_color(*ACCENT)
        self.rect(0, 0, self.w, 1.6, style="F")
        self.set_fill_color(*SOFT)
        self.rect(self.l_margin, 6, 5.5, 5.5, style="F", round_corners=True, corner_radius=1.4)
        self.icon("order", self.l_margin + 1.0, 7.0, 3.5, ACCENT, 2.4)
        self.font(8, semi=True, color=ACCENT_DARK)
        self.set_xy(self.l_margin + 8, 6.2)
        self.cell(80, 5, _safe(f"{self.kind}  {self.code}").strip())
        self.font(7.5, color=MUTED)
        self.set_xy(self.w - self.r_margin - 60, 6.2)
        self.cell(60, 5, "Sistema MRP", align="R")
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, 13, self.w - self.r_margin, 13)
        self.set_y(18)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.font(7, color=MUTED)
        self.set_xy(self.l_margin, self.get_y() + 1.6)
        self.cell(self.usable * 0.7, 4, f"Generado el {datetime.now():%d/%m/%Y a las %H:%M}  ·  Sistema MRP  ·  {APP_VERSION}")
        self.cell(self.usable * 0.3, 4, f"Página {self.page_no()} de {{nb}}", align="R")

    # --------------------------------------------------------------------------------------------- bloques
    def section(self, text: str, icon: str | None = None, count: int | str | None = None) -> None:
        """Título de sección con icono y, si se pide, un contador."""
        if self.get_y() > self.h - 40:
            self.add_page()
        y = self.get_y()
        x = self.l_margin
        if icon:
            self.icon(icon, x, y + 0.3, 5, ACCENT, 2.0)
            x += 7
        self.font(11, bold=True)
        self.set_xy(x, y)
        self.cell(0, 5.6, _safe(text))
        if count is not None:
            width = self.get_string_width(_safe(text)) + 2
            self.chip(x + width + 1, y + 0.1, str(count), "accent", size=7)
        self.set_y(y + 8)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)

    def info_card(self, items: list[tuple[str, str, str | None]], columns: int = 2, title: str | None = None, x: float | None = None, w: float | None = None) -> float:
        """Tarjeta con pares etiqueta/valor distribuidos en columnas (cada ítem: etiqueta, valor, icono opcional).
        Devuelve la altura usada y deja el cursor debajo de la tarjeta."""
        items = [(k, v, i) for k, v, i in items if _safe(v)]
        if not items:
            return 0.0
        x0 = self.l_margin if x is None else x
        width = self.usable if w is None else w
        pad, row_h = 4.0, 10.5
        rows = -(-len(items) // columns)
        title_h = 7.5 if title else 0.0
        height = pad * 2 + rows * row_h + title_h - 1.5
        y0 = self.get_y()
        if y0 + height > self.h - 20:
            self.add_page()
            y0 = self.get_y()
        self.box(x0, y0, width, height, fill=WHITE)
        self.set_fill_color(*ACCENT)
        self.rect(x0, y0 + 3.5, 0.9, height - 7, style="F")
        cy = y0 + pad
        if title:
            self.font(8, semi=True, color=ACCENT_DARK)
            self.set_xy(x0 + pad + 1, cy - 0.5)
            self.cell(width - pad * 2, 4, _safe(title).upper())
            cy += title_h
        col_w = (width - pad * 2) / columns
        for index, (key, value, icon) in enumerate(items):
            col, row = index % columns, index // columns
            cx, ry = x0 + pad + 1 + col * col_w, cy + row * row_h
            text_x = cx
            if icon:
                self.icon(icon, cx, ry + 0.9, 4.2, MUTED, 2.0)
                text_x += 6
            self.font(6.8, semi=True, color=MUTED)
            self.set_xy(text_x, ry)
            self.cell(col_w - 7, 3.4, _safe(key).upper())
            self.font(9, semi=True)
            self.set_xy(text_x, ry + 3.6)
            self.cell(col_w - 7, 4.6, self.fit(value, col_w - 8))
        self.set_y(y0 + height + 4)
        return height

    def kpis(self, cards: list[dict], per_row: int | None = None, h: float = 21.0) -> None:
        """Tarjetas de cifras. Cada una: {label, value, sub?, tone?, icon?, fraction?}."""
        per_row = per_row or len(cards)
        gap = 3.0
        w = (self.usable - gap * (per_row - 1)) / per_row
        y = self.get_y()
        if y + h > self.h - 20:
            self.add_page()
            y = self.get_y()
        for i, card in enumerate(cards):
            col, row = i % per_row, i // per_row
            x, yy = self.l_margin + col * (w + gap), y + row * (h + gap)
            fg, bg = TONES[card.get("tone", "accent")]
            self.box(x, yy, w, h, fill=WHITE)
            self.set_fill_color(*fg)
            self.rect(x, yy + 3, 1.0, h - 6, style="F")
            if card.get("icon"):
                self.set_fill_color(*bg)
                self.rect(x + w - 10, yy + 3.2, 7, 7, style="F", round_corners=True, corner_radius=2)
                self.icon(card["icon"], x + w - 9, yy + 4.2, 5, fg, 2.1)
            self.font(6.8, semi=True, color=MUTED)
            self.set_xy(x + 4, yy + 3)
            self.cell(w - 14, 3.4, self.fit(_safe(card["label"]).upper(), w - 14))
            self.font(13.5, bold=True, color=fg if card.get("tone") not in (None, "accent") else TEXT)
            self.set_xy(x + 4, yy + 7.6)
            self.cell(w - 6, 6.4, self.fit(card["value"], w - 6))
            if card.get("fraction") is not None:
                self.progress(x + 4, yy + h - 5.6, w - 8, card["fraction"], tone=card.get("tone", "accent"))
            if card.get("sub"):
                self.font(6.8, color=MUTED)
                self.set_xy(x + 4, yy + h - 4.6 if card.get("fraction") is None else yy + h - 3.2)
                self.cell(w - 6, 3, self.fit(card["sub"], w - 6))
        rows = -(-len(cards) // per_row)
        self.set_y(y + rows * (h + gap) + 1)

    def table(
        self, columns: list[str], rows: list[list], widths: list[float], align: list[str] | None = None, row_h: float = 6.6,
        tones: dict[int, dict[int, str]] | None = None, bold_last_row: bool = False, size: float = 8,
    ) -> None:
        """Tabla con encabezado de color, filas alternadas y texto recortado con «…». `widths` son pesos relativos;
        `align` por columna ('L' o 'R'); `tones[fila][columna]` pinta esa celda como etiqueta ('good', 'bad', 'warn'…)."""
        total = sum(widths)
        cols = [w / total * self.usable for w in widths]
        align = align or ["L"] * len(columns)

        def head() -> None:
            y = self.get_y()
            self.set_fill_color(*ACCENT_DARK)
            self.rect(self.l_margin, y, self.usable, 7.4, style="F", round_corners=True, corner_radius=1.6)
            self.font(7.4, semi=True, color=WHITE)
            x = self.l_margin
            for name, w, a in zip(columns, cols, align):
                self.set_xy(x + 1.8, y)
                self.cell(w - 3.6, 7.4, self.fit(_safe(name).upper(), w - 3.6), align=a)
                x += w
            self.set_y(y + 8.2)

        head()
        for r, row in enumerate(rows):
            if self.get_y() + row_h > self.h - 18:
                self.add_page()
                head()
            y = self.get_y()
            last = bold_last_row and r == len(rows) - 1
            if last:
                self.set_fill_color(*SOFT)
                self.rect(self.l_margin, y, self.usable, row_h, style="F", round_corners=True, corner_radius=1.2)
            elif r % 2 == 1:
                self.set_fill_color(*PAPER)
                self.rect(self.l_margin, y, self.usable, row_h, style="F")
            x = self.l_margin
            for c, (value, w, a) in enumerate(zip(row, cols, align)):
                tone = (tones or {}).get(r, {}).get(c)
                if tone and _safe(value):
                    self.chip(x + 1.4 if a == "L" else x + w - 1.4, y + (row_h - 5) / 2, self.fit(value, w - 3), tone, size=6.8, h=5, align=a if a == "R" else "L")
                else:
                    self.font(size, bold=last, color=TEXT)
                    self.set_xy(x + 1.8, y)
                    self.cell(w - 3.6, row_h, self.fit(value, w - 3.6), align=a)
                x += w
            self.set_y(y + row_h)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y() + 0.6, self.l_margin + self.usable, self.get_y() + 0.6)
        self.set_y(self.get_y() + 4)

    def totals(self, lines: list[tuple[str, str]], total: tuple[str, str], width: float = 78) -> None:
        """Cuadro de totales alineado a la derecha: líneas de detalle y un total destacado."""
        h = len(lines) * 6.6 + 12
        if self.get_y() + h > self.h - 20:
            self.add_page()
        x, y = self.w - self.r_margin - width, self.get_y()
        self.box(x, y, width, h, fill=WHITE)
        cy = y + 3
        for key, value in lines:
            self.font(8.5, color=MUTED)
            self.set_xy(x + 4, cy)
            self.cell(width / 2, 6, _safe(key))
            self.font(8.5, semi=True)
            self.cell(width / 2 - 8, 6, _safe(value), align="R")
            cy += 6.6
        self.set_fill_color(*ACCENT_DARK)
        self.rect(x, cy + 0.6, width, 9, style="F", round_corners=True, corner_radius=2.2)
        self.font(8.5, semi=True, color=(214, 208, 255))
        self.set_xy(x + 4, cy + 0.6)
        self.cell(width / 2, 9, _safe(total[0]).upper())
        self.font(11.5, bold=True, color=WHITE)
        self.cell(width / 2 - 8, 9, _safe(total[1]), align="R")
        self.set_y(y + h + 5)

    def note_box(self, title: str, text: str, icon: str = "note", tone: str = "warn") -> None:
        """Recuadro de color con un texto (notas, observaciones)."""
        text = _safe(text)
        if not text:
            return
        fg, bg = TONES[tone]
        self.font(8.5)
        lines = self.wrap(text, self.usable - 18, max_lines=6)
        h = 9 + len(lines) * 4.4
        if self.get_y() + h > self.h - 20:
            self.add_page()
        y = self.get_y()
        self.box(self.l_margin, y, self.usable, h, fill=bg, border=None)
        self.icon(icon, self.l_margin + 4, y + 3.2, 5, fg, 2.0)
        self.font(7.4, semi=True, color=fg)
        self.set_xy(self.l_margin + 12, y + 2.6)
        self.cell(0, 3.6, _safe(title).upper())
        self.font(8.5, color=TEXT)
        for i, line in enumerate(lines):
            self.set_xy(self.l_margin + 12, y + 7 + i * 4.4)
            self.cell(self.usable - 16, 4.4, line)
        self.set_y(y + h + 4)

    def signatures(self, labels: list[tuple[str, str | None]]) -> None:
        """Líneas de firma: cada una con su rol y, opcionalmente, el nombre de quien firma."""
        if self.get_y() + 33 > self.h - 18:   # el bloque (7 de aire + 26 de firmas) tiene que caber entero
            self.add_page()
        self.ln(7)
        y = self.get_y()
        n = len(labels)
        gap = 10.0
        w = (self.usable - gap * (n - 1)) / n
        for i, (role, name) in enumerate(labels):
            x = self.l_margin + i * (w + gap)
            self.set_draw_color(*MUTED)
            self.set_line_width(0.3)
            self.line(x, y + 14, x + w, y + 14)
            self.font(8, semi=True)
            self.set_xy(x, y + 15.2)
            self.cell(w, 4, _safe(role), align="C")
            if name:
                self.font(7.5, color=MUTED)
                self.set_xy(x, y + 19.4)
                self.cell(w, 4, self.fit(name, w), align="C")
        self.set_y(y + 26)
