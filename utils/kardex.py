"""Kardex de un material: cada entrada y salida en orden cronológico con el saldo corrido."""
from __future__ import annotations

from typing import Callable

import pandas as pd
from utils import clock

def _text(value) -> str:
    """Texto de un dato opcional: vacío si falta (None o NaN)."""
    return "" if value is None or value != value else str(value)


COLUMNS = ["Fecha", "Tipo", "Documento", "Detalle", "Entrada", "Salida", "Saldo"]


def build(movements: pd.DataFrame, type_label: Callable[[str | None, str], str] | None = None) -> pd.DataFrame:
    """Kardex a partir de los movimientos de UN material tal como los devuelve `list_movements`
    (el más reciente primero). Devuelve las filas en orden cronológico, con `Saldo` acumulado."""
    if movements is None or movements.empty:
        return pd.DataFrame(columns=COLUMNS)
    label = type_label or (lambda movement_type, kind: movement_type or ("Entrada" if kind == "entrada" else "Salida"))
    rows, balance = [], 0.0
    for move in reversed(movements.to_dict("records")):
        quantity = float(move["quantity"])
        entry = quantity if move["kind"] == "entrada" else 0.0
        exit_ = quantity if move["kind"] == "salida" else 0.0
        balance += entry - exit_
        document = next((_text(move.get(k)) for k in ("voucher_code", "order_code", "count_code") if _text(move.get(k))), "")
        detail = " · ".join(_text(move.get(k)) for k in ("site_name", "stage", "requested_by", "note") if _text(move.get(k)))
        rows.append(
            {
                "Fecha": clock.local(move["created_at"]),
                "Tipo": label(move.get("movement_type") if _text(move.get("movement_type")) else None, move["kind"]),
                "Documento": document,
                "Detalle": detail,
                "Entrada": entry or None,
                "Salida": exit_ or None,
                "Saldo": balance,
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)
