"""Deja el sistema como nuevo: borra todo lo registrado con los formularios y el historial, y conserva el catálogo de materiales,
las cuentas de acceso y los datos de la empresa.

Uso:
    python scripts/clean_data.py              # solo muestra cuántos registros hay en cada tabla (no borra nada)
    python scripts/clean_data.py --execute    # borra de verdad (no se puede deshacer)

Escribe en la misma base que usa la app (Supabase si hay credenciales en .env / secrets, si no el SQLite local).
Genera antes un respaldo ZIP en `respaldos/` salvo que se pase --sin-respaldo."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from db import repository as repo  # noqa: E402

# se conservan: el catálogo, quién puede entrar y los datos fiscales de la empresa
KEEP = ("materials", "users", "company_profile")
# de lo más dependiente a lo menos: así ninguna llave foránea bloquea el borrado
ORDER = [
    "attachments", "attendance", "inventory_count_lines", "inventory_counts", "stock_movements", "dispatch_vouchers", "order_receipts",
    "purchase_order_items", "purchase_orders", "site_budgets", "price_history", "supplier_materials", "workers", "project_sites",
    "work_groups", "suppliers", "audit_log",
]


def _count(table: str) -> int:
    if repo.USING_LOCAL:
        from db import local_repository as local

        with local._connect() as conn:
            return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    from db.client import get_client

    return int(get_client().table(table).select("*", count="exact").limit(1).execute().count or 0)


def _wipe(table: str) -> None:
    if repo.USING_LOCAL:
        from db import local_repository as local

        with local._connect() as conn:
            conn.execute(f"delete from {table}")
        return
    from db.client import get_client

    get_client().table(table).delete().not_.is_("id", "null").execute()


def _wipe_files() -> int:
    """Borra del almacenamiento los documentos adjuntos (en Supabase viven en un bucket aparte de la tabla)."""
    if repo.USING_LOCAL:
        import shutil

        from db import local_repository as local

        folder = local._attachments_dir()
        removed = sum(1 for p in folder.rglob("*") if p.is_file())
        shutil.rmtree(folder, ignore_errors=True)
        return removed
    from db.client import get_client
    from utils import attachments as rules

    storage = get_client().storage.from_(rules.BUCKET)
    paths = [row["storage_path"] for row in get_client().table("attachments").select("storage_path").execute().data or [] if row.get("storage_path")]
    for start in range(0, len(paths), 100):
        storage.remove(paths[start:start + 100])
    return len(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--execute", action="store_true", help="borrar de verdad")
    parser.add_argument("--sin-respaldo", action="store_true", help="no generar el ZIP previo")
    args = parser.parse_args()

    print(f"Base: {'SQLite local' if repo.USING_LOCAL else 'Supabase'}")
    print("\nSe conservan:")
    for table in KEEP:
        print(f"  {table:<22}{_count(table):>7}")
    print("\nSe borran:")
    before = {table: _count(table) for table in ORDER}
    for table, n in before.items():
        print(f"  {table:<22}{n:>7}")
    if not args.execute:
        print("\nNo se borró nada. Para borrar: python scripts/clean_data.py --execute")
        return 0

    if not args.sin_respaldo:
        from utils import backup

        folder = ROOT / "respaldos"
        folder.mkdir(exist_ok=True)
        target = folder / f"respaldo_previo_{datetime.now():%Y%m%d_%H%M%S}.zip"
        target.write_bytes(backup.to_zip(repo.dump_tables()))
        print(f"\nRespaldo previo: {target}")

    print(f"\nDocumentos adjuntos borrados del almacenamiento: {_wipe_files()}")
    pending = [t for t in ORDER if before[t]]
    for attempt in range(1, 5):
        failed = []
        for table in pending:
            try:
                _wipe(table)
            except Exception as exc:  # una llave foránea pendiente: se reintenta en la siguiente vuelta
                failed.append(table)
                last = f"{table}: {exc}"
        pending = failed
        if not pending:
            break
    if pending:
        print(f"\nNo se pudo vaciar: {', '.join(pending)}\n  {last}")
        return 1

    print("\nResultado:")
    for table in (*KEEP, *ORDER):
        print(f"  {table:<22}{_count(table):>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
