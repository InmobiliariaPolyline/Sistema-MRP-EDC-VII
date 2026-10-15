"""Moneda, tipo de cambio e IGV de las órdenes de compra.

Cada orden guarda su moneda (los precios del catálogo del proveedor se toman tal cual en esa
moneda), el tipo de cambio a soles y la tasa de IGV (0 si los precios ya lo incluyen o no aplica).
Los acumulados del sistema (dashboard, presupuesto de obra) se calculan siempre en soles."""
from __future__ import annotations

BASE = "PEN"
CURRENCIES = {"PEN": "S/", "USD": "US$"}
CURRENCY_NAMES = {"PEN": "Soles (S/)", "USD": "Dólares (US$)"}
IGV = 0.18


def symbol(currency: str | None) -> str:
    return CURRENCIES.get(currency or BASE, currency or "")


def fmt(amount: float, currency: str | None = BASE) -> str:
    """«S/ 1,234.50»"""
    return f"{symbol(currency)} {float(amount):,.2f}"


def normalize_terms(terms: dict | None) -> dict:
    """Condiciones de una orden con valores seguros: moneda conocida, tipo de cambio > 0 (1 si es soles)
    e IGV entre 0 y 1. Lanza ValueError si algo no tiene sentido."""
    terms = dict(terms or {})
    currency = terms.get("currency") or BASE
    if currency not in CURRENCIES:
        raise ValueError(f"Moneda no válida: {currency}.")
    rate = 1.0 if currency == BASE else float(terms.get("exchange_rate") or 0)
    if rate <= 0:
        raise ValueError("Indica el tipo de cambio (mayor que 0) para una orden en dólares.")
    tax = float(terms.get("tax_rate") or 0)
    if not 0 <= tax <= 1:
        raise ValueError("El IGV debe estar entre 0 % y 100 %.")
    expected = terms.get("expected_date")
    return {"expected_date": str(expected)[:10] if expected else None, "currency": currency, "exchange_rate": rate, "tax_rate": tax}


def is_default(terms: dict) -> bool:
    """¿Son las condiciones de siempre (soles, sin IGV, sin fecha)? Entonces no hace falta guardar nada."""
    return terms["currency"] == BASE and terms["tax_rate"] == 0 and not terms["expected_date"]


def amounts(subtotal: float, tax_rate: float = 0.0, exchange_rate: float = 1.0) -> dict:
    """Subtotal, IGV y total en la moneda de la orden, y su equivalente en soles."""
    subtotal = float(subtotal or 0)
    tax = subtotal * float(tax_rate or 0)
    total = subtotal + tax
    rate = float(exchange_rate or 1)
    return {"subtotal": subtotal, "tax": tax, "total": total, "subtotal_base": subtotal * rate, "total_base": total * rate}


def add_amounts(orders):
    """Agrega a una tabla de órdenes (con `subtotal`, `tax_rate` y `exchange_rate`) las columnas
    `tax`, `total`, `subtotal_base` y `total_base`. Sin filas, solo crea las columnas."""
    import pandas as pd

    df = orders.copy()
    for col, default in (("subtotal", 0.0), ("tax_rate", 0.0), ("exchange_rate", 1.0)):
        df[col] = pd.to_numeric(df[col] if col in df.columns else default, errors="coerce").fillna(default)
    df["exchange_rate"] = df["exchange_rate"].where(df["exchange_rate"] > 0, 1.0)
    df["tax"] = df["subtotal"] * df["tax_rate"]
    df["total"] = df["subtotal"] + df["tax"]
    df["subtotal_base"] = df["subtotal"] * df["exchange_rate"]
    df["total_base"] = df["total"] * df["exchange_rate"]
    return df
