"""Ejecuta las pruebas SQL contra un Postgres real (PGlite) con Node: scripts, funciones, triggers, vistas y cierre de la base.

Las pruebas están en tests/sql/sql.test.mjs. Necesitan Node y `npm ci` dentro de tests/sql; si falta alguno, se omiten
(en GitHub Actions siempre se ejecutan)."""
import shutil
import subprocess
import unittest
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"
NODE = shutil.which("node")
READY = NODE and (SQL_DIR / "node_modules" / "@electric-sql" / "pglite").exists()


@unittest.skipUnless(READY, "falta Node o `npm ci` en tests/sql (ver tests/sql/package.json)")
class SqlRuntimeTests(unittest.TestCase):
    def test_sql_scripts_and_functions_on_real_postgres(self):
        result = subprocess.run([NODE, "--test"], cwd=SQL_DIR, capture_output=True, text=True, encoding="utf-8", timeout=600)
        self.assertEqual(result.returncode, 0, f"\n{result.stdout[-4000:]}\n{result.stderr[-1500:]}")


if __name__ == "__main__":
    unittest.main()
