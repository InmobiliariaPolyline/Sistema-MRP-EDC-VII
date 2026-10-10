"""Ayudas y reglas compartidas entre los formularios y la validación en vivo."""
from __future__ import annotations

import html
import math
import re
import unicodedata

import streamlit as st

PERSON = r"[\p{L}\p{M} .'’\-]"
TEXT = r'''[\p{L}\p{M}\p{N}\p{S}\p{Pd} .,;:'’"“”&()\[\]/#%+_=°ºª·′″]'''

RULES = {
    "Nombre del proveedor": {"required": True, "min": 2, "max": 120, "allowed": TEXT, "kind": "text", "hint": "Ej. Ferretería Norte"},
    "Persona de contacto (opcional)": {"max": 100, "allowed": PERSON, "kind": "person", "hint": "Ej. Ana Ruiz"},
    "Teléfono": {"max": 25, "allowed": r"[0-9+()\-\s]", "kind": "phone", "digits": [7, 15], "hint": "Ej. +51 987 654 321"},
    "Correo (opcional)": {"max": 120, "kind": "email", "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", "pattern_msg": "Usa un correo como ventas@empresa.com", "hint": "Ej. ventas@empresa.com"},
    "Notas (opcional)": {"max": 500, "hint": "Condiciones de entrega u otra información útil"},
    "Nota (opcional)": {"max": 500, "hint": "Explica el motivo del movimiento"},
    "Categoría": {"required": True, "min": 2, "max": 100, "allowed": TEXT, "kind": "text", "hint": "Ej. Concreto"},
    "Nombre": {"required": True, "min": 2, "max": 180, "allowed": TEXT, "kind": "text", "hint": "Ej. Concreto f'c=210"},
    "Métrica de cómputo": {"max": 100, "allowed": TEXT, "kind": "text", "hint": "Ej. Volumen (m³)"},
    "Densidad (kg/m³, opcional)": {"optional_number": True, "num": {"min": 0, "max": 1000000}, "hint": "0 o vacío = sin densidad registrada"},
    "Nombre completo": {"required": True, "min": 3, "max": 120, "allowed": PERSON, "kind": "person", "hint": "Ej. Juan Pérez"},
    "Documento (opcional)": {"max": 30, "allowed": r"[A-Za-z0-9\-\s]", "kind": "document", "hint": "DNI, carné de extranjería u otro documento"},
    "Puesto (opcional)": {"max": 100, "allowed": TEXT, "kind": "text", "hint": "Ej. Capataz"},
    "Nombre de la cuadrilla": {"required": True, "min": 2, "max": 100, "allowed": TEXT, "kind": "text", "hint": "Ej. Electricistas"},
    "Nombre de la obra": {"required": True, "min": 2, "max": 120, "allowed": TEXT, "kind": "text", "hint": "Ej. Torre Central"},
    "Dirección": {"max": 250, "hint": "Calle y número, distrito y ciudad"},
    "Usuario": {"required": True, "min": 3, "max": 50, "allowed": r"[A-Za-z0-9._\-]", "kind": "username", "hint": "Ej. jperez"},
    "Cantidad": {"num": {"gt0": True}, "hint": "Indica la cantidad en la unidad del material"},
    "Cantidad prevista": {"num": {"gt0": True}},
    "Precio unit.": {"num": {"min": 0}, "hint": "0 = precio sin registrar"},
    "Precio unit. estimado": {"num": {"min": 0}},
    "Recibido ahora": {"num": {"min": 0}},
}


def rule_for(label: str) -> dict | None:
    if label in RULES:
        return RULES[label]
    for prefix in ("Cantidad prevista", "Recibido ahora"):
        if label.startswith(prefix):
            return RULES[prefix]
    return None


def _allowed(char: str, kind: str) -> bool:
    letter = unicodedata.category(char).startswith(("L", "M"))
    if kind == "person":
        return letter or char in " .'’-"
    if kind == "text":
        return letter or char.isnumeric() or unicodedata.category(char).startswith("S") or unicodedata.category(char) == "Pd" or char in " .,;:'’\"“”&()[]/#%+_=°ºª·′″"
    if kind == "phone":
        return char in "0123456789+()-" or char.isspace()
    if kind == "document":
        return (char.isascii() and char.isalnum()) or char == "-" or char.isspace()
    if kind == "username":
        return (char.isascii() and char.isalnum()) or char in "._-"
    return True


def validate(values: dict[str, object]) -> list[str]:
    """Valida antes de escribir; los opcionales vacíos permanecen válidos."""
    issues = []
    for label, value in values.items():
        rule = rule_for(label)
        if not rule:
            continue
        if "num" in rule:
            if rule.get("optional_number") and (value is None or value == ""):
                continue
            try:
                number = float(value)
                limits = rule["num"]
                valid = math.isfinite(number)
                valid &= not limits.get("gt0") or number > 0
                valid &= "min" not in limits or number >= limits["min"]
                valid &= "max" not in limits or number <= limits["max"]
            except (TypeError, ValueError):
                valid = False
            if not valid:
                limits = rule["num"]
                condition = "mayor que 0" if limits.get("gt0") else f"como mínimo {limits.get('min', 0)}"
                if "max" in limits:
                    condition += f" y como máximo {limits['max']:g}"
                issues.append(f"{label}: escribe un número finito {condition}.")
            continue
        text = str(value or "").strip()
        if not text:
            if rule.get("required"):
                issues.append(f"{label}: completa este campo obligatorio.")
            continue
        if len(text) < rule.get("min", 0):
            issues.append(f"{label}: usa al menos {rule['min']} caracteres.")
        if len(text) > rule.get("max", float("inf")):
            issues.append(f"{label}: el máximo es {rule['max']} caracteres.")
        kind = rule.get("kind", "")
        invalid = list(dict.fromkeys(ch for ch in text if not _allowed(ch, kind)))
        if invalid:
            issues.append(f"{label}: revisa estos caracteres: {' '.join(invalid)}.")
        if rule.get("digits"):
            count = len(re.sub(r"[^0-9]", "", text))
            if not rule["digits"][0] <= count <= rule["digits"][1]:
                issues.append(f"{label}: utiliza entre 7 y 15 dígitos, incluyendo el código de país.")
        if rule.get("pattern") and not re.fullmatch(rule["pattern"], text):
            issues.append(f"{label}: {rule['pattern_msg']}.")
    return issues


def errors(issues: list[str]) -> bool:
    if issues:
        st.error("Revisa estos datos antes de guardar:\n\n" + "\n".join(f"- {issue}" for issue in issues))
    return bool(issues)


def header(title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="mrp-form-intro"><div class="mrp-form-title">{html.escape(title)}</div>'
        f'<div class="mrp-form-description">{html.escape(description)}</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Completa los campos indicados. Los que dicen «opcional» pueden quedar vacíos.")


def section(title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="mrp-form-section"><strong>{html.escape(title)}</strong>'
        f'<span>{html.escape(description)}</span></div>',
        unsafe_allow_html=True,
    )
