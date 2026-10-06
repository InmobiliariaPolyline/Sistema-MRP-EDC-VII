"""Formato relativo de fechas ("hace 5 min", "hace 2 h", "hace 3 d")."""
from __future__ import annotations

from datetime import datetime


def time_ago(value: str | None) -> str:
    if not value:
        return ""
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        seconds = max((now - dt).total_seconds(), 0)
    except (ValueError, TypeError):
        return ""

    if seconds < 60:
        return "hace un momento"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"hace {minutes} min"
    hours = int(minutes // 60)
    if hours < 24:
        return f"hace {hours} h"
    days = int(hours // 24)
    if days < 30:
        return f"hace {days} d"
    months = int(days // 30)
    return f"hace {months} mes(es)"


def age_days(value: str | None) -> int:
    """Días enteros transcurridos desde una fecha ISO (0 si no se puede leer)."""
    if not value:
        return 0
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return max((now - dt).days, 0)
    except (ValueError, TypeError):
        return 0
