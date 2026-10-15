"""Carga las hojas de estilo de `modules/styles/` en orden.

La apariencia vive en archivos CSS reales (con sus propios comentarios) en
vez de cadenas de Python:

    palette_light.css / palette_dark.css   variables --mrp-* de cada tema
    00_base · 10_layout · 20_sidebar · 30_controls · 40_components ·
    50_forms · 60_responsive               reglas, de lo general a lo específico

`ui.inject()` usa `LIGHT`/`DARK` según el tema, `FONT_IMPORT` (que debe ir
primero en su propia hoja) y `CSS` (todas las hojas numeradas, minificadas)."""
import re
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "styles"


def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8")


def _minify(css: str) -> str:
    """Quita comentarios y espacios sobrantes: st.markdown interpreta las
    líneas en blanco e indentadas de una hoja larga como Markdown, no como CSS."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    return re.sub(r"\s*([{};,])\s*", r"\1", css).strip()


_ALL = "\n".join(_read(path.name) for path in sorted(_DIR.glob("[0-9][0-9]_*.css")))

LIGHT = _minify(_read("palette_light.css"))
DARK = _minify(_read("palette_dark.css"))
# un @import solo funciona al inicio de una hoja: se separa para ponerlo primero
FONT_IMPORT = "\n".join(line for line in _ALL.splitlines() if line.startswith("@import"))
CSS = _minify("\n".join(line for line in _ALL.splitlines() if not line.startswith("@import")))
