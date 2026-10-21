"""Ubicación de obras sin API key.

Nominatim (OpenStreetMap) solo conoce el *eje de la calle* en muchas zonas
(sin números de puerta), así que una dirección como «Av. Las Lomas 1649» cae
a ~1 km del punto real. Para dar exactitud hay dos caminos:

- `parse_coordinates`: acepta coordenadas («-12.00989, -76.98364») o un enlace
  de Google Maps (largo, con `@lat,lng` / `!3d..!4d..`, o corto `maps.app.goo.gl`),
  y devuelve el punto exacto que marcó la persona en Google Maps.
- `search_address`: varios candidatos (OpenStreetMap restringido a Perú, con variantes de la
  dirección y Photon de respaldo), sin duplicados, para que se elija el correcto."""
from __future__ import annotations

import math
import re
import time
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


_PHOTON_URL = "https://photon.komoot.io/api/"
_COUNTRY = "pe"
_LIMA = (-12.0464, -77.0428)                       # centro de Lima: da prioridad a los resultados cercanos cuando la dirección es ambigua
_THROTTLE = 1.05                                   # el servidor público de Nominatim pide como máximo 1 consulta por segundo
_last_nominatim = 0.0
_cache: dict[str, list[dict]] = {}

# abreviaturas de direcciones peruanas → como las escribe OpenStreetMap
_ABBREVIATIONS = [
    (r"\bav\.?(?=\s)", "Avenida"), (r"\bjr\.?(?=\s)", "Jirón"), (r"\bcdra\.?(?=\s)", "cuadra"), (r"\burb\.?(?=\s)", "Urbanización"),
    (r"\bpsje\.?(?=\s)", "Pasaje"), (r"\bmz\.?(?=\s)", "Manzana"), (r"\bcl\.?(?=\s)", "Calle"), (r"\bpje\.?(?=\s)", "Pasaje"),
    (r"\bsta\.?(?=\s)", "Santa"), (r"\bsto\.?(?=\s)", "Santo"), (r"\bgral\.?(?=\s)", "General"), (r"\bcrl\.?(?=\s)", "Coronel"),
]


# lugares conocidos que OpenStreetMap llama distinto de como los escribe la gente
_ALIASES = [
    (r"\bplaza de armas(?=,?\s*(?:de\s+)?lima\b)", "Plaza Mayor"),
    (r"\bplaza de armas(?=,?\s*(?:de\s+)?(?:cusco|cuzco)\b)", "Plaza de Armas"),
    (r"\baeropuerto jorge ch[aá]vez\b", "Aeropuerto Internacional Jorge Chávez"),
]
_OTHER_CITIES = r"\b(cusco|cuzco|arequipa|trujillo|piura|chiclayo|iquitos|huancayo|tacna|ica|puno|cajamarca|pucallpa|ayacucho|huaraz|tarapoto)\b"


