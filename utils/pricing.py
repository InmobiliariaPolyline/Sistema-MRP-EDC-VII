"""Vigencia de las cotizaciones: un precio de proveedor con meses sin actualizarse deja de ser confiable."""
from __future__ import annotations

from datetime import datetime

DEFAULT_MAX_AGE_DAYS = 90


def price_age_days(updated_at, now: datetime | None = None) -> int | None:
    """Días desde que se actualizó el precio, o None si no se sabe (precio cargado antes de llevar fecha)."""
    if updated_at is None or str(updated_at) in ("", "None", "nan", "NaT"):
        return None
    try:
        moment = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    current = now or (datetime.now(moment.tzinfo) if moment.tzinfo else datetime.now())
    return max((current - moment).days, 0)


def is_stale(updated_at, max_days: int = DEFAULT_MAX_AGE_DAYS, now: datetime | None = None) -> bool:
    """¿El precio superó su vigencia? Un precio sin fecha conocida no se marca como vencido."""
    age = price_age_days(updated_at, now)
    return age is not None and age > max_days


def describe(updated_at, max_days: int = DEFAULT_MAX_AGE_DAYS, now: datetime | None = None) -> str:
    """Texto corto para mostrar junto a un precio: «actualizado hace 12 d», «hace 130 d (vencido)»…"""
    age = price_age_days(updated_at, now)
    if age is None:
        return "sin fecha de actualización"
    if age == 0:
        return "actualizado hoy"
    text = f"hace {age} d" if age < 60 else f"hace {age // 30} meses"
    return f"{text} (vencido)" if age > max_days else f"actualizado {text}"
