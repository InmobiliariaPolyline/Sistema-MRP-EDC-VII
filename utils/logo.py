"""Logotipos de proveedores: se reducen y guardan como un texto (data URL) dentro del propio registro del proveedor.

Así no hace falta un servicio de archivos aparte: una imagen de ~160 px pesa pocos KB. Acepta PNG, JPG y WEBP (y GIF: se toma el
primer cuadro). Respeta la transparencia y la orientación de las fotos de celular."""
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_SIDE = 160
TYPES = ["png", "jpg", "jpeg", "webp"]


class LogoError(ValueError):
    """La imagen no sirve: el mensaje explica por qué, en lenguaje claro."""


def process(data: bytes) -> str:
    """Bytes de una imagen → data URL PNG reducida (máximo 160 × 160 px, proporción intacta)."""
    if not data:
        raise LogoError("El archivo está vacío.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise LogoError(f"La imagen pesa más de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Usa una más liviana.")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise LogoError("No se pudo leer la imagen. Usa un archivo PNG, JPG o WEBP.") from exc
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA")
    if min(image.size) < 16:
        raise LogoError("La imagen es demasiado pequeña (mínimo 16 px por lado).")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def to_bytes(data_url: str | None) -> bytes | None:
    """data URL → bytes de la imagen (para el PDF); None si no hay logotipo o está dañado."""
    if not data_url or not str(data_url).startswith("data:image/") or "," not in str(data_url):
        return None
    try:
        return base64.b64decode(str(data_url).split(",", 1)[1], validate=True)
    except (ValueError, base64.binascii.Error):
        return None


def is_valid(data_url) -> bool:
    return to_bytes(data_url) is not None