def _normalize_query(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return re.sub(r"\s*,\s*", ", ", text)


def _aliased(text: str) -> str | None:
    for pattern, replacement in _ALIASES:
        changed = re.sub(pattern, replacement, text, flags=re.I)
        if changed != text:
            return changed
    return None


def query_variants(query: str) -> list[str]:
    """Formas de escribir la misma dirección, de la más específica a la más general. Nominatim a veces no encuentra una dirección
    larga pero sí la misma sin el nombre del local, sin el número de puerta o solo con la calle y el distrito."""
    base = _normalize_query(query)
    parts = [p.strip() for p in base.split(",") if p.strip()]
    variants = [base]
    alias = _aliased(base)
    if alias:
        variants.insert(0, alias)
    if len(parts) >= 2:
        variants.append(", ".join([parts[0]] + parts[-1:]))                       # nombre del lugar + distrito
        variants.append(", ".join(parts[1:]))                                     # sin el nombre del local
    joined = " ".join(parts)
    no_number = re.sub(r"\b\d{1,5}[a-zA-Z]?\b", "", joined)
    if no_number.strip() != joined.strip():
        variants.append(re.sub(r"\s+", " ", no_number).strip())                    # solo calle y distrito (cae sobre la vía)
    if not re.search(r"\b(per[uú]|lima|cusco|cuzco|arequipa|trujillo|piura|chiclayo|iquitos|huancayo|tacna|callao)\b", base, flags=re.I):
        variants.append(f"{base}, Lima, Perú")                                    # sin ciudad escrita: se asume Lima
    seen, out = set(), []
    for variant in variants:
        key = variant.lower()
        if variant and key not in seen:
            seen.add(key)
            out.append(variant)
    return out


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _nominatim(query: str, limit: int) -> list[dict]:
    global _last_nominatim
    wait = _THROTTLE - (time.monotonic() - _last_nominatim)
    if wait > 0:
        time.sleep(wait)
    _last_nominatim = time.monotonic()
    res = requests.get(
        _NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": limit, "addressdetails": 0, "accept-language": "es", "countrycodes": _COUNTRY},
        headers=_HEADERS, timeout=8,
    )
    res.raise_for_status()
    out = []
    for item in res.json():
        try:
            out.append({"lat": float(item["lat"]), "lon": float(item["lon"]), "display_name": item.get("display_name", query), "source": "OpenStreetMap"})
        except (KeyError, ValueError):
            continue
    return out


def _photon(query: str, limit: int) -> list[dict]:
    """Photon (también con datos de OpenStreetMap, tolera errores de escritura y busca por cercanía)."""
    res = requests.get(
        _PHOTON_URL, params={"q": query, "limit": limit, "lat": _LIMA[0], "lon": _LIMA[1], "lang": "default"}, headers=_HEADERS, timeout=8,
    )
    res.raise_for_status()
    out = []
    for feature in res.json().get("features", []):
        props = feature.get("properties", {})
        if str(props.get("countrycode", "")).lower() not in ("", _COUNTRY):
            continue
        try:
            lon, lat = feature["geometry"]["coordinates"][:2]
        except (KeyError, ValueError, TypeError):
            continue
        street = " ".join(x for x in (props.get("street"), props.get("housenumber")) if x)
        label = ", ".join(x for x in (props.get("name"), street, props.get("district") or props.get("suburb"), props.get("city"), props.get("state"), props.get("country")) if x)
        out.append({"lat": float(lat), "lon": float(lon), "display_name": label or query, "source": "Photon"})
    return out


def _rank(query: str, candidates: list[dict]) -> list[dict]:
    """Reordena (sin descartar nada): primero los candidatos cuya dirección trae el número de puerta que se escribió y, si la búsqueda
    no nombra otra ciudad del Perú, los que están en el área de Lima. Dentro de cada grupo se respeta el orden del buscador."""
    numbers = re.findall(r"(?<![\w-])(\d{2,5})(?![\w-])", query)
    near_lima = not re.search(_OTHER_CITIES, query, flags=re.I)

    def key(candidate: dict) -> tuple[int, int]:
        label = candidate["display_name"]
        has_number = any(re.search(rf"(?<![\w-]){n}(?![\w-])", label) for n in numbers)
        in_lima = _distance_m(candidate["lat"], candidate["lon"], *_LIMA) <= 40000
        return (0 if has_number else 1, 0 if (in_lima or not near_lima) else 1)

    return sorted(candidates, key=key)


def search_address(query: str, limit: int = 5) -> list[dict]:
    """Candidatos para una dirección (lista vacía si no hay o si la búsqueda falla). Cada uno: {"lat", "lon", "display_name", "source"}.

    Prueba primero OpenStreetMap restringido a Perú, con variantes de la misma dirección (abreviaturas expandidas, sin el nombre del
    local, sin el número de puerta); si con todas no hay nada o no hay ningún punto cercano a un número de puerta, completa con Photon.
    Los resultados se recuerdan para no repetir consultas."""
    query = re.sub(r"\s+", " ", (query or "").strip())
    if not query:
        return []
    if query.lower() in _cache:
        return _cache[query.lower()][:limit]

    candidates: list[dict] = []

    def add(items: list[dict]) -> None:
        for item in items:
            if any(abs(item["lat"] - c["lat"]) < 0.001 and abs(item["lon"] - c["lon"]) < 0.001 for c in candidates):
                continue     # el mismo lugar (a menos de ~100 m) no se repite
            candidates.append(item)

    failed = False
    for variant in query_variants(query)[:3]:
        try:
            add(_nominatim(variant, limit))
        except Exception:
            failed = True
            break
        if candidates:
            break
    if len(candidates) < 2:                              # poco o nada: se completa con el segundo buscador
        for variant in query_variants(query)[:2]:
            try:
                add(_photon(variant, limit))
            except Exception:
                break
            if len(candidates) >= 2:
                break
    candidates = _rank(query, candidates)
    if candidates or not failed:
        _cache[query.lower()] = candidates
    return candidates[:limit]


def google_maps_search_url(address: str = "", coords: tuple[float, float] | None = None) -> str:
    """Enlace a Google Maps. Con coordenadas abre exactamente ese punto; si no,
    busca la dirección escrita."""
    if coords:
        return f"https://www.google.com/maps/search/?api=1&query={coords[0]:.7f},{coords[1]:.7f}"
    return f"https://www.google.com/maps/search/?api=1&query={quote(address)}"
