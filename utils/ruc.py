"""RUC del Perú (Registro Único de Contribuyentes, 11 dígitos): limpieza, validación con el dígito verificador de SUNAT y formato.

Los dos primeros dígitos indican el tipo de contribuyente: 10 persona natural (con DNI), 15 y 17 sujetos no domiciliados
o sucesiones, 20 persona jurídica (empresas). El último dígito es un verificador calculado con módulo 11."""
from __future__ import annotations

import re

WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
KINDS = {"10": "Persona natural", "15": "Sujeto no domiciliado", "17": "Sucesión o entidad", "20": "Persona jurídica"}


def clean(value) -> str:
    """Solo los dígitos (acepta espacios, guiones y puntos)."""
    return re.sub(r"\D", "", str(value or ""))


def check_digit(first_ten: str) -> int:
    total = sum(int(d) * w for d, w in zip(first_ten, WEIGHTS))
    digit = 11 - total % 11
    return {10: 0, 11: 1}.get(digit, digit)


def is_valid(value) -> bool:
    ruc = clean(value)
    return len(ruc) == 11 and ruc[:2] in KINDS and int(ruc[10]) == check_digit(ruc[:10])


def kind(value) -> str | None:
    ruc = clean(value)
    return KINDS.get(ruc[:2]) if len(ruc) == 11 else None


def issues(value, label: str = "RUC", required: bool = False) -> list[str]:
    """Problemas de un RUC escrito por el usuario (lista vacía = válido o vacío si no es obligatorio)."""
    ruc = clean(value)
    if not ruc:
        return [f"{label}: completa este campo obligatorio."] if required else []
    if len(ruc) != 11:
        return [f"{label}: debe tener 11 dígitos (tiene {len(ruc)})."]
    if ruc[:2] not in KINDS:
        return [f"{label}: debe empezar con 10, 15, 17 o 20."]
    if not is_valid(ruc):
        return [f"{label}: el dígito verificador no coincide; revisa que esté bien escrito."]
    return []

