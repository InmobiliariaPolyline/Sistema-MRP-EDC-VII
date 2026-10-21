"""Banco de pruebas del buscador de direcciones: lo compara con puntos conocidos del Perú y dice cuántos acierta.

Uso:
    python scripts/probar_direcciones.py

Los puntos de referencia son lugares muy conocidos con sus coordenadas de memoria (por eso cada uno lleva una tolerancia en metros);
sirven para comparar versiones del buscador. Para afinarlo con tus propias obras, agrega a CASES la dirección tal como la escribes y
las coordenadas que te da Google Maps al marcar ese punto. Usa internet y respeta 1 consulta por segundo: tarda cerca de un minuto."""
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import geocode  # noqa: E402

# (consulta como la escribiría una persona, latitud y longitud de referencia, tolerancia en metros)
CASES = [
    ("Plaza de Armas, Lima", -12.04635, -77.03055, 400),
    ("Jockey Plaza, Av. Javier Prado Este 4200, Santiago de Surco", -12.0846, -76.9753, 500),
    ("Larcomar, Malecon de la Reserva 610, Miraflores", -12.1316, -77.0301, 400),
    ("Parque Kennedy, Miraflores", -12.1219, -77.0300, 400),
    ("Aeropuerto Internacional Jorge Chavez, Callao", -12.0219, -77.1143, 1500),
    ("Estadio Nacional, Av. Jose Diaz, Lima", -12.0672, -77.0337, 500),
    ("Real Plaza Salaverry, Av. Salaverry 2370, Jesus Maria", -12.0897, -77.0526, 500),
    ("Ciudad Universitaria San Marcos, Av. Venezuela, Lima", -12.0568, -77.0845, 900),
    ("Hospital Rebagliati, Av. Edgardo Rebagliati 490, Jesus Maria", -12.0807, -77.0409, 500),
    ("Plaza San Martin, Lima", -12.0517, -77.0338, 400),
    ("Plaza de Armas, Cusco", -13.5167, -71.9786, 500),
    ("Plaza de Armas, Arequipa", -16.3989, -71.5369, 500),
    ("av larco 1301 miraflores", -12.1267, -77.0297, 700),          # número y abreviaturas, escrita rápido
    ("Av. Javier Prado Este 4200 Surco", -12.0846, -76.9753, 700),
    ("Parque de la Exposicion, Lima", -12.0578, -77.0368, 500),
    ("Museo de Arte de Lima, Paseo Colon 125", -12.0689, -77.0358, 400),
    ("Huaca Pucllana, Miraflores", -12.1105, -77.0336, 500),
    ("C.C. Plaza Norte, Av. Alfredo Mendiola 1400, Independencia", -11.9953, -77.0613, 600),
    ("Universidad de Lima, Av. Javier Prado Este 4600, Surco", -12.0856, -76.9714, 600),
    ("Mercado Central, Jr. Ayacucho, Lima", -12.0485, -77.0237, 500),
    ("Plaza de Armas, Trujillo", -8.1116, -79.0288, 500),
    ("Catedral de Lima", -12.0463, -77.0300, 400),
    ("miraflores parque kenedy", -12.1219, -77.0300, 600),      # con error de escritura
    ("Av. Alfredo Mendiola 1400", -11.9953, -77.0613, 1200),
]


def meters(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def run(label="buscador actual"):
    first_ok = in_list = 0
    rows = []
    for query, lat, lon, tol in CASES:
        found = geocode.search_address(query)
        time.sleep(1.2)
        dists = [meters(lat, lon, c["lat"], c["lon"]) for c in found]
        first = dists[0] if dists else None
        best = min(dists) if dists else None
        ok = first is not None and first <= tol
        okb = best is not None and best <= tol
        first_ok += ok
        in_list += okb
        rows.append((query[:48], len(found), "—" if first is None else round(first), "—" if best is None else round(best), tol, "OK" if ok else ("en la lista" if okb else "FALLA")))
    print(f"== {label}: primer resultado correcto {first_ok}/{len(CASES)} · correcto entre los candidatos {in_list}/{len(CASES)}")
    for row in rows:
        print("  {:<48} candidatos={} primero={} m mejor={} m tolerancia={} → {}".format(*row))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "buscador actual")
