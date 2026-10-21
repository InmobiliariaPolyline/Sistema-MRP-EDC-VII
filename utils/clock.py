"""Hora del sistema: siempre la de Perú (Lima, UTC−5, sin horario de verano).

El servidor (por ejemplo Streamlit Cloud) corre en UTC y la base guarda las marcas de tiempo en UTC, así que lo que se
muestra o se escribe en un documento pasa siempre por aquí: `now()` y `today()` para «ahora» y `local()` para convertir
una marca de tiempo guardada a la hora de Lima."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

LIMA = timezone(timedelta(hours=-5), "America/Lima")
UTC = timezone.utc


def now() -> datetime:
    """Fecha y hora actuales en Lima."""
    return datetime.now(LIMA)


def today() -> date:
    """Fecha de hoy en Lima (a las 23:00 de Lima ya no es «mañana» de UTC)."""
    return now().date()


def parse(value) -> datetime | None:
    """Una marca de tiempo guardada → `datetime` con zona. Sin zona se entiende UTC (así las guarda SQLite y Supabase)."""
    text = str(value or "").strip()
    if not text or text in ("None", "nan", "NaT"):
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def local(value, with_time: bool = True) -> str:
    """Marca de tiempo guardada → «2026-10-21 15:57» en hora de Lima (o solo «2026-10-21»).

    Un valor que ya es solo fecha («2026-10-21», p. ej. una fecha prometida) se devuelve igual: no tiene hora que convertir."""
    text = str(value or "").strip()
    if not text or text in ("None", "nan", "NaT"):
        return ""
    if len(text) <= 10:
        return text
    moment = parse(text)
    if moment is None:
        return text[:16].replace("T", " ") if with_time else text[:10]
    moment = moment.astimezone(LIMA)
    return f"{moment:%Y-%m-%d %H:%M}" if with_time else f"{moment:%Y-%m-%d}"
