"""Moneda, tipo de cambio, IGV y condición de pago de las órdenes de compra.

Cada orden guarda su moneda (los precios del catálogo del proveedor se toman tal cual en esa moneda), el tipo de
cambio a soles, cómo se trata el IGV y la condición de pago. Los acumulados del sistema (dashboard, presupuesto de
obra) se calculan siempre en soles.

**IGV en el Perú:** la tasa es 18 % (16 % de IGV + 2 % del Impuesto de Promoción Municipal). Una factura muestra el
*valor de venta* (base imponible), el *IGV* y el *importe total*. Los precios del proveedor pueden venir sin IGV
(se suma 18 %) o ya con IGV (la base se obtiene dividiendo entre 1,18); también hay ventas exoneradas o inafectas.

El sistema **no cobra ni paga**: la condición de pago es solo información para tesorería."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

BASE = "PEN"
CURRENCIES = {"PEN": "S/", "USD": "US$"}
CURRENCY_NAMES = {"PEN": "Soles (S/)", "USD": "Dólares (US$)"}
IGV = 0.18   # 16 % IGV + 2 % IPM

# Tratamiento del IGV en una orden: clave -> (texto para elegir, tasa, ¿los precios ya lo incluyen?)
TAX_MODES = {
    "add": ("Los precios NO incluyen IGV: se suma 18 %", IGV, False),
    "included": ("Los precios YA incluyen IGV (18 %)", IGV, True),
    "none": ("Sin IGV (operación exonerada o inafecta)", 0.0, False),
}
PAYMENT_TERMS = ["Contado", "Contra entrega", "Crédito 7 días", "Crédito 15 días", "Crédito 30 días", "Crédito 45 días", "Crédito 60 días"]


def symbol(currency: str | None) -> str:
    return CURRENCIES.get(currency or BASE, currency or "")


def fmt(amount: float, currency: str | None = BASE) -> str:
    """«S/ 1,234.50»"""
    return f"{symbol(currency)} {float(amount):,.2f}"


def tax_mode(tax_rate: float | None, prices_include_tax: bool | None = False) -> str:
    """Clave de `TAX_MODES` que corresponde a una orden guardada."""
    if not float(tax_rate or 0):
        return "none"
    return "included" if prices_include_tax else "add"


def tax_from_mode(mode: str) -> tuple[float, bool]:
    """(tasa, ¿precios con IGV incluido?) de un tratamiento de IGV."""
    _, rate, include = TAX_MODES[mode]
    return rate, include


def credit_days(payment_terms: str | None) -> int | None:
    """Días de crédito de una condición de pago («Crédito 30 días» → 30); None si es contado, en cuotas o no se indicó."""
    if parse_plan(payment_terms):
        return None
    match = re.search(r"(\d+)\s*d", payment_terms or "")
    return int(match.group(1)) if match else None


def due_date(issued: str | date | None, payment_terms: str | None) -> date | None:
    """Fecha límite de pago a crédito: emisión + días de crédito (None si no hay crédito)."""
    plan = parse_plan(payment_terms)
    if plan and issued:
        schedule = payment_schedule(issued, 0, payment_terms)
        return schedule[-1]["due"] if schedule else None
    days = credit_days(payment_terms)
    if days is None or not issued:
        return None
    try:
        start = issued if isinstance(issued, date) else date.fromisoformat(str(issued)[:10])
    except ValueError:
        return None
    return start + timedelta(days=days)


def normalize_terms(terms: dict | None) -> dict:
    """Condiciones de una orden con valores seguros: moneda conocida, tipo de cambio > 0 (1 si es soles), IGV entre 0 y 1
    (y «precios con IGV incluido» solo si hay IGV) y condición de pago conocida. Lanza ValueError si algo no tiene sentido."""
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
    payment = (terms.get("payment_terms") or "").strip() or None
    if payment and payment not in PAYMENT_TERMS and parse_plan(payment) is None:
        raise ValueError(f"Condición de pago no válida: {payment}.")
    expected = terms.get("expected_date")
    return {
        "expected_date": str(expected)[:10] if expected else None, "currency": currency, "exchange_rate": rate, "tax_rate": tax,
        "prices_include_tax": bool(terms.get("prices_include_tax")) and tax > 0, "payment_terms": payment,
    }


def default_terms() -> dict:
    """Condiciones de una orden nueva: soles, IGV 18 % sumado a los precios, sin fecha ni condición de pago."""
    return normalize_terms({"tax_rate": IGV})


def is_default(terms: dict) -> bool:
    """¿Son las condiciones de siempre (soles, sin IGV, sin fecha ni condición de pago)? Entonces no hace falta guardar nada."""
    return (
        terms["currency"] == BASE and terms["tax_rate"] == 0 and not terms["expected_date"]
        and not terms.get("prices_include_tax") and not terms.get("payment_terms")
    )


def cents(value: float) -> float:
    """Redondea a céntimos «hacia arriba en el .5» (como se redondea una factura), no al par más cercano."""
    return math.floor(float(value) * 100 + 0.5 + 1e-9) / 100


def amounts(subtotal: float, tax_rate: float = 0.0, exchange_rate: float = 1.0, prices_include_tax: bool = False) -> dict:
    """Importes de una orden en su moneda y en soles. `subtotal` es la suma de cantidad × precio tal como se escribió.
    Devuelve `net` (valor de venta, sin IGV), `tax` (IGV), `total` (importe total) y sus equivalentes en soles
    (`subtotal_base` = valor de venta en soles, `total_base`)."""
    subtotal = float(subtotal or 0)
    rate_tax = float(tax_rate or 0)
    if prices_include_tax and rate_tax:
        total = cents(subtotal)
        net = cents(total / (1 + rate_tax))
        tax = cents(total - net)
    else:
        net = cents(subtotal)
        tax = cents(net * rate_tax)
        total = cents(net + tax)
    fx = float(exchange_rate or 1)
    return {"subtotal": subtotal, "net": net, "tax": tax, "total": total, "subtotal_base": net * fx, "total_base": total * fx}


def add_amounts(orders):
    """Agrega a una tabla de órdenes (con `subtotal`, `tax_rate`, `exchange_rate` y `prices_include_tax`) las columnas
    `net`, `tax`, `total`, `subtotal_base` (valor de venta en soles) y `total_base`. Sin filas, solo crea las columnas."""
    import pandas as pd

    df = orders.copy()
    for col, default in (("subtotal", 0.0), ("tax_rate", 0.0), ("exchange_rate", 1.0)):
        df[col] = pd.to_numeric(df[col] if col in df.columns else default, errors="coerce").fillna(default)
    include = (df["prices_include_tax"] if "prices_include_tax" in df.columns else pd.Series(False, index=df.index)).map(lambda v: bool(v) and v == v)
    df["prices_include_tax"] = include.astype(bool)
    df["exchange_rate"] = df["exchange_rate"].where(df["exchange_rate"] > 0, 1.0)
    inclusive = df["prices_include_tax"] & (df["tax_rate"] > 0)

    def half_up(series):
        return ((series * 100 + 0.5 + 1e-9) // 1) / 100   # a céntimos, el .5 hacia arriba

    net_added = half_up(df["subtotal"])
    tax_added = half_up(net_added * df["tax_rate"])
    total_inc = half_up(df["subtotal"])
    net_inc = half_up(total_inc / (1 + df["tax_rate"]))
    df["net"] = net_added.where(~inclusive, net_inc)
    df["total"] = (net_added + tax_added).where(~inclusive, total_inc)
    df["tax"] = df["total"] - df["net"]
    df["subtotal_base"] = df["net"] * df["exchange_rate"]
    df["total_base"] = df["total"] * df["exchange_rate"]
    return df


# ---------------------------------------------------------------------------------------------------------------------
# Plan de pagos en cuotas (informativo: el sistema no cobra ni paga, solo calcula cuánto y cuándo)
# ---------------------------------------------------------------------------------------------------------------------
INSTALLMENT_EVERY = {"mensuales": "cada mes", "quincenales": "cada 15 días", "semanales": "cada 7 días"}
FIRST_DUE_DAYS = [0, 7, 15, 30, 45, 60]
_PLAN = re.compile(r"^En (\d{1,2}) cuotas (mensuales|quincenales|semanales)(?: · 1\.ª a los (\d{1,3}) días)?(?: · inicial (\d{1,2}) ?%)?$")


def installment_terms(count: int, every: str = "mensuales", first_days: int = 30, initial_pct: int = 0) -> str:
    """Condición de pago en cuotas como texto: «En 3 cuotas mensuales · 1.ª a los 30 días · inicial 20 %»."""
    if not 2 <= int(count) <= 24 or every not in INSTALLMENT_EVERY or not 0 <= int(first_days) <= 365 or not 0 <= int(initial_pct) <= 90:
        raise ValueError("El plan de cuotas no es válido: de 2 a 24 cuotas, periodicidad conocida, inicial de 0 a 90 %.")
    text = f"En {int(count)} cuotas {every}"
    if int(first_days):
        text += f" · 1.ª a los {int(first_days)} días"
    if int(initial_pct):
        text += f" · inicial {int(initial_pct)} %"
    return text


def parse_plan(terms: str | None) -> dict | None:
    """Los datos de una condición de pago en cuotas ({count, every, first_days, initial_pct}); None si no es un plan de cuotas."""
    match = _PLAN.match((terms or "").strip())
    if not match:
        return None
    count, every, first_days, initial = int(match.group(1)), match.group(2), int(match.group(3) or 0), int(match.group(4) or 0)
    if not 2 <= count <= 24 or initial > 90:
        return None
    return {"count": count, "every": every, "first_days": first_days, "initial_pct": initial}


def _add_months(start: date, months: int) -> date:
    year, month = divmod(start.month - 1 + months, 12)
    year, month = start.year + year, month + 1
    last = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(start.day, last))


def _as_date(issued) -> date | None:
    if not issued:
        return None
    if isinstance(issued, datetime):
        return issued.date()
    if isinstance(issued, date):
        return issued
    try:
        return date.fromisoformat(str(issued)[:10])
    except ValueError:
        return None


def payment_schedule(issued, total: float, terms: str | None) -> list[dict]:
    """Cuánto y cuándo hay que pagar según la condición pactada: [{n, of, label, due, amount}].

    Contado y contra entrega: un pago el día de la emisión; crédito a N días: un pago único; en cuotas: la inicial (si hay) el día de
    la emisión y luego las cuotas iguales (la última absorbe el redondeo). Es solo información para tesorería."""
    start, text = _as_date(issued), (terms or "").strip()
    if start is None or not text:
        return []
    total = cents(total)
    plan = parse_plan(text)
    if plan:
        payments: list[tuple[str, date, float]] = []
        remaining = total
        if plan["initial_pct"]:
            initial = cents(total * plan["initial_pct"] / 100)
            payments.append((f"Inicial ({plan['initial_pct']} %)", start, initial))
            remaining = cents(total - initial)
        first = start + timedelta(days=plan["first_days"])
        base = cents(remaining / plan["count"])
        for k in range(plan["count"]):
            if plan["every"] == "mensuales":
                due = _add_months(first, k)
            else:
                due = first + timedelta(days=(15 if plan["every"] == "quincenales" else 7) * k)
            amount = base if k < plan["count"] - 1 else cents(remaining - base * (plan["count"] - 1))
            payments.append((f"Cuota {k + 1} de {plan['count']}" if not plan["initial_pct"] else f"Cuota {k + 1}", due, amount))
        count = len(payments)
        return [{"n": i + 1, "of": count, "label": label, "due": due, "amount": amount} for i, (label, due, amount) in enumerate(payments)]
    days = credit_days(text)
    if days is not None:
        return [{"n": 1, "of": 1, "label": f"Pago a {days} días", "due": start + timedelta(days=days), "amount": total}]
    if text in ("Contado", "Contra entrega"):
        return [{"n": 1, "of": 1, "label": f"Pago {text.lower()}", "due": start, "amount": total}]
    return []
