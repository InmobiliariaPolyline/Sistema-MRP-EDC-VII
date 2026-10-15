"""Reglas de los documentos adjuntos (facturas, guías de remisión, vales firmados, fotos)."""
from __future__ import annotations

import re
import unicodedata
import uuid

MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
ENTITY_TYPES = {"orden": "orden de compra", "vale": "vale de salida", "conteo": "conteo de inventario"}
BUCKET = "adjuntos"


def validate(filename: str, size: int) -> tuple[str, str]:
    """Devuelve (nombre seguro, tipo de contenido) o lanza ValueError si el archivo no se acepta."""
    name = (filename or "").strip().replace("\\", "/").split("/")[-1]
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise ValueError("Solo se aceptan archivos PDF o imágenes (PNG, JPG, WEBP).")
    if size <= 0:
        raise ValueError("El archivo está vacío.")
    if size > MAX_BYTES:
        raise ValueError(f"El archivo pesa {size / 1024 / 1024:.1f} MB y el máximo es {MAX_BYTES // 1024 // 1024} MB.")
    stem = name[: -len(ext)]
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")[:80] or "documento"
    return stem + ext, ALLOWED[ext]


def storage_path(entity_type: str, entity_id: str, safe_name: str) -> str:
    """Ruta única dentro del depósito: orden/<id>/<uuid>-factura.pdf"""
    if entity_type not in ENTITY_TYPES:
        raise ValueError("Tipo de documento no válido.")
    return f"{entity_type}/{entity_id}/{uuid.uuid4().hex[:12]}-{safe_name}"


def human_size(size: int | float | None) -> str:
    size = float(size or 0)
    if size < 1024:
        return f"{size:.0f} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / 1024 / 1024:.1f} MB"
