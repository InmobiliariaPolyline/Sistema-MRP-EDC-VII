"""Ubicación de obras sin API key.

Nominatim (OpenStreetMap) solo conoce el *eje de la calle* en muchas zonas
(sin números de puerta), así que una dirección como «Av. Las Lomas 1649» cae
a ~1 km del punto real. Para dar exactitud hay dos caminos:

- `parse_coordinates`: acepta coordenadas («-12.00989, -76.98364») o un enlace
  de Google Maps (largo, con `@lat,lng` / `!3d..!4d..`, o corto `maps.app.goo.gl`),
  y devuelve el punto exacto que marcó la persona en Google Maps.
- `search_address`: varios candidatos de Nominatim (ya filtrados y sin
  duplicados) para que se elija el correcto, en vez de tomar a ciegas el primero."""
from __future__ import annotations

import re
from urllib.parse import quote, unquote

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "sistema-mrp-edc-vii/1.0 (uso interno)"}

_NUM = r"(-?\d{1,3}(?:\.\d+)?)"
_PATTERNS = [
    re.compile(rf"@{_NUM},{_NUM}"),  # centro del mapa: donde cae el pin al abrir un lugar buscado
    re.compile(rf"!3d{_NUM}!4d{_NUM}"),  # coordenadas del lugar dentro de los datos del enlace
    re.compile(rf"[?&](?:q|query|ll)={_NUM}(?:,|%2C){_NUM}"),
    re.compile(rf"^\s*{_NUM}\s*[,;\s]\s*{_NUM}\s*$"),  # «lat, lon» pegado tal cual
]


def _valid(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)


def parse_coordinates(text: str) -> dict | None:
    """Devuelve {"lat", "lon", "display_name"} si `text` son coordenadas o un
    enlace de Google Maps; None si no se reconoce."""
    text = (text or "").strip()
    if not text:
        return None
    if re.match(r"https?://(maps\.app\.goo\.gl|goo\.gl/maps|g\.co/kgs)", text):
        try:  # enlace corto: seguir la redirección hasta la URL larga
            text = requests.get(text, headers=_HEADERS, timeout=8, allow_redirects=True).url
        except Exception:
            return None
    decoded = unquote(text)
    for pattern in _PATTERNS:
        match = pattern.search(decoded)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if _valid(lat, lon):
                return {"lat": lat, "lon": lon, "display_name": f"Coordenadas {lat:.6f}, {lon:.6f}"}
    return None


def search_address(query: str, limit: int = 5) -> list[dict]:
    """Candidatos de Nominatim para una dirección (lista vacía si no hay o si
    la búsqueda falla). Cada uno: {"lat", "lon", "display_name"}."""
    query = re.sub(r"\s+", " ", (query or "").strip())
    if not query:
        return []
    try:
        res = requests.get(
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": limit, "addressdetails": 0, "accept-language": "es"},
            headers=_HEADERS,
            timeout=8,
        )
        res.raise_for_status()
        results = res.json()
    except Exception:
        return []

    candidates: list[dict] = []
    for item in results:
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
        except (KeyError, ValueError):
            continue
        # mismo lugar repetido (a menos de ~100 m): se descarta
        if any(abs(lat - c["lat"]) < 0.001 and abs(lon - c["lon"]) < 0.001 for c in candidates):
            continue
        candidates.append({"lat": lat, "lon": lon, "display_name": item.get("display_name", query)})
    return candidates


def geocode_address(query: str) -> dict | None:
    """Primer candidato de `search_address` (compatibilidad)."""
    found = search_address(query, limit=1)
    return found[0] if found else None


def google_maps_search_url(address: str = "", coords: tuple[float, float] | None = None) -> str:
    """Enlace a Google Maps. Con coordenadas abre exactamente ese punto; si no,
    busca la dirección escrita."""
    if coords:
        return f"https://www.google.com/maps/search/?api=1&query={coords[0]:.7f},{coords[1]:.7f}"
    return f"https://www.google.com/maps/search/?api=1&query={quote(address)}"
