"""Comprueba si la base está cerrada para la clave PÚBLICA de Supabase.

Uso:
    python scripts/check_security.py

Intenta, con SUPABASE_KEY (la clave pública), escribir una fila de prueba en cada tabla (y la borra
si llegó a entrar). Si la base está abierta, lo dice tabla por tabla; si está cerrada, cada intento
falla con «permission denied» (42501). También informa si la app está usando la clave de servicio.

Además prueba las funciones rpc con datos inexistentes (no escriben nada)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):  # consola de Windows (cp1252): que no falle con tildes ni símbolos
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT))

from db.client import _get_setting, using_service_key  # noqa: E402

Z = "00000000-0000-0000-0000-000000000001"
PROBES = {
    "materials": {"category": "zz-probe", "name": "zz-probe"},
    "suppliers": {"name": "zz-probe"},
    "work_groups": {"name": "zz-probe"},
    "project_sites": {"name": "zz-probe"},
    "users": {"username": "zz-probe", "password_hash": "x", "name": "zz", "role": "invitado"},
    "workers": {"full_name": "zz-probe"},
    "supplier_materials": {"supplier_id": Z, "material_id": Z},
    "purchase_orders": {"code": "zz-probe", "supplier_name": "zz"},
    "purchase_order_items": {"order_id": Z, "material_name": "zz", "quantity": 1},
    "dispatch_vouchers": {"code": "zz-probe", "site_name": "zz"},
    "stock_movements": {"material_id": Z, "kind": "entrada", "quantity": 1},
    "site_budgets": {"project_site_id": Z, "material_id": Z},
    "attendance": {"worker_id": Z, "work_date": "2026-01-01"},
    "audit_log": {"actor": "zz-probe", "summary": "zz-probe"},
    "price_history": {"supplier_id": Z, "material_id": Z},
    # Fase B (si todavía no se corrió su SQL, la tabla no existe y se omite)
    "inventory_counts": {"code": "zz-probe"},
    "inventory_count_lines": {"count_id": Z, "material_id": Z, "system_qty": 0, "counted_qty": 0, "difference": 0},
    "order_receipts": {"order_id": Z},
    "attachments": {"entity_type": "zz", "entity_id": Z, "filename": "zz", "storage_path": "zz-probe"},
}


def main() -> int:
    url, public_key = _get_setting("SUPABASE_URL"), _get_setting("SUPABASE_KEY")
    if not url or not public_key:
        print("Falta SUPABASE_URL o SUPABASE_KEY (la clave pública) en .env.")
        return 2
    from supabase import create_client

    client = create_client(url, public_key)
    print(f"La app usa la clave de servicio: {'SÍ' if using_service_key() else 'NO (modo abierto)'}\n")
    open_tables = []
    for table, row in PROBES.items():
        try:
            res = client.table(table).insert(row).execute()
            if res.data and res.data[0].get("id"):
                client.table(table).delete().eq("id", res.data[0]["id"]).execute()
            open_tables.append(table)
            print(f"  ABIERTA   {table}  (la clave pública pudo escribir)")
        except Exception as exc:
            code = str(getattr(exc, "code", ""))
            if code in ("42501",):
                print(f"  cerrada   {table}")
            elif code in ("PGRST205", "42P01"):
                print(f"  (no existe) {table}: falta correr el SQL de su parche")
            else:  # pasó el control de acceso y falló después (p. ej. clave foránea): también está abierta
                open_tables.append(table)
                print(f"  ABIERTA   {table}  (pasó los permisos; falló por {code})")
    for fn, params in {
        "receive_order": {"p_order_id": Z, "p_receipts": {}, "p_actor": "check"},
        "create_dispatch": {"p_site": Z, "p_worker": None, "p_requested_by": None, "p_note": None, "p_actor": "check", "p_lines": [{"material_id": Z, "quantity": 1}]},
    }.items():
        try:
            client.rpc(fn, params).execute()
            print(f"  ABIERTA   función {fn}")
            open_tables.append(fn)
        except Exception as exc:
            code = str(getattr(exc, "code", ""))
            if code in ("42501", "PGRST202"):
                print(f"  cerrada   función {fn}")
            else:  # respondió con su propio error: la clave pública pudo llamarla
                print(f"  ABIERTA   función {fn}  ({getattr(exc, 'message', exc)})")
                open_tables.append(fn)
    print()
    if open_tables:
        print(f"⚠️  BASE ABIERTA: {len(open_tables)} elemento(s) accesibles con la clave pública. Ver db/migrations/040_cerrar_base.sql.")
        return 1
    print("✅ Base cerrada: la clave pública no puede escribir en ninguna tabla ni llamar a las funciones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
