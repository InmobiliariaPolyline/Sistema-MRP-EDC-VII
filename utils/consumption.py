"""Consumo de material por obra: lo despachado menos lo devuelto al almacén."""
from __future__ import annotations


def site_quantity(movement: dict) -> float:
    """Cuánto cuenta un movimiento en el consumo de una obra: los despachos suman y las
    devoluciones desde la obra restan. Cualquier otro movimiento (recepciones, mermas, conteos) no cuenta."""
    if not movement.get("project_site_id"):
        return 0.0
    quantity = float(movement.get("quantity") or 0)
    if movement.get("kind") == "salida" and movement.get("movement_type") != "devolucion_proveedor":
        return quantity
    if movement.get("kind") == "entrada" and movement.get("movement_type") == "devolucion":
        return -quantity
    return 0.0


def net_by_material(movements) -> dict[str, float]:
    """{material_id: despachado − devuelto} a partir de movimientos (lista de dicts o DataFrame)."""
    rows = movements.to_dict("records") if hasattr(movements, "to_dict") else movements
    totals: dict[str, float] = {}
    for row in rows:
        amount = site_quantity(row)
        if amount:
            totals[row["material_id"]] = totals.get(row["material_id"], 0.0) + amount
    return totals
