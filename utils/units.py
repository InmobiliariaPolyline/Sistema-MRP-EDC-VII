"""Lista cerrada de métricas de cómputo (la unidad en que se presupuesta, pide y cuenta cada material).

Evita que el mismo dato quede escrito de varias formas («m3», «M³», «Volumen (m3)»…): el formulario
ofrece las métricas ya usadas más las estándar, y cualquier texto nuevo se normaliza antes de guardarse."""
from __future__ import annotations

import re
from collections import Counter

STANDARD = [
    "Área (m²)", "Volumen (m³)", "Peso (kg)", "Longitud (m)", "unidad", "Peso (kg / ton)",
    "Capacidad (litros)", "Capacidad (galones)", "bolsa", "saco", "rollo", "plancha", "caja", "balde", "juego", "millar", "global",
]

_REPLACEMENTS = [
    (re.compile(r"m\s*\^?\s*3\b", re.I), "m³"),
    (re.compile(r"m\s*\^?\s*2\b", re.I), "m²"),
    (re.compile(r"\bkgs?\b", re.I), "kg"),
    (re.compile(r"\btons?\b|\btoneladas?\b", re.I), "ton"),
    (re.compile(r"\bunidades\b|\bund\b|\bunid\b|\bunidad\b", re.I), "unidad"),
]


def normalize(text: str | None, known: list[str] | None = None) -> str:
    """Texto limpio y con las unidades escritas de una sola forma. Si coincide (sin importar mayúsculas)
    con una métrica conocida, devuelve esa métrica tal cual está escrita."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for pattern, replacement in _REPLACEMENTS:
        value = pattern.sub(replacement, value)
    for option in [*(known or []), *STANDARD]:
        if option.lower() == value.lower():
            return option
    return value


def options(existing: list[str | None]) -> list[str]:
    """Métricas para elegir: las ya usadas en el catálogo (más frecuentes primero) y luego las estándar que falten."""
    counts = Counter(normalize(x) for x in existing if x and str(x).strip())
    used = [name for name, _ in counts.most_common()]
    return used + [s for s in STANDARD if s not in used]


def _first_segment(label: str | None) -> str:
    """La primera medida de una métrica compuesta: «Peso (kg) / Longitud (m)» → «Peso (kg)»; «Peso (kg / ton)» → «Peso (kg / ton)»."""
    text = str(label or "").split(" — ")[0].strip()
    depth, start = 0, 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif char == "/" and depth == 0:
            return text[start:index].strip()
    return text


def primary(label: str | None) -> str:
    """La unidad en que se pide y se cotiza un material (la primera de su métrica): «Peso (kg) / Longitud (m)» → «kg»,
    «Área (m²) / unidad» → «m²», «unidad» → «unid.»; sin métrica → «unid.»."""
    first = _first_segment(label)
    match = re.search(r"\(([^)]*)\)", first)
    unit = match.group(1).split("/")[0].strip() if match else first
    return "unid." if not unit or unit.lower() in ("unidad", "unidades", "unid", "unid.") else unit


def primary_label(label: str | None) -> str:
    """La primera medida con una sola unidad: «Peso (kg / ton) / Longitud (m)» → «Peso (kg)»."""
    first = _first_segment(label)
    match = re.search(r"^(.*?)\(([^)]*)\)", first)
    if not match:
        return first or "unidad"
    return f"{match.group(1).strip()} ({match.group(2).split('/')[0].strip()})".strip()
