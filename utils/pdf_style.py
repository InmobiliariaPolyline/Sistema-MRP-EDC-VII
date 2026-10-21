"""Estilo común de los PDF del sistema: fuente Inter, colores de la app, encabezado y pie, tarjetas, tablas,
indicadores, etiquetas de estado e iconos vectoriales (dibujados, no emojis).

Todos los documentos (orden de compra, vale de salida, reportes, reporte de obra, kardex) se arman con `BrandPDF`
para verse como una sola familia y respetar los mismos márgenes, colores y tipografía."""
from __future__ import annotations

import io
import math

from pathlib import Path

from fpdf import FPDF

from core.version import APP_VERSION
from utils.icons import ICONS as _ICONS
from utils import clock

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

# Un tema por familia de documento: acento, tono oscuro, tono suave y estilo de portada.
THEMES = {
    "violet": {"accent": ACCENT, "dark": ACCENT_DARK, "soft": SOFT},              # orden de compra
    "teal": {"accent": (14, 150, 150), "dark": (10, 106, 112), "soft": (222, 245, 244)},      # vale de salida
    "blue": {"accent": (47, 111, 222), "dark": (24, 62, 148), "soft": (228, 238, 255)},       # reportes del sistema
    "amber": {"accent": (224, 140, 20), "dark": (150, 82, 8), "soft": (255, 240, 214)},       # reporte de obra
    "green": {"accent": (30, 150, 96), "dark": (16, 96, 62), "soft": (225, 245, 235)},        # kardex
    "slate": {"accent": (70, 84, 120), "dark": (30, 38, 66), "soft": (233, 236, 245)},        # documentos sobrios
}

