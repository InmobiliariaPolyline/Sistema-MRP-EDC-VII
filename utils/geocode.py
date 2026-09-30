"""Geocodificación de direcciones sin API key, vía Nominatim (OpenStreetMap).
Uso ligero (una obra a la vez, creada a mano), así que no hace falta cuenta
de Google Cloud ni facturación."""
from __future__ import annotations

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "sistema-mrp-edc-vii/1.0 (uso interno)"}


def geocode_address(query: str) -> dict | None:
    """Busca una dirección y devuelve {"lat": float, "lon": float,
    "display_name": str} del primer resultado, o None si no encontró nada
    o la búsqueda falló (sin conexión, límite de uso, etc.)."""
    query = (query or "").strip()
    if not query:
        return None
    try:
        res = requests.get(
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers=_HEADERS,
            timeout=8,
        )
        res.raise_for_status()
        results = res.json()
    except Exception:
        return None

    if not results:
        return None
    top = results[0]
    try:
        return {
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
            "display_name": top.get("display_name", query),
        }
    except (KeyError, ValueError):
        return None
