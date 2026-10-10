"""Reglas de formularios: valores opcionales, notación de obra y límites."""
import unittest

from modules.forms import validate


class FormValidationTests(unittest.TestCase):
    def test_optional_fields_can_be_empty(self):
        self.assertEqual(validate({"Teléfono": "", "Correo (opcional)": None, "Densidad (kg/m³, opcional)": 0, "Métrica de cómputo": ""}), [])

    def test_required_whitespace_is_not_a_name(self):
        self.assertTrue(validate({"Nombre del proveedor": "  "}))

    def test_construction_notation_and_accents_are_preserved(self):
        self.assertEqual(validate({"Nombre": "Concreto f'c≥210 kg/cm² · ⌀ ½″ – 2′", "Nombre completo": "María O’Connor", "Métrica de cómputo": "Volumen (m³)"}), [])

    def test_unknown_optional_density_stays_optional(self):
        self.assertEqual(validate({"Densidad (kg/m³, opcional)": None}), [])

    def test_phone_and_email_have_useful_format_checks(self):
        self.assertEqual(validate({"Teléfono": "+51 (987) 654-321", "Correo (opcional)": "ventas+obra@empresa.com"}), [])
        self.assertTrue(validate({"Teléfono": "123abc", "Correo (opcional)": "ventas@"}))

    def test_number_must_be_finite_and_positive(self):
        for value in (0, -1, float("nan"), float("inf"), ""):
            with self.subTest(value=value):
                self.assertTrue(validate({"Cantidad": value}))
        self.assertEqual(validate({"Cantidad": 0.25, "Precio unit.": 0}), [])

    def test_dynamic_labels_apply_same_rules(self):
        self.assertTrue(validate({"Cantidad prevista (m³)": -1}))
        self.assertTrue(validate({"Recibido ahora (máx. 10)": -1}))

    def test_multiline_notes_are_accepted(self):
        self.assertEqual(validate({"Notas (opcional)": "Primera entrega: lunes.\nSegunda entrega: viernes."}), [])
        self.assertTrue(validate({"Notas (opcional)": "a" * 501}))


if __name__ == "__main__":
    unittest.main()
