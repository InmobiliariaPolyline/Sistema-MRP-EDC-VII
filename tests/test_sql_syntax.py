"""Los scripts SQL de db/ deben ser sintácticamente válidos para Postgres (incluidas las funciones plpgsql).

Usa pglast (el analizador real de Postgres). Si no está instalado (`pip install pglast`), se omite."""
import unittest
from pathlib import Path

try:
    import pglast
    from pglast import parse_plpgsql
    from pglast.parser import split
except Exception:  # pragma: no cover
    pglast = None

DB = Path(__file__).resolve().parent.parent / "db"
FILES = sorted([DB / "schema.sql", *(DB / "migrations").glob("*.sql")])


@unittest.skipIf(pglast is None, "pglast no está instalado")
class SqlSyntaxTests(unittest.TestCase):
    def test_every_sql_file_parses(self):
        self.assertTrue(FILES)
        for path in FILES:
            with self.subTest(archivo=path.name):
                pglast.parse_sql(path.read_text(encoding="utf-8"))

    def test_every_plpgsql_function_parses(self):
        count = 0
        for path in FILES:
            for statement in split(path.read_text(encoding="utf-8"), with_parser=True, only_slices=False):
                text = str(statement)
                if "create or replace function" in text.lower() and "plpgsql" in text.lower():
                    with self.subTest(archivo=path.name, funcion=text.split("(")[0][-30:]):
                        parse_plpgsql(text)
                    count += 1
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
