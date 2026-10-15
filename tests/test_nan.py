"""Los vacíos de texto de Supabase deben llegar como None, no como NaN (pandas 3 los vuelve NaN)."""
import math
import unittest

import pandas as pd

from db.supabase_repository import _clean, _df


class EmptyTextTests(unittest.TestCase):
    rows = [
        {"code": "VS-1", "order_code": "OC-1", "note": None, "qty": 2.0},
        {"code": "VS-2", "order_code": None, "note": None, "qty": None},
    ]

    def test_missing_text_is_none_not_nan(self):
        df = _df(self.rows, columns=["code", "order_code", "note", "qty"])
        records = df.to_dict("records")
        self.assertIsNone(records[1]["order_code"])  # columna mixta: con pandas 3 sería NaN
        self.assertIsNone(records[0]["note"])
        for row in records:
            for column in ("code", "order_code", "note"):
                self.assertFalse(isinstance(row[column], float))

    def test_numeric_columns_keep_their_numeric_nan(self):
        df = _df(self.rows, columns=["code", "order_code", "note", "qty"])
        self.assertTrue(math.isnan(df.loc[1, "qty"]))  # el precio/cantidad vacío sigue siendo numérico

    def test_the_patterns_used_by_the_screens_work_with_missing_text(self):
        row = _df(self.rows, columns=["code", "order_code", "note", "qty"]).to_dict("records")[1]
        self.assertEqual(" · ".join(x for x in [row["code"], row["order_code"], row["note"]] if x), "VS-2")
        self.assertEqual(row["order_code"] or "sin orden", "sin orden")

    def test_raw_pandas_would_have_failed(self):
        """Documenta el problema original: sin limpiar, el vacío es un float «verdadero»."""
        raw = pd.DataFrame(self.rows, columns=["code", "order_code", "note", "qty"]).to_dict("records")[1]
        if isinstance(raw["order_code"], float):  # pandas >= 3
            with self.assertRaises(TypeError):
                " · ".join(x for x in [raw["code"], raw["order_code"]] if x)

    def test_clean_leaves_complete_columns_alone(self):
        df = _clean(pd.DataFrame({"a": ["x", "y"], "b": [1, 2]}))
        self.assertEqual(df["a"].tolist(), ["x", "y"])
        self.assertEqual(df["b"].tolist(), [1, 2])


if __name__ == "__main__":
    unittest.main()
