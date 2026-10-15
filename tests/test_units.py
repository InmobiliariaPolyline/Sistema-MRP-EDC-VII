"""Métricas de cómputo: una sola forma de escribir cada unidad."""
import unittest

from utils import units


class UnitsTests(unittest.TestCase):
    def test_variants_are_written_one_way(self):
        self.assertEqual(units.normalize("Volumen (m3)"), "Volumen (m³)")
        self.assertEqual(units.normalize("volumen (M³)"), "Volumen (m³)")  # coincide con una estándar
        self.assertEqual(units.normalize("Área (m^2)"), "Área (m²)")
        self.assertEqual(units.normalize("Peso (Kg)"), "Peso (kg)")
        self.assertEqual(units.normalize("  Peso   (kgs)  "), "Peso (kg)")
        self.assertEqual(units.normalize("UNIDADES"), "unidad")

    def test_known_values_keep_their_spelling(self):
        known = ["Área (m²) — se cotiza por peso areal (g/m²)", "Peso (kg / ton) / Longitud (m)"]
        self.assertEqual(units.normalize("peso (kg / ton) / longitud (m)", known), "Peso (kg / ton) / Longitud (m)")

    def test_unknown_text_is_only_cleaned(self):
        self.assertEqual(units.normalize("Pliego  de lija"), "Pliego de lija")
        self.assertEqual(units.normalize(None), "")

    def test_options_put_the_used_ones_first_without_duplicates(self):
        found = units.options(["Peso (kg)", "Peso (kg)", "Volumen (m3)", None, "", "Rareza"])
        self.assertEqual(found[:3], ["Peso (kg)", "Volumen (m³)", "Rareza"])
        self.assertEqual(len(found), len(set(found)))
        self.assertIn("Longitud (m)", found)  # las estándar siempre están


if __name__ == "__main__":
    unittest.main()
