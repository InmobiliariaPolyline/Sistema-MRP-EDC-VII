"""Cambios de un registro (antes → después) para el historial de auditoría."""
from __future__ import annotations

import json
from datetime import date, datetime


def fmt(value) -> str | None:
    """Valor legible de un dato (None si está vacío): números sin ceros de más, Sí/No, fechas ISO cortas."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (int, float)):
        return f"{float(value):g}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    text = str(value).strip()
    return text or None


def diff(before: dict, after: dict, labels: dict[str, str]) -> list[dict]:
    """Lo que cambió entre dos versiones de un registro. `labels`: {campo: nombre legible}; solo se comparan esos campos.
    Devuelve [{"field", "before", "after"}] (valores como texto, None = vacío)."""
    changes = []
    for key, label in labels.items():
        old, new = fmt(before.get(key)), fmt(after.get(key))
        if old != new:
            try:  # 10 y 10.0 son lo mismo
                if old is not None and new is not None and float(old) == float(new):
                    continue
            except ValueError:
                pass
            changes.append({"field": label, "before": old, "after": new})
    return changes


def diff_lines(before: list[dict], after: list[dict], key: str = "material_name", field: str = "quantity") -> list[dict]:
    """Cambios entre las líneas de una orden: cantidad modificada, líneas nuevas y líneas quitadas, por nombre de material."""
    old = {str(line[key]): line for line in before}
    new = {str(line[key]): line for line in after}
    changes = []
    for name in old.keys() | new.keys():
        was, now = old.get(name), new.get(name)
        if was and now:
            if fmt(was.get(field)) != fmt(now.get(field)):
                changes.append({"field": f"{name} (cantidad)", "before": fmt(was.get(field)), "after": fmt(now.get(field))})
        elif now:
            changes.append({"field": f"{name} (línea nueva)", "before": None, "after": fmt(now.get(field))})
        else:
            changes.append({"field": f"{name} (línea quitada)", "before": fmt(was.get(field)), "after": None})
    return sorted(changes, key=lambda c: c["field"])


def describe(changes: list[dict], limit: int = 6) -> str:
    """Resumen de una línea: «precio: 10 → 12; disponible: No → Sí»."""
    parts = [f"{c['field']}: {c['before'] if c['before'] is not None else '—'} → {c['after'] if c['after'] is not None else '—'}" for c in changes[:limit]]
    if len(changes) > limit:
        parts.append(f"y {len(changes) - limit} más")
    return "; ".join(parts)


def to_json(changes: list[dict] | None) -> str | None:
    return json.dumps(changes, ensure_ascii=False) if changes else None


def from_json(value) -> list[dict]:
    """Lista de cambios a partir de lo guardado (texto JSON, lista o vacío)."""
    if value is None or (isinstance(value, float) and value != value):
        return []
    if isinstance(value, list):
        return value
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []
