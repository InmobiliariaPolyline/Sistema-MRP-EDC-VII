"""Genera un respaldo completo de la base en un ZIP (un CSV por tabla).

Uso:
    python scripts/backup.py                      # guarda backups/mrp_AAAAMMDD_HHMM.zip
    python scripts/backup.py --require-password   # exige BACKUP_PASSWORD (respaldo cifrado AES-256)
    python scripts/backup.py --out otra/carpeta

Lee la misma configuración que la app (.env o variables de entorno): SUPABASE_URL y
SUPABASE_SERVICE_KEY. Sin Supabase configurado respalda el SQLite local."""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):  # consola de Windows (cp1252): que no falle con tildes ni símbolos
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT))

from db import repository as repo  # noqa: E402
from core.version import APP_VERSION  # noqa: E402
from utils.backup import to_zip  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(ROOT / "backups"), help="carpeta de destino")
    parser.add_argument("--require-password", action="store_true", help="falla si no hay BACKUP_PASSWORD")
    args = parser.parse_args()

    password = os.environ.get("BACKUP_PASSWORD") or None
    if args.require_password and not password:
        print("ERROR: falta la variable BACKUP_PASSWORD (el respaldo incluye hashes de contraseñas y debe ir cifrado).")
        return 2

    tables = repo.dump_tables()
    data = to_zip(tables, password, APP_VERSION)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"mrp_{datetime.now():%Y%m%d_%H%M}.zip"
    target.write_bytes(data)
    rows = sum(len(df) for df in tables.values())
    print(f"Respaldo guardado en {target} · {len(tables)} tablas, {rows} filas, {'cifrado' if password else 'SIN cifrar'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
