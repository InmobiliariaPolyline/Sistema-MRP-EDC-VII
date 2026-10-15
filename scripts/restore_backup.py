"""Restaura un respaldo (ZIP de scripts/backup.py o de la pantalla Respaldo) en Supabase.

Uso:
    python scripts/restore_backup.py ruta/al/respaldo.zip [--password CLAVE] [--yes]

- Carga las tablas en orden de dependencia con `upsert` por `id`: se puede repetir sin duplicar y
  NO borra filas que hoy existan y no estén en el respaldo.
- Pensado para una base vacía o para recuperar datos borrados. Necesita SUPABASE_SERVICE_KEY.
- Antes de escribir muestra qué va a cargar y pide confirmación (salvo --yes)."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):  # consola de Windows (cp1252): que no falle con tildes ni símbolos
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT))

from db import repository as repo  # noqa: E402
from utils.backup import rows_from_zip  # noqa: E402

CHUNK = 400


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zip_path")
    parser.add_argument("--password", default=None)
    parser.add_argument("--yes", action="store_true", help="no pedir confirmación")
    args = parser.parse_args()

    if repo.USING_LOCAL:
        print("ERROR: la restauración es para Supabase; configura SUPABASE_URL y SUPABASE_SERVICE_KEY.")
        return 2
    manifest, tables = rows_from_zip(Path(args.zip_path).read_bytes(), args.password)
    print(f"Respaldo del {manifest['generated_at']} (app {manifest.get('app_version') or '?'}):")
    for name, rows in tables.items():
        print(f"  {name:22s} {len(rows):6d} filas")
    if not args.yes and input("¿Cargar estas filas en Supabase? (escribe SI) ").strip().upper() != "SI":
        print("Cancelado.")
        return 1

    client = repo.get_client()
    for name in repo.BACKUP_TABLES:  # orden de dependencia
        rows = tables.get(name, [])
        for start in range(0, len(rows), CHUNK):
            client.table(name).upsert(rows[start:start + CHUNK], on_conflict="id").execute()
        print(f"  restaurada {name} ({len(rows)})")
    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
