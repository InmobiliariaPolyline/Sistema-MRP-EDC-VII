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
