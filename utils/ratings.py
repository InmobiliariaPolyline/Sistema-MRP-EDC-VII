"""Calificación de proveedores según cómo cumplieron sus pedidos.

Dos medidas, calculadas solo con lo que ya registra el sistema:

* **Entrega a tiempo:** de las órdenes con fecha prometida, cuántas se completaron a más tardar ese día.
  Una orden aún abierta o parcial cuya fecha ya pasó cuenta como atrasada; si todavía no vence, no se evalúa.
* **Cantidades completas:** de lo pedido en órdenes recibidas (o parciales con más de 30 días), cuánto llegó.

La nota (0 a 100) pondera 60 % plazo y 40 % cantidades; si solo hay una de las dos medidas, usa esa."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from utils import clock

WEIGHT_TIME, WEIGHT_QTY = 0.6, 0.4
PARTIAL_GRACE_DAYS = 30
COLUMNS = [
    "supplier_id", "supplier_name", "orders", "timed", "on_time", "on_time_pct", "avg_delay_days",
    "fill_pct", "score", "label",
]


def _day(value) -> date | None:
    text = str(value or "")
    if not text or text in ("None", "nan", "NaT"):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def label(score: float | None) -> str:
    if score is None:
        return "Sin historial"
    if score >= 90:
        return "Excelente"
    if score >= 75:
        return "Buena"
    if score >= 50:
        return "Regular"
    return "Baja"


def rate_suppliers(orders: pd.DataFrame, items: pd.DataFrame, receipts: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Una fila por proveedor con órdenes (sin contar las canceladas). Ver el docstring del módulo."""
    today = today or clock.today()
    if orders is None or orders.empty:
        return pd.DataFrame(columns=COLUMNS)
    last_receipt: dict[str, date] = {}
    if receipts is not None and not receipts.empty:
        for row in receipts.to_dict("records"):
            moment = _day(row.get("received_at"))
            if moment and (row["order_id"] not in last_receipt or moment > last_receipt[row["order_id"]]):
                last_receipt[row["order_id"]] = moment
    totals: dict[str, dict[str, float]] = {}
    if items is not None and not items.empty:
        for row in items.to_dict("records"):
            entry = totals.setdefault(row["order_id"], {"ordered": 0.0, "received": 0.0})
            entry["ordered"] += float(row.get("quantity") or 0)
            entry["received"] += float(row.get("received_qty") or 0)

    stats: dict[str, dict] = {}
    for order in orders[orders["status"] != "cancelada"].to_dict("records"):
        supplier_id = order.get("supplier_id")
        if not supplier_id:
            continue
        s = stats.setdefault(
            supplier_id,
            {"name": order.get("supplier_name"), "orders": 0, "timed": 0, "on_time": 0, "delays": [], "ordered": 0.0, "received": 0.0},
        )
        s["orders"] += 1
        status = order["status"]
        expected = _day(order.get("expected_date"))
        if expected:
            if status == "recibida":
                done = last_receipt.get(order["id"])
                if done:
                    s["timed"] += 1
                    if done <= expected:
                        s["on_time"] += 1
                    else:
                        s["delays"].append((done - expected).days)
            elif today > expected:  # pendiente, enviada o parcial y ya venció
                s["timed"] += 1
                s["delays"].append((today - expected).days)
        created = _day(order.get("created_at"))
        old_partial = status == "parcial" and created is not None and (today - created).days > PARTIAL_GRACE_DAYS
        if (status == "recibida" or old_partial) and order["id"] in totals:
            s["ordered"] += totals[order["id"]]["ordered"]
            s["received"] += totals[order["id"]]["received"]

    rows = []
    for supplier_id, s in stats.items():
        on_time_pct = s["on_time"] / s["timed"] * 100 if s["timed"] else None
        fill_pct = min(s["received"] / s["ordered"] * 100, 100.0) if s["ordered"] else None
        parts = [(WEIGHT_TIME, on_time_pct), (WEIGHT_QTY, fill_pct)]
        parts = [(w, v) for w, v in parts if v is not None]
        score = sum(w * v for w, v in parts) / sum(w for w, _ in parts) if parts else None
        rows.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": s["name"],
                "orders": s["orders"],
                "timed": s["timed"],
                "on_time": s["on_time"],
                "on_time_pct": on_time_pct,
                "avg_delay_days": sum(s["delays"]) / len(s["delays"]) if s["delays"] else None,
                "fill_pct": fill_pct,
                "score": score,
                "label": label(score),
            }
        )
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df.sort_values(["score", "supplier_name"], ascending=[False, True], na_position="last").reset_index(drop=True)
