"""Carga las hojas de estilo de `modules/styles/` en orden.

La apariencia vive en archivos CSS reales (con sus propios comentarios) en
vez de cadenas de Python:

    palette_light.css / palette_dark.css   variables --mrp-* de cada tema
    00_base · 10_layout · 20_sidebar · 30_controls · 40_components ·
    50_forms · 60_responsive               reglas, de lo general a lo específico

Streamlit solo recarga los módulos `.py` que cambian, no los `.css`; si las
hojas se leyeran una sola vez al importar, un despliegue que solo toque CSS
(Streamlit Cloud actualiza los archivos sin reiniciar el proceso) seguiría
mostrando el estilo viejo. Por eso `bundle()` revisa la fecha de modificación
de los archivos en cada recarga y vuelve a leerlos solo si cambiaron."""
import re
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "styles"


def _minify(css: str) -> str:
    """Quita comentarios y espacios sobrantes: st.markdown interpreta las
    líneas en blanco e indentadas de una hoja larga como Markdown, no como CSS."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    return re.sub(r"\s*([{};,])\s*", r"\1", css).strip()


def _files() -> list[Path]:
    return sorted(_DIR.glob("*.css"))


def _signature() -> tuple:
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in _files())


@lru_cache(maxsize=2)
def _build(signature: tuple) -> dict[str, str]:
    read = lambda name: (_DIR / name).read_text(encoding="utf-8")
    sheets = "\n".join(read(p.name) for p in _files() if p.name[:2].isdigit())
    # un @import solo funciona al inicio de una hoja: se separa para ponerlo primero
    return {
        "light": _minify(read("palette_light.css")),
        "dark": _minify(read("palette_dark.css")),
        "dark_extra": _minify(read("dark_extra.css")),
        "font": "\n".join(line for line in sheets.splitlines() if line.startswith("@import")),
        "css": _minify("\n".join(line for line in sheets.splitlines() if not line.startswith("@import"))),
    }


def bundle() -> dict[str, str]:
    """Hojas actuales: claves `light`, `dark`, `font` y `css`."""
    return _build(_signature())