# Código 39: cada carácter son 9 elementos (barra, espacio, barra…), «1» = ancho y «0» = angosto. Lo leen todos los lectores.
_CODE39 = {
    "0": "000110100", "1": "100100001", "2": "001100001", "3": "101100000", "4": "000110001", "5": "100110000", "6": "001110000", "7": "000100101",
    "8": "100100100", "9": "001100100", "A": "100001001", "B": "001001001", "C": "101001000", "D": "000011001", "E": "100011000", "F": "001011000",
    "G": "000001101", "H": "100001100", "I": "001001100", "J": "000011100", "K": "100000011", "L": "001000011", "M": "101000010", "N": "000010011",
    "O": "100010010", "P": "001010010", "Q": "000000111", "R": "100000110", "S": "001000110", "T": "000010110", "U": "110000001", "V": "011000001",
    "W": "111000000", "X": "010010001", "Y": "110010000", "Z": "011010000", "-": "010000101", ".": "110000100", " ": "011000100", "*": "010010100",
    "$": "010101000", "/": "010100010", "+": "010001010", "%": "000101010",
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

    def __init__(self, kind: str, code: str = "", orientation: str = "P", margin: float = 14.0, theme: str = "violet", style: str = "band"):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.kind, self.code = kind, code
        palette = THEMES[theme]
        self.accent, self.accent_dark, self.soft = palette["accent"], palette["dark"], palette["soft"]
        self.style = style            # portada: band (franja), ticket (vale), poster (reporte), stripe (obra), minimal (ledger)
        self.set_margins(margin, margin + 8, margin)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()
        self.set_title(f"{kind} {code}".strip())
        self.set_creator("Sistema MRP")
        self.add_font("Inter", "", str(FONTS / "Inter_Regular.ttf"))
        self.add_font("Inter", "B", str(FONTS / "Inter_Bold.ttf"))
        self.add_font("InterSB", "", str(FONTS / "Inter_SemiBold.ttf"))
        self._cover_done = False

    def tone(self, name: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """Colores (texto, fondo) de un tono; «accent» sigue al tema del documento."""
        return (self.accent, self.soft) if name == "accent" else TONES[name]

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
    def icon(self, name: str, x: float, y: float, size: float = 5, color: tuple[int, int, int] | None = None, weight: float = 2.0) -> None:
        body = _ICONS[name]
        color = color or self.accent
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
            f'<g fill="none" stroke="{_rgb(color)}" stroke-width="{weight}" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>'
        )
        self.image(io.BytesIO(svg.encode("utf-8")), x=x, y=y, w=size, h=size)

    def chip(self, x: float, y: float, text: str, tone: str = "gray", size: float = 7.5, h: float = 5.4, align: str = "L") -> float:
        """Etiqueta redondeada de color. Devuelve su ancho. `align='R'` ancla `x` al borde derecho."""
        fg, bg = self.tone(tone)
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
        fg, _ = self.tone(tone)
        self.set_fill_color(*BORDER)
        self.rect(x, y, w, h, style="F", round_corners=True, corner_radius=h / 2)
        if fraction and fraction > 0:
            self.set_fill_color(*fg)
            self.rect(x, y, max(min(fraction, 1.0) * w, h), h, style="F", round_corners=True, corner_radius=h / 2)

    # --------------------------------------------------------------------------------------------- formas decorativas
    def _alpha(self, value: float):
        return self.local_context(fill_opacity=value, stroke_opacity=value)

    def barcode(self, x: float, y: float, text: str, h: float = 9.0, narrow: float = 0.32, color: tuple[int, int, int] = TEXT, draw: bool = True) -> float:
        """Código de barras Code 39 del texto (letras, números y - . espacio). Devuelve su ancho. Lo lee cualquier lector.
        Con `draw=False` solo mide."""
        wide = narrow * 2.6
        if draw:
            self.set_fill_color(*color)
        cursor = x
        for ch in f"*{_safe(text).upper()}*":
            pattern = _CODE39.get(ch)
            if not pattern:
                continue
            for index, bit in enumerate(pattern):
                width = wide if bit == "1" else narrow
                if draw and index % 2 == 0:
                    self.rect(cursor, y, width, h, style="F")
                cursor += width
            cursor += narrow
        return cursor - x

    def stamp_size(self, text: str, size: float = 14, sub: str | None = None) -> tuple[float, float]:
        """Ancho y alto (mm) que ocupa un sello rectangular, para poder centrarlo o dejarle sitio."""
        self.font(size, bold=True)
        icon = size * 0.62
        return self.get_string_width(_safe(text).upper()) + icon + 13, size * 0.5 + (4.6 if sub else 0) + 6.5

    def stamp(
        self, text: str, x: float | None = None, y: float | None = None, tone: str = "accent", angle: float = -9, size: float = 14, opacity: float = 0.62,
        sub: str | None = None, icon: str = "check", center: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        """Sello de tinta rectangular: doble borde, icono, la palabra grande y, debajo, una línea chica (fecha o código).
        Va inclinado y translúcido para que no tape lo que hay debajo. Con `center` se centra en ese punto (en vez de usar x, y).
        Devuelve su ancho y alto sin inclinar."""
        fg, _ = self.tone(tone)
        keep_x, keep_y = self.get_x(), self.get_y()
        text = _safe(text).upper()
        w, h = self.stamp_size(text, size, sub)
        if center is not None:
            x, y = center[0] - w / 2, center[1] - h / 2
        x, y = x or 0.0, y or 0.0
        ic = size * 0.62
        with self.rotation(angle, x + w / 2, y + h / 2):
            with self._alpha(opacity):
                self.set_draw_color(*fg)
                self.set_line_width(1.0)
                self.rect(x, y, w, h, style="D", round_corners=True, corner_radius=2.4)
                self.set_line_width(0.3)
                self.rect(x + 1.5, y + 1.5, w - 3, h - 3, style="D", round_corners=True, corner_radius=1.5)
                # icono en un círculo, a la izquierda
                icon_y = y + (h - ic) / 2 - (1.6 if sub else 0)
                self.set_line_width(0.7)
                self.circle(x + 5.2 + ic / 2, icon_y + ic / 2, ic / 2 + 0.9, style="D")
                self.icon(icon, x + 5.2 + ic * 0.15, icon_y + ic * 0.15, ic * 0.7, fg, 2.6)
                # palabra
                self.font(size, bold=True, color=fg)
                tx = x + 5.2 + ic + 3.6
                self.set_xy(tx, y + (h - size * 0.5) / 2 - (2.3 if sub else 0.2))
                self.cell(w - (tx - x) - 4, size * 0.5, text, align="C")
                if sub:
                    self.font(max(size * 0.45, 6), semi=True, color=fg)
                    self.set_xy(tx, y + h - 4.8 - 1.5)
                    self.cell(w - (tx - x) - 4, 3.6, self.fit(_safe(sub), w - (tx - x) - 5), align="C")
        self.set_xy(keep_x, keep_y)
        return w, h

    def seal(self, text: str, cx: float, cy: float, r: float = 15.0, tone: str = "accent", angle: float = -12, sub: str | None = None, icon: str = "check", opacity: float = 0.6) -> None:
        """Sello redondo de oficina (p. ej. el «ENTREGADO» del almacén sobre su firma): anillos, icono arriba, palabra en una banda
        y una línea chica abajo. Centrado en (cx, cy)."""
        fg, _ = self.tone(tone)
        keep_x, keep_y = self.get_x(), self.get_y()
        text = _safe(text).upper()
        with self.rotation(angle, cx, cy):
            with self._alpha(opacity):
                self.set_draw_color(*fg)
                self.set_line_width(1.0)
                self.circle(cx, cy, r, style="D")
                self.set_line_width(0.3)
                self.circle(cx, cy, r - 1.5, style="D")
                self.set_dash_pattern(dash=0.6, gap=1.0)
                self.circle(cx, cy, r - 3.2, style="D")
                self.set_dash_pattern()
                self.icon(icon, cx - r * 0.2, cy - r * 0.78, r * 0.4, fg, 2.7)
                # banda central con la palabra: más opaca que los anillos para que se lea bien
                size = 11.0
                self.font(size, bold=True, color=WHITE)
                while size > 6 and self.get_string_width(text) > r * 2 - 11:   # la palabra más grande que quepa en la banda
                    size -= 0.5
                    self.font(size, bold=True, color=WHITE)
                band_w = min(self.get_string_width(text) + 6, r * 2 - 4)
                with self._alpha(min(opacity + 0.3, 0.95)):
                    self.set_fill_color(*fg)
                    self.rect(cx - band_w / 2, cy - 3.2, band_w, 6.4, style="F", round_corners=True, corner_radius=1.2)
                    self.font(size, bold=True, color=WHITE)
                    self.set_xy(cx - band_w / 2, cy - 3.2)
                    self.cell(band_w, 6.4, text, align="C")
                if sub:
                    self.font(6.4, semi=True, color=fg)
                    self.set_xy(cx - r, cy + 4.6)
                    self.cell(r * 2, 3.2, self.fit(_safe(sub), r * 2 - 8), align="C")
        self.set_xy(keep_x, keep_y)

    def hazard(self, x: float, y: float, w: float, h: float, a: tuple[int, int, int], b: tuple[int, int, int], step: float = 5.0) -> None:
        """Franja de obra: rayas diagonales de dos colores (se recorta al rectángulo)."""
        self.set_fill_color(*a)
        self.rect(x, y, w, h, style="F")
        self.set_fill_color(*b)
        with self.rect_clip(x, y, w, h):
            cursor = x - h
            while cursor < x + w:
                self.polygon([(cursor, y + h), (cursor + step / 2, y + h), (cursor + step / 2 + h, y), (cursor + h, y)], style="F")
                cursor += step

    def dashed(self, x1: float, y: float, x2: float, color: tuple[int, int, int] = BORDER, dash: float = 1.6, gap: float = 1.4) -> None:
        self.set_draw_color(*color)
        self.set_line_width(0.3)
        self.set_dash_pattern(dash=dash, gap=gap)
        self.line(x1, y, x2, y)
        self.set_dash_pattern()

    # --------------------------------------------------------------------------------------------- portada y páginas
    def cover(self, label: str, title: str, meta: list[tuple[str, str]] | None = None, chip: tuple[str, str] | None = None, icon: str = "order") -> None:
        """Primera página: cada familia de documentos tiene su portada (franja, ticket, póster, obra o sobria)."""
        {"ticket": self._cover_ticket, "poster": self._cover_poster, "stripe": self._cover_stripe, "minimal": self._cover_minimal}.get(self.style, self._cover_band)(
            label, title, meta or [], chip, icon
        )
        self._cover_done = True
        self._draw_watermark()

    def _meta_right(self, meta: list[tuple[str, str]], y: float, key_color, value_color, width: float = 62, limit: int = 3) -> None:
        right = self.w - self.r_margin
        for key, value in meta[:limit]:
            self.font(7, color=key_color)
            self.set_xy(right - width, y)
            self.cell(width, 3.4, _safe(key).upper(), align="R")
            self.font(9, semi=True, color=value_color)
            self.set_xy(right - width, y + 3.2)
            self.cell(width, 4.2, self.fit(value, width), align="R")
            y += 7.8

    def _cover_band(self, label, title, meta, chip, icon) -> None:
        """Franja de dos tonos con círculos decorativos (orden de compra y documentos formales)."""
        top, band = 0.0, 32.0
        self.set_fill_color(*self.accent_dark)
        self.rect(0, top, self.w, band, style="F")
        self.set_fill_color(*self.accent)
        self.rect(self.w * 0.55, top, self.w * 0.45, band, style="F")
        self.set_fill_color(*self.accent_dark)
        self.rect(self.w * 0.55 - 8, top, 16, band, style="F")  # transición suave entre los dos tonos
        with self._alpha(0.10):
            self.set_fill_color(255, 255, 255)
            with self.rect_clip(0, 0, self.w, band):
                self.circle(self.w * 0.74, 4, 22, style="F")
                self.circle(self.w * 0.9, 30, 16, style="F")
                self.circle(self.w * 0.42, 38, 12, style="F")
        self.set_fill_color(255, 255, 255)
        self.rect(self.l_margin, 8, 11, 11, style="F", round_corners=True, corner_radius=2.6)
        self.icon(icon, self.l_margin + 2.1, 10.1, 6.8, self.accent_dark, 2.2)
        self.font(7.5, semi=True, color=(214, 208, 255))
        self.set_xy(self.l_margin + 14, 8.2)
        self.cell(60, 4, _safe(label).upper())
        self.font(17, bold=True, color=WHITE)
        self.set_xy(self.l_margin + 14, 12.4)
        self.cell(110, 8, self.fit(title, 110))
        self._meta_right(meta, 6.4, (214, 208, 255), WHITE)
        if chip:
            self.chip(self.l_margin + 14, 22.4, chip[0], chip[1])
        self.set_y(band + 7)

    def _cover_ticket(self, label, title, meta, chip, icon) -> None:
        """Vale / boleta: franja con muescas de talonario, código de barras del número y línea de corte."""
        band = 40.0
        self.set_fill_color(*self.accent_dark)
        self.rect(0, 0, self.w, band, style="F")
        self.set_fill_color(*self.accent)
        self.rect(0, 0, self.w, 4, style="F")
        with self._alpha(0.09):
            self.set_fill_color(255, 255, 255)
            with self.rect_clip(0, 0, self.w, band):
                self.circle(self.w * 0.28, 8, 26, style="F")
                self.circle(self.w * 0.62, 48, 20, style="F")
        # muescas del talonario a ambos lados
        self.set_fill_color(255, 255, 255)
        self.circle(-0.5, band, 4.2, style="F")
        self.circle(self.w + 0.5, band, 4.2, style="F")
        self.set_fill_color(255, 255, 255)
        self.rect(self.l_margin, 10, 12, 12, style="F", round_corners=True, corner_radius=3)
        self.icon(icon, self.l_margin + 2.3, 12.3, 7.4, self.accent_dark, 2.2)
        self.font(7.5, semi=True, color=(205, 240, 238))
        self.set_xy(self.l_margin + 16, 9.6)
        self.cell(80, 4, _safe(label).upper())
        self.font(22, bold=True, color=WHITE)
        self.set_xy(self.l_margin + 16, 14.2)
        self.cell(90, 10, self.fit(title, 90))
        if chip:
            self.chip(self.l_margin + 16, 27.6, chip[0], chip[1])
        # tarjeta blanca con el código de barras del número
        right = self.w - self.r_margin
        card_w = 70.0
        self.set_fill_color(255, 255, 255)
        self.rect(right - card_w, 8.5, card_w, 25, style="F", round_corners=True, corner_radius=2.6)
        natural = self.barcode(0, 0, title, h=1, draw=False)
        scale = min(1.0, (card_w - 12) / max(natural, 1))
        self.barcode(right - card_w + (card_w - natural * scale) / 2, 12, title, h=11, narrow=0.32 * scale, color=self.accent_dark)
        self.font(7.5, semi=True, color=self.accent_dark)
        self.set_xy(right - card_w, 24.4)
        self.cell(card_w, 3.6, _safe(title), align="C")
        if meta:
            self.font(6.6, color=MUTED)
            self.set_xy(right - card_w, 28.2)
            self.cell(card_w, 3, f"{_safe(meta[0][0])}: {_safe(meta[0][1])}", align="C")
        self.dashed(self.l_margin, band + 4, self.w - self.r_margin, color=self.accent)
        self.set_y(band + 10)

    def _cover_poster(self, label, title, meta, chip, icon) -> None:
        """Reportes: póster oscuro con barras de gráfico decorativas y el título grande."""
        band = 40.0
        self.set_fill_color(*self.accent_dark)
        self.rect(0, 0, self.w, band, style="F")
        heights = [8, 13, 10, 18, 15, 24, 20, 28, 25, 33, 30]   # barras decorativas, cada vez más altas
        x0 = self.w * 0.62
        step = (self.w - x0 - self.r_margin) / len(heights)
        with self._alpha(0.18):
            self.set_fill_color(255, 255, 255)
            for i, hh in enumerate(heights):
                self.rect(x0 + i * step, band - hh - 3, step * 0.62, hh, style="F", round_corners=True, corner_radius=1)
        with self._alpha(0.07):
            self.set_fill_color(255, 255, 255)
            with self.rect_clip(0, 0, self.w, band):
                self.circle(self.w * 0.18, 4, 30, style="F")
        self.set_fill_color(*self.accent)
        self.rect(0, band - 2.2, self.w, 2.2, style="F")
        self.set_fill_color(255, 255, 255)
        self.rect(self.l_margin, 9, 12, 12, style="F", round_corners=True, corner_radius=3)
        self.icon(icon, self.l_margin + 2.3, 11.3, 7.4, self.accent_dark, 2.2)
        self.font(7.5, semi=True, color=(205, 220, 255))
        self.set_xy(self.l_margin + 16, 9.2)
        self.cell(100, 4, _safe(label).upper())
        self.font(19, bold=True, color=WHITE)
        self.set_xy(self.l_margin + 16, 13.4)
        self.cell(self.w * 0.55, 9, self.fit(title, self.w * 0.55))
        x = self.l_margin + 16
        for key, value in meta[:2]:
            self.font(7.2, color=(220, 232, 255))
            text = f"{_safe(key)}: {_safe(value)}"
            width = self.get_string_width(text) + 6
            with self._alpha(0.16):
                self.set_fill_color(255, 255, 255)
                self.rect(x, 26, width, 6, style="F", round_corners=True, corner_radius=3)
            self.font(7.2, color=(220, 232, 255))
            self.set_xy(x, 26)
            self.cell(width, 6, text, align="C")
            x += width + 3
        if chip:
            self.chip(x, 26.3, chip[0], chip[1])
        self.set_y(band + 8)

    def _cover_stripe(self, label, title, meta, chip, icon) -> None:
        """Obra: franja de peligro (rayas), nombre de la obra en grande sobre fondo claro."""
        self.hazard(0, 0, self.w, 7, self.accent_dark, self.accent, step=6)
        self.set_fill_color(*self.soft)
        self.rect(0, 7, self.w, 27, style="F")
        self.set_fill_color(*self.accent)
        self.rect(self.l_margin, 12, 15, 15, style="F", round_corners=True, corner_radius=3.4)
        self.icon(icon, self.l_margin + 3.1, 15.1, 8.8, WHITE, 2.1)
        self.font(7.5, semi=True, color=self.accent_dark)
        self.set_xy(self.l_margin + 19, 11.6)
        self.cell(90, 4, _safe(label).upper())
        self.font(19, bold=True, color=TEXT)
        self.set_xy(self.l_margin + 19, 16.4)
        self.cell(self.w * 0.5, 9, self.fit(title, self.w * 0.5))
        if chip:
            self.chip(self.l_margin + 19, 27, chip[0], chip[1])
        self._meta_right(meta, 11.4, MUTED, TEXT, width=90, limit=2)
        self.set_fill_color(*self.accent)
        self.rect(0, 34, self.w, 0.9, style="F")
        self.set_y(34 + 8)

    def _cover_minimal(self, label, title, meta, chip, icon) -> None:
        """Libro mayor (kardex): encabezado sobrio con barra de color y una sola línea de datos."""
        self.set_fill_color(*self.accent)
        self.rect(self.l_margin, 9, 2.2, 17, style="F", round_corners=True, corner_radius=1.1)
        self.icon(icon, self.l_margin + 6, 9.4, 6, self.accent, 2.1)
        self.font(7.5, semi=True, color=self.accent)
        self.set_xy(self.l_margin + 14, 9.4)
        self.cell(100, 4, _safe(label).upper())
        self.font(18, bold=True, color=TEXT)
        self.set_xy(self.l_margin + 6, 15.2)
        self.cell(self.w * 0.6, 9, self.fit(title, self.w * 0.6))
        self._meta_right(meta, 8.2, MUTED, TEXT, width=80, limit=2)
        if chip:
            self.chip(self.w - self.r_margin - 40, 21, chip[0], chip[1])
        self.set_draw_color(*self.accent)
        self.set_line_width(0.5)
        self.line(self.l_margin, 28.6, self.w - self.r_margin, 28.6)
        self.set_y(28.6 + 7)

    def header(self) -> None:
        if not self._cover_done:
            return  # la primera página lleva portada
        if self.style == "stripe":
            self.hazard(0, 0, self.w, 2.4, self.accent_dark, self.accent, step=5)
        else:
            self.set_fill_color(*self.accent)
            self.rect(0, 0, self.w, 1.6, style="F")
        self.set_fill_color(*self.soft)
        self.rect(self.l_margin, 6, 5.5, 5.5, style="F", round_corners=True, corner_radius=1.4)
        self.icon("order", self.l_margin + 1.0, 7.0, 3.5, self.accent, 2.4)
        self.font(8, semi=True, color=self.accent_dark)
        self.set_xy(self.l_margin + 8, 6.2)
        self.cell(80, 5, _safe(f"{self.kind}  {self.code}").strip())
        self.font(7.5, color=MUTED)
        self.set_xy(self.w - self.r_margin - 60, 6.2)
        self.cell(60, 5, "Sistema MRP", align="R")
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, 13, self.w - self.r_margin, 13)
        self.set_y(18)
        self._draw_watermark()

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.font(7, color=MUTED)
        self.set_xy(self.l_margin, self.get_y() + 1.6)
        self.cell(self.usable * 0.7, 4, f"Generado el {clock.now():%d/%m/%Y a las %H:%M}  ·  Sistema MRP  ·  {APP_VERSION}")
        self.cell(self.usable * 0.3, 4, f"Página {self.page_no()} de {{nb}}", align="R")

    # --------------------------------------------------------------------------------------------- bloques
    def section(self, text: str, icon: str | None = None, count: int | str | None = None) -> None:
        """Título de sección con icono y, si se pide, un contador."""
        if self.get_y() > self.h - 40:
            self.add_page()
        y = self.get_y()
        x = self.l_margin
        if icon:
            self.icon(icon, x, y + 0.3, 5, self.accent, 2.0)
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
        pad = 4.0
        col_w = (width - pad * 2) / columns
        rows = -(-len(items) // columns)
        # un valor que no cabe en una línea se parte en dos (en vez de cortarlo con «…»); esa fila crece
        self.font(9, semi=True)
        values = []
        for key, value, icon in items:
            room = col_w - 8 - (6 if icon else 0)
            values.append(self.wrap(value, room, max_lines=2) if self.get_string_width(_safe(value)) > room else [_safe(value)])
        row_heights = [10.5 + (3.9 if any(len(values[r * columns + c]) > 1 for c in range(columns) if r * columns + c < len(items)) else 0.0) for r in range(rows)]
        title_h = 7.5 if title else 0.0
        height = pad * 2 + sum(row_heights) + title_h - 1.5
        y0 = self.get_y()
        if y0 + height > self.h - 20:
            self.add_page()
            y0 = self.get_y()
        self.box(x0, y0, width, height, fill=WHITE)
        self.set_fill_color(*self.accent)
        self.rect(x0, y0 + 3.5, 0.9, height - 7, style="F")
        cy = y0 + pad
        if title:
            self.font(8, semi=True, color=self.accent_dark)
            self.set_xy(x0 + pad + 1, cy - 0.5)
            self.cell(width - pad * 2, 4, _safe(title).upper())
            cy += title_h
        for index, (key, value, icon) in enumerate(items):
            col, row = index % columns, index // columns
            cx, ry = x0 + pad + 1 + col * col_w, cy + sum(row_heights[:row])
            text_x = cx
            if icon:
                self.icon(icon, cx, ry + 0.9, 4.2, MUTED, 2.0)
                text_x += 6
            self.font(6.8, semi=True, color=MUTED)
            self.set_xy(text_x, ry)
            self.cell(col_w - 7, 3.4, _safe(key).upper())
            lines = values[index]
            self.font(9 if len(lines) == 1 else 8.4, semi=True)
            for n, line in enumerate(lines):
                self.set_xy(text_x, ry + 3.6 + n * 4.1)
                self.cell(col_w - 7, 4.4, line)
        self.set_y(y0 + height + 3)
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
            fg, bg = self.tone(card.get("tone", "accent"))
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
        tones: dict[int, dict[int, str]] | None = None, bold_last_row: bool = False, size: float = 8, look: str | None = None,
        colors: dict[tuple[int, int], tuple[int, int, int]] | None = None,
    ) -> None:
        """Tabla con encabezado de color, filas alternadas y texto recortado con «…». `widths` son pesos relativos;
        `align` por columna ('L' o 'R'); `tones[fila][columna]` pinta esa celda como etiqueta ('good', 'bad', 'warn'…).
        `look`: «zebra» (filas alternadas, el predeterminado), «lines» (libro mayor: encabezado claro y líneas finas) o «cards»."""
        look = look or {"minimal": "lines", "ticket": "cards"}.get(self.style, "zebra")
        total = sum(widths)
        cols = [w / total * self.usable for w in widths]
        align = align or ["L"] * len(columns)

        def head() -> None:
            y = self.get_y()
            if look == "lines":
                self.set_fill_color(*self.soft)
                self.rect(self.l_margin, y, self.usable, 7.4, style="F")
                self.set_draw_color(*self.accent)
                self.set_line_width(0.4)
                self.line(self.l_margin, y + 7.4, self.l_margin + self.usable, y + 7.4)
            else:
                self.set_fill_color(*self.accent_dark)
                self.rect(self.l_margin, y, self.usable, 7.4, style="F", round_corners=True, corner_radius=1.6)
            self.font(7.4, semi=True, color=self.accent_dark if look == "lines" else WHITE)
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
                self.set_fill_color(*self.soft)
                self.rect(self.l_margin, y, self.usable, row_h, style="F", round_corners=True, corner_radius=1.2)
            elif look == "zebra" and r % 2 == 1:
                self.set_fill_color(*PAPER)
                self.rect(self.l_margin, y, self.usable, row_h, style="F")
            elif look == "lines":
                self.set_draw_color(*BORDER)
                self.set_line_width(0.15)
                self.line(self.l_margin, y + row_h, self.l_margin + self.usable, y + row_h)
            elif look == "cards":
                self.set_draw_color(*BORDER)
                self.set_line_width(0.2)
                self.set_dash_pattern(dash=1.2, gap=1.2)
                self.line(self.l_margin, y + row_h, self.l_margin + self.usable, y + row_h)
                self.set_dash_pattern()
            x = self.l_margin
            for c, (value, w, a) in enumerate(zip(row, cols, align)):
                tone = (tones or {}).get(r, {}).get(c)
                if columns[c] == "Verif.":
                    self.set_draw_color(*self.accent)
                    self.set_line_width(0.35)
                    self.set_fill_color(*WHITE)
                    self.rect(x + (w - 4.2) / 2, y + (row_h - 4.2) / 2, 4.2, 4.2, style="DF", round_corners=True, corner_radius=0.9)
                elif tone and _safe(value):
                    self.chip(x + 1.4 if a == "L" else x + w - 1.4, y + (row_h - 5) / 2, self.fit(value, w - 3), tone, size=6.8, h=5, align=a if a == "R" else "L")
                else:
                    colored = (colors or {}).get((r, c))
                    self.font(size, bold=last or bool(colored), color=colored or TEXT)
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
        self.set_fill_color(*self.accent_dark)
        self.rect(x, cy + 0.6, width, 9, style="F", round_corners=True, corner_radius=2.2)
        self.font(8.5, semi=True, color=(214, 208, 255))
        self.set_xy(x + 4, cy + 0.6)
        self.cell(width / 2, 9, _safe(total[0]).upper())
        self.font(11.5, bold=True, color=WHITE)
        self.cell(width / 2 - 8, 9, _safe(total[1]), align="R")
        self.set_y(y + h + 3)

    def note_box(self, title: str, text: str, icon: str = "note", tone: str = "warn") -> None:
        """Recuadro de color con un texto (notas, observaciones)."""
        text = _safe(text)
        if not text:
            return
        fg, bg = self.tone(tone)
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
        self.set_y(y + h + 3)

    def signatures(self, labels: list[tuple[str, str | None]], seal: dict | None = None) -> None:
        """Líneas de firma: cada una con su rol y, opcionalmente, el nombre de quien firma. `seal` (argumentos de `seal()`) estampa
        un sello redondo sobre la primera firma, como el de un almacén."""
        needed = 26 + (20 if seal else 0)
        if self.get_y() + needed > self.h - 18:   # el bloque entero (aire, sello y firmas) tiene que caber
            self.add_page()
        self.ln(4 + (20 if seal else 0))
        y = self.get_y()
        n = len(labels)
        gap = 10.0
        w = (self.usable - gap * (n - 1)) / n
        for i, (role, name) in enumerate(labels):
            x = self.l_margin + i * (w + gap)
            self.set_draw_color(*MUTED)
            self.set_line_width(0.3)
            self.line(x, y + 11, x + w, y + 11)
            self.font(8, semi=True)
            self.set_xy(x, y + 12.2)
            self.cell(w, 4, _safe(role), align="C")
            if name:
                self.font(7.5, color=MUTED)
                self.set_xy(x, y + 16.4)
                self.cell(w, 4, self.fit(name, w), align="C")
        if seal:
            first_w = w
            self.seal(cx=self.l_margin + first_w / 2, cy=y - 4.5, **seal)
        self.set_y(y + 22)

    # --------------------------------------------------------------------------------------------- gráficos y visuales
    def watermark(self, text: str, tone: str = "bad") -> None:
        """Texto grande en diagonal, muy tenue, detrás del contenido (p. ej. «CANCELADA»). Se repite en cada página."""
        self._watermark = (text, tone)
        self._draw_watermark()

    def _draw_watermark(self) -> None:
        mark = getattr(self, "_watermark", None)
        if not mark:
            return
        text, tone = mark
        fg, _ = self.tone(tone)
        keep_x, keep_y = self.get_x(), self.get_y()
        size = 62 if self.w < 250 else 54
        self.font(size, bold=True, color=fg)
        width = self.get_string_width(_safe(text).upper())
        cx, cy = self.w / 2, self.h / 2
        with self.rotation(35, cx, cy):
            with self._alpha(0.07):
                self.set_xy(cx - width / 2, cy - size * 0.18)
                self.cell(width, size * 0.36, _safe(text).upper(), align="C")
        self.set_xy(keep_x, keep_y)

    def donut(self, cx: float, cy: float, r: float, fraction: float | None, tone: str = "accent", label: str | None = None, sub: str | None = None, thickness: float = 0.30) -> None:
        """Anillo de avance con la cifra al centro (`fraction` de 0 a 1; None = sin dato)."""
        fg, _ = self.tone(tone)
        value = max(0.0, min(fraction or 0.0, 1.0))
        self.set_fill_color(*BORDER)
        self.circle(cx, cy, r, style="F")
        if value >= 0.999:
            self.set_fill_color(*fg)
            self.circle(cx, cy, r, style="F")
        elif value > 0:
            self.set_fill_color(*fg)
            steps = max(int(360 * value / 3), 2)      # el sector se arma con un polígono: a las 12 en punto y en sentido horario
            points = [(cx, cy)] + [
                (cx + r * math.cos(math.radians(-90 + 360 * value * i / steps)), cy + r * math.sin(math.radians(-90 + 360 * value * i / steps)))
                for i in range(steps + 1)
            ]
            self.polygon(points, style="F")
        self.set_fill_color(*WHITE)
        self.circle(cx, cy, r * (1 - thickness), style="F")
        if label:
            self.font(r * 0.95, bold=True, color=fg if fraction is not None else MUTED)
            self.set_xy(cx - r, cy - r * 0.42)
            self.cell(r * 2, r * 0.55, _safe(label), align="C")
        if sub:
            self.font(max(r * 0.38, 5.5), color=MUTED)
            self.set_xy(cx - r, cy + r * 0.2)
            self.cell(r * 2, r * 0.4, _safe(sub), align="C")

    def hbars(self, x: float, y: float, w: float, items: list[tuple[str, float, str, str]], row_h: float = 8.5, label_w: float = 34.0) -> float:
        """Barras horizontales comparativas. Cada ítem: (etiqueta, valor, tono, texto del valor). Devuelve el alto usado."""
        top = max((v for _, v, _, _ in items), default=0) or 1.0
        value_w = 30.0
        track = w - label_w - value_w - 4
        for index, (label, value, tone, text) in enumerate(items):
            ry = y + index * row_h
            fg, _ = self.tone(tone)
            self.font(8, semi=True, color=TEXT)
            self.set_xy(x, ry)
            self.cell(label_w, row_h - 1, self.fit(label, label_w - 1))
            self.set_fill_color(*BORDER)
            self.rect(x + label_w, ry + 1.6, track, row_h - 4.2, style="F", round_corners=True, corner_radius=(row_h - 4.2) / 2)
            self.set_fill_color(*fg)
            self.rect(x + label_w, ry + 1.6, max(track * (value / top), 1.6), row_h - 4.2, style="F", round_corners=True, corner_radius=(row_h - 4.2) / 2)
            self.font(8.4, bold=True, color=fg)
            self.set_xy(x + label_w + track + 3, ry)
            self.cell(value_w, row_h - 1, _safe(text), align="R")
        return len(items) * row_h

    def linechart(self, x: float, y: float, w: float, h: float, values: list[float], tone: str = "accent") -> None:
        """Línea con área sombreada y puntos (p. ej. la evolución del saldo de un material). Marca el mínimo y el máximo."""
        values = [float(v) for v in values]
        if len(values) < 2:
            return
        fg, bg = self.tone(tone)
        lo, hi = min(values + [0.0]), max(values)
        span = (hi - lo) or 1.0
        pad_x, pad_y = 3.0, 4.0
        pts = [(x + pad_x + i / (len(values) - 1) * (w - pad_x * 2), y + h - pad_y - (v - lo) / span * (h - pad_y * 2)) for i, v in enumerate(values)]
        self.set_draw_color(*BORDER)
        self.set_line_width(0.15)
        for k in range(3):
            gy = y + pad_y + k * (h - pad_y * 2) / 2
            self.set_dash_pattern(dash=0.8, gap=1.2)
            self.line(x + pad_x, gy, x + w - pad_x, gy)
        self.set_dash_pattern()
        with self._alpha(0.35):
            self.set_fill_color(*bg)
            self.polygon([(pts[0][0], y + h - pad_y - (0 - lo) / span * (h - pad_y * 2))] + pts + [(pts[-1][0], y + h - pad_y - (0 - lo) / span * (h - pad_y * 2))], style="F")
        self.set_draw_color(*fg)
        self.set_line_width(0.6)
        self.polyline(pts)
        self.set_fill_color(*fg)
        for px, py in pts:
            self.circle(px, py, 0.9, style="F")
        for idx, label in ((values.index(max(values)), f"máx. {max(values):,.0f}"), (values.index(min(values)), f"mín. {min(values):,.0f}")):
            if idx == values.index(max(values)) and label.startswith("mín") and min(values) == max(values):
                continue
            px, py = pts[idx]
            self.font(6.8, semi=True, color=fg)
            self.set_xy(min(max(px - 12, x), x + w - 24), py - 4.6 if label.startswith("máx") else py + 1.2)
            self.cell(24, 3.4, label, align="C")

    def timeline(self, steps: list[tuple[str, str, str]], title: str | None = None) -> None:
        """Línea de tiempo horizontal. Cada paso: (nombre, texto, estado) con estado «done», «current» o «todo»."""
        h = 22.0 if title else 18.0
        y = self.get_y()
        if y + h > self.h - 20:
            self.add_page()
            y = self.get_y()
        self.box(self.l_margin, y, self.usable, h, fill=WHITE)
        top = y + 4.0
        if title:
            self.font(8, semi=True, color=self.accent_dark)
            self.set_xy(self.l_margin + 5, y + 3)
            self.cell(80, 4, _safe(title).upper())
            top = y + 8.2
        n = len(steps)
        inner = self.usable - 24
        gap = inner / max(n - 1, 1)
        x0 = self.l_margin + 12
        for i in range(n - 1):
            done = steps[i][2] == "done" and steps[i + 1][2] in ("done", "current")
            self.set_draw_color(*(self.accent if done else BORDER))
            self.set_line_width(0.8)
            self.line(x0 + i * gap + 2.6, top + 2.6, x0 + (i + 1) * gap - 2.6, top + 2.6)
        for i, (name, text, state) in enumerate(steps):
            cx = x0 + i * gap
            if state == "done":
                self.set_fill_color(*self.accent)
                self.circle(cx, top + 2.6, 2.6, style="F")
                self.icon("check", cx - 1.6, top + 1.0, 3.2, WHITE, 3.0)
            elif state == "current":
                self.set_fill_color(*self.soft)
                self.circle(cx, top + 2.6, 3.0, style="F")
                self.set_fill_color(*self.accent)
                self.circle(cx, top + 2.6, 1.5, style="F")
            else:
                self.set_fill_color(*WHITE)
                self.set_draw_color(*BORDER)
                self.set_line_width(0.5)
                self.circle(cx, top + 2.6, 2.4, style="D")
            self.font(7.6, semi=True, color=TEXT if state != "todo" else MUTED)
            self.set_xy(cx - gap / 2, top + 6.2)
            self.cell(gap, 3.6, self.fit(name, gap - 2), align="C")
            self.font(6.8, color=MUTED)
            self.set_xy(cx - gap / 2, top + 9.8)
            self.cell(gap, 3.2, self.fit(text, gap - 2), align="C")
        self.set_y(y + h + 3)

    def index_card(self, items: list[tuple[str, int]], title: str = "Contenido") -> None:
        """Índice del documento: cada sección con su número, su nombre y cuántos registros trae (con una barrita proporcional)."""
        if not items:
            return
        columns = 2 if len(items) > 3 else 1
        rows = -(-len(items) // columns)
        row_h = 8.2
        h = 12 + rows * row_h
        y = self.get_y()
        if y + h > self.h - 20:
            self.add_page()
            y = self.get_y()
        self.box(self.l_margin, y, self.usable, h, fill=WHITE)
        self.set_fill_color(*self.accent)
        self.rect(self.l_margin, y + 3.5, 0.9, h - 7, style="F")
        self.font(8, semi=True, color=self.accent_dark)
        self.set_xy(self.l_margin + 5, y + 3.2)
        self.cell(60, 4, _safe(title).upper())
        top = max(count for _, count in items) or 1
        col_w = (self.usable - 10) / columns
        for index, (name, count) in enumerate(items):
            col, row = index // rows, index % rows
            cx, cy = self.l_margin + 5 + col * col_w, y + 10 + row * row_h
            self.set_fill_color(*self.soft)
            self.circle(cx + 2.6, cy + 3, 2.6, style="F")
            self.font(7, bold=True, color=self.accent_dark)
            self.set_xy(cx, cy + 1.2)
            self.cell(5.2, 3.6, str(index + 1), align="C")
            self.font(8.4, semi=True)
            self.set_xy(cx + 7, cy + 1)
            self.cell(col_w * 0.5, 4, self.fit(name, col_w * 0.5 - 1))
            bar_x, bar_w = cx + 7 + col_w * 0.5, col_w * 0.25
            self.set_fill_color(*BORDER)
            self.rect(bar_x, cy + 2.2, bar_w, 1.8, style="F", round_corners=True, corner_radius=0.9)
            self.set_fill_color(*self.accent)
            self.rect(bar_x, cy + 2.2, max(bar_w * count / top, 1.2), 1.8, style="F", round_corners=True, corner_radius=0.9)
            self.font(7.6, bold=True, color=MUTED)
            self.set_xy(bar_x + bar_w + 1.5, cy + 1.2)
            self.cell(col_w * 0.2, 3.6, f"{count:,}")
        self.set_y(y + h + 5)
