"""Lectura/escritura de Excel para importar y exportar catálogos.

El importador es tolerante con archivos "reales" que no vienen limpios:
reconoce encabezados en español o inglés (p. ej. "Categoría"/"category"),
sin importar mayúsculas o acentos, y sabe saltarse filas decorativas
(títulos, notas) que vengan antes de la fila de encabezado real — como el
catálogo de referencia de materiales (501 materiales, 27 categorías) que
trae una fila de título y una de explicación antes de la tabla."""
from __future__ import annotations

import io
import unicodedata

import pandas as pd

# Nombre interno -> variantes de encabezado que lo identifican (ya
# normalizadas: minúsculas y sin acentos se comparan en _normalize).
MATERIAL_ALIASES: dict[str, set[str]] = {
    "category": {"category", "categoria"},
    "name": {"name", "material", "nombre"},
    "density": {"density", "densidad", "densidad (kg/m3)"},
    "metric_label": {"metric_label", "metrica", "metrica que usa"},
}
MATERIAL_REQUIRED = {"category", "name"}

SUPPLIER_ALIASES: dict[str, set[str]] = {
    "name": {"name", "nombre", "proveedor"},
    "contact_name": {"contact_name", "contacto", "persona de contacto"},
    "phone": {"phone", "telefono"},
    "email": {"email", "correo"},
    "notes": {"notes", "notas"},
}
SUPPLIER_REQUIRED = {"name"}

# Encabezados de exportación, iguales a los del catálogo de referencia de
# materiales (501 materiales / 27 categorías) para que el archivo que
# exporta la app se pueda reimportar sin ajustes, y viceversa.
MATERIAL_EXPORT_COLUMNS = {
    "category": "Categoría",
    "name": "Material",
    "density": "Densidad (kg/m³)",
    "metric_label": "Métrica que usa",
}


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def read_excel_upload(uploaded_file) -> pd.DataFrame:
    """Lee el archivo tal cual, sin asumir que la primera fila es el
    encabezado (eso lo resuelve `extract_columns` más adelante, ya que el
    encabezado real puede venir más abajo)."""
    return pd.read_excel(uploaded_file, header=None, dtype=str)


def _normalize(value: object) -> str:
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def extract_columns(raw_df: pd.DataFrame, aliases: dict[str, set[str]], required: set[str], max_scan: int = 10) -> pd.DataFrame:
    """Busca, entre las primeras `max_scan` filas, la que reconozca como
    encabezado (según `aliases`) y devuelve un DataFrame ya con las
    columnas internas (category/name/density/...), tomando los datos de
    las filas debajo de esa fila de encabezado.

    Si no encuentra ninguna fila reconocible, asume que la primera fila del
    archivo ya es el encabezado (compatibilidad con exportaciones previas)."""
    alias_to_field = {alias: field for field, names in aliases.items() for alias in names}

    header_row_idx = None
    header_map: dict[int, str] = {}
    for i in range(min(max_scan, len(raw_df))):
        mapped: dict[int, str] = {}
        for col_idx, value in raw_df.iloc[i].items():
            if pd.isna(value):
                continue
            field = alias_to_field.get(_normalize(value))
            if field and field not in mapped.values():
                mapped[col_idx] = field
        if required.issubset(set(mapped.values())):
            header_row_idx = i
            header_map = mapped
            break

    if header_row_idx is None:
        raise ValueError(
            "No se reconoció el encabezado del Excel. Verifica que traiga columnas como "
            f"{', '.join(sorted(required))}."
        )

    data = raw_df.iloc[header_row_idx + 1 :].reset_index(drop=True)
    result = pd.DataFrame({field: data[col_idx] for col_idx, field in header_map.items()})
    return result
