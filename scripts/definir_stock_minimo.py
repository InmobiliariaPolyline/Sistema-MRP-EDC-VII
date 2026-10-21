"""Asigna un stock mínimo a cada material del catálogo para que el sistema detecte la falta de material en el almacén.

Uso:
    python scripts/definir_stock_minimo.py              # muestra los valores que asignaría (no escribe)
    python scripts/definir_stock_minimo.py --execute    # los guarda de verdad

El mínimo se expresa en la primera unidad de la métrica del material (m³, m², kg, m o unidad). Se calcula como una reserva de
valor razonable para una obra pequeña o mediana dividida entre el precio de referencia: lo que se gasta mucho y es barato
(arena, varilla, ladrillo, placas) tiene un mínimo grande; lo caro o de uso puntual (maderas exóticas, metales especiales,
membranas) tiene uno pequeño. Son valores de partida: se ajustan después desde Inventario › Stock mínimo.
Escribe en la misma base que usa la app (Supabase si hay credenciales en .env, si no el SQLite local)."""
import argparse
import math
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

from db import repository as repo  # noqa: E402
from seed_proveedores import base_price  # noqa: E402
from utils.pricelist import normalize  # noqa: E402

# reserva de valor (S/) que conviene tener en el almacén por categoría
RESERVE = {
    "Acero y hierro": 9000, "Aceros e instalaciones": 3500, "Adhesivos y selladores": 2500, "Aislamiento": 2500,
    "Carpintería de puertas y ventanas": 4000, "Concreto": 9000, "Fachadas y revestimiento exterior": 3500, "Fibras de refuerzo": 1500,
    "Geosintéticos": 2500, "Madera": 4500, "Mampostería": 6000, "Materiales ignífugos y contrafuego": 1800, "Membranas textiles": 1500,
    "Metales no ferrosos": 1800, "Paisajismo y exteriores": 1500, "Paneles y compuestos": 3000, "Pavimentación vial": 6000,
    "Piedra natural": 3000, "Pisos técnicos y cielos rasos": 2500, "Pisos y revestimientos": 4000, "Plásticos y polímeros": 1800,
    "Prefabricados de concreto": 5000, "Suelos y áridos": 4500, "Techos y membranas": 3500, "Tuberías y conducciones": 3000,
    "Vidrio": 3000, "Yeso y placas": 4500,
}
# materiales de uso diario en obra: reserva mayor
COMMON = ("varilla", "mortero de cemento", "king kong", "pandereta", "cmu", "drywall", "arena", "grava", "piedra triturada", "piedra chancada",
          "concreto normal", "pvc presion", "pvc sanitario", "ceramica esmaltada", "porcelanato", "silicona", "contrachapado", "mdf", "tierra vegetal",
          "malla electrosoldada para concreto", "teja de arcilla", "vidrio float", "vidrio templado", "base granular", "sub-base")
# de uso puntual o muy caros: reserva menor
RARE = ("ebano", "palo de rosa", "wengue", "zebrano", "bubinga", "padauk", "amaranto", "guayacan", "inconel", "monel", "titanio", "maraging",
        "antibalas", "translucido", "aerogel", "etfe", "ptfe", "kevlar", "cobre", "aramida", "fotovoltaico", "solar", "ultra alto")


def minimum_for(category: str, name: str) -> int:
    reserve = RESERVE.get(category, 2500)
    text = normalize(name)
    if any(normalize(w) in text for w in COMMON):
        reserve *= 1.8
    if any(normalize(w) in text for w in RARE):
        reserve *= 0.35
    quantity = reserve / max(base_price(category, name), 0.05)
    if quantity >= 100:
        step = 50 if quantity >= 1000 else 10 if quantity >= 300 else 5
        return int(math.ceil(quantity / step) * step) if quantity < 5000 else 5000
    if quantity >= 10:
        return int(round(quantity / 5) * 5) or 5
    return max(2, int(round(quantity)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--execute", action="store_true", help="guardar de verdad")
    args = parser.parse_args()

    materials = repo.list_materials().to_dict("records")
    plan = [(m, minimum_for(m["category"], m["name"])) for m in materials]
    print(f"Base: {'SQLite local' if repo.USING_LOCAL else 'Supabase'} · {len(materials)} materiales\n")
    by_category: dict[str, list[int]] = {}
    for m, minimum in plan:
        by_category.setdefault(m["category"], []).append(minimum)
    for category, values in sorted(by_category.items()):
        print(f"  {category:<38}{len(values):>4} materiales · mínimos de {min(values)} a {max(values)}")
    print("\nEjemplos:")
    for m, minimum in plan[::37]:
        print(f"  {m['name'][:50]:<50} {minimum:>6}  ({m['metric_label'][:24]})")
    if not args.execute:
        print("\nNo se guardó nada. Para guardar: python scripts/definir_stock_minimo.py --execute")
        return 0

    done = 0
    for m, minimum in plan:
        if float(m.get("min_stock") or 0) != float(minimum):
            repo.set_min_stock(m["id"], minimum)
        done += 1
    print(f"\nStock mínimo definido en {done} materiales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
