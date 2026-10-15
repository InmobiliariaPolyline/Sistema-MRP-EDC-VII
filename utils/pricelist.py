"""Importación de la lista de precios de un proveedor desde Excel o CSV.

Los proveedores mandan sus precios en una hoja con, al menos, una columna con el
nombre del material y otra con el precio. Aquí se lee ese archivo (sin importar
el orden ni el nombre exacto de las columnas), se enlaza cada fila con un
material del catálogo y se devuelve qué se puede aplicar y qué no."""
from __future__ import annotations

import difflib
import io
import re
import unicodedata

import pandas as pd

NAME_HEADERS = ("material", "descripcion", "producto", "nombre", "articulo", "item", "insumo")
PRICE_HEADERS = ("precio", "price", "costo", "valor", "importe", "p.u", "pu")
CATEGORY_HEADERS = ("categoria", "rubro", "familia", "grupo")
RESULT_COLUMNS = ["fila", "archivo", "material_id", "material", "coincidencia", "precio", "precio_actual", "estado"]


def normalize(text) -> str:
    """Minúsculas, sin tildes ni signos, espacios simples: «Concreto f'c=210» ~ «concreto f c 210»."""
    text = unicodedata.normalize("NFD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _find_column(columns: list[str], keywords: tuple[str, ...]) -> str | None:
    for col in columns:
        n = normalize(col)
        if any(n == k or n.startswith(k) or k in n.split() for k in keywords):
            return col
    return None


def parse_price(value) -> float | None:
    """Acepta 12.5, '12,50', 'S/ 1,250.90', '1.250,90'. None si no es un precio válido (> 0)."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = re.sub(r"[^\d.,]", "", str(value))
    if not text:
        return None
    if "," in text and "." in text:  # el último separador es el decimal
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = head.replace(",", "") + ("." + tail if len(tail) <= 2 else tail)
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number > 0 else None


def read_table(data: bytes, filename: str) -> pd.DataFrame:
    """Lee un .xlsx/.xls o .csv. Busca la fila de encabezados (la primera que tenga una
    columna de nombre y una de precio) para tolerar títulos encima de la tabla."""
    if filename.lower().endswith(".csv"):
        raw = pd.read_csv(io.BytesIO(data), header=None, dtype=object, sep=None, engine="python", encoding_errors="replace")
    else:
        raw = pd.read_excel(io.BytesIO(data), header=None, dtype=object)
    for index in range(min(len(raw), 30)):
        headers = [str(v) if v is not None and v == v else "" for v in raw.iloc[index].tolist()]
        if _find_column(headers, NAME_HEADERS) and _find_column(headers, PRICE_HEADERS):
            table = raw.iloc[index + 1:].copy()
            table.columns = [h or f"col{i}" for i, h in enumerate(headers)]
            return table.reset_index(drop=True)
    raise ValueError("No encontré las columnas «Material» y «Precio». Revisa los encabezados o descarga la plantilla.")


def match_rows(table: pd.DataFrame, catalog: pd.DataFrame, current_prices: dict[str, float] | None = None, cutoff: float = 0.9) -> pd.DataFrame:
    """Enlaza cada fila con un material del catálogo.

    Columnas del resultado: fila, archivo (nombre en el archivo), material_id, material (nombre en el
    catálogo), coincidencia (exacta | parecida | sin coincidencia), precio, precio_actual y estado
    (nuevo | cambia | igual | sin precio válido | sin coincidencia)."""
    current_prices = current_prices or {}
    columns = list(table.columns)
    name_col = _find_column(columns, NAME_HEADERS)
    price_col = _find_column(columns, PRICE_HEADERS)
    category_col = _find_column(columns, CATEGORY_HEADERS)
    by_name: dict[str, list[dict]] = {}
    for row in catalog.to_dict("records"):
        by_name.setdefault(normalize(row["name"]), []).append(row)
    names = list(by_name)

    out = []
    for position, row in enumerate(table.to_dict("records"), start=1):
        raw_name = row.get(name_col)
        if raw_name is None or (isinstance(raw_name, float) and raw_name != raw_name) or not str(raw_name).strip():
            continue
        key = normalize(raw_name)
        candidates = by_name.get(key)
        match_kind = "exacta"
        if not candidates:
            close = difflib.get_close_matches(key, names, n=1, cutoff=cutoff)
            candidates = by_name.get(close[0]) if close else None
            match_kind = "parecida"
        material = None
        if candidates:
            if len(candidates) > 1 and category_col:  # mismo nombre en varias categorías: desempata por categoría
                wanted = normalize(row.get(category_col))
                material = next((c for c in candidates if normalize(c["category"]) == wanted), candidates[0])
            else:
                material = candidates[0]
        price = parse_price(row.get(price_col))
        current = current_prices.get(material["id"]) if material else None
        if material is None:
            state, match_kind = "sin coincidencia", "sin coincidencia"
        elif price is None:
            state = "sin precio válido"
        elif current is None:
            state = "nuevo"
        elif abs(current - price) > 1e-9:
            state = "cambia"
        else:
            state = "igual"
        out.append(
            {
                "fila": position,
                "archivo": str(raw_name).strip(),
                "material_id": material["id"] if material else None,
                "material": material["name"] if material else None,
                "coincidencia": match_kind,
                "precio": price,
                "precio_actual": current,
                "estado": state,
            }
        )
    return pd.DataFrame(out, columns=RESULT_COLUMNS)


def template_bytes(catalog: pd.DataFrame, current_prices: dict[str, float] | None = None) -> bytes:
    """Plantilla Excel con todos los materiales del catálogo para llenar el precio."""
    current_prices = current_prices or {}
    frame = pd.DataFrame(
        {
            "Categoría": catalog["category"],
            "Material": catalog["name"],
            "Unidad": catalog["metric_label"],
            "Precio": [current_prices.get(i) for i in catalog["id"]],
        }
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Precios", index=False)
        sheet = writer.sheets["Precios"]
        for letter, width in zip("ABCD", (26, 56, 24, 14)):
            sheet.column_dimensions[letter].width = width
        sheet.freeze_panes = "A2"
    return buffer.getvalue()
