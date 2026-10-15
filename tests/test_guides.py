"""Guías de uso y ventana de ayuda «Cómo usar»."""
import re
import unittest
from pathlib import Path

from modules import guides, help_ui
from utils import icons

# títulos con los que cada pantalla llama a page_header
SCREEN_TITLES = [
    "Dashboard", "Órdenes de compra", "Proveedores", "Materiales", "Inventario", "Obras y presupuesto", "Asistencia",
    "Trabajadores", "Reportes", "Historial de cambios", "Respaldo de datos", "Sistema",
]


class GuideDataTests(unittest.TestCase):
    def test_every_screen_has_a_guide(self):
        for title in SCREEN_TITLES:
            guide = guides.guide_for("", title)
            self.assertIsNotNone(guide, title)
            self.assertEqual(guide["title"], title)
        self.assertEqual(guides.guide_for("Centro de control · OCTUBRE", "Buenos días, Luis")["title"], "Dashboard")
        self.assertIsNone(guides.guide_for("", "Pantalla que no existe"))

    def test_page_headers_in_the_code_all_resolve_to_a_guide(self):
        modules_dir = Path(__file__).resolve().parent.parent / "modules"
        found = set()
        for path in modules_dir.glob("*.py"):
            for match in re.finditer(r'page_header\(\s*"([^"]+)",\s*"([^"]+)"', path.read_text(encoding="utf-8")):
                found.add(match.group(2))
        self.assertTrue(found)
        for title in found:
            self.assertIn(title, guides.GUIDES, f"la pantalla «{title}» no tiene guía")

    def test_structure_is_complete_and_simple(self):
        for title, guide in guides.GUIDES.items():
            with self.subTest(guia=title):
                self.assertIn(guide["icon"], icons.ICONS)
                self.assertTrue(guide["summary"].endswith("."))
                self.assertGreaterEqual(len(guide["sections"]), 1)
                for section in guide["sections"]:
                    self.assertTrue(section["title"])
                    self.assertGreaterEqual(len(section["steps"]), 1)
                    for step in section["steps"]:
                        self.assertTrue(step["title"] and step["text"])
                        self.assertLessEqual(len(step["title"]), 60, step["title"])
                        self.assertLessEqual(len(step["text"]), 420, f"paso demasiado largo en {title}: {step['title']}")
                        self.assertNotRegex(step["title"], r"^\d")   # los números los pone la ventana, no el texto
                if guide.get("example"):
                    self.assertTrue(guide["example"]["title"])
                    self.assertGreaterEqual(len(guide["example"]["steps"]), 2)
                for key in ("tips", "warnings", "not_does"):
                    self.assertTrue(all(isinstance(t, str) and t for t in guide.get(key, [])))

    def test_money_wording_never_claims_a_payment_or_a_loss(self):
        text = repr(guides.GUIDES).lower()
        for forbidden in ("pérdida de dinero", "dinero perdido", "se va el dinero", "comprado hasta hoy", "procesa pagos."):
            self.assertNotIn(forbidden, text)
        self.assertIn("no se conecta con el sistema del proveedor", repr(guides.GUIDES["Órdenes de compra"]["not_does"]))


class HelpHtmlTests(unittest.TestCase):
    def test_inline_formatting_is_safe(self):
        self.assertEqual(help_ui.inline("Pulsa **Guardar** y mira `scripts/x.py`"), "Pulsa <strong>Guardar</strong> y mira <code>scripts/x.py</code>")
        self.assertEqual(help_ui.inline("un *énfasis* simple"), "un <em>énfasis</em> simple")
        self.assertEqual(help_ui.inline("<script>alert(1)</script> & más"), "&lt;script&gt;alert(1)&lt;/script&gt; &amp; más")
        self.assertEqual(help_ui.inline(None), "")
        self.assertEqual(help_ui.inline("2 * 3 * 4"), "2 * 3 * 4")   # asteriscos sueltos no son cursiva

    def test_steps_are_numbered_continuously_across_sections(self):
        guide = guides.guide_for("", "Órdenes de compra")
        html_text = help_ui.steps_html(guide)
        numbers = [int(n) for n in re.findall(r'<span class="mrp-help-num">(\d+)</span>', html_text)]
        self.assertEqual(numbers, list(range(1, help_ui.count_steps(guide) + 1)))
        self.assertIn("Parte 1 de 5", html_text)
        self.assertEqual(html_text.count("<ol"), html_text.count("</ol>"))
        self.assertEqual(html_text.count("<li>"), html_text.count("</li>"))

    def test_single_section_guides_say_pasos_and_where_chips_appear(self):
        asistencia = help_ui.steps_html(guides.guide_for("", "Asistencia"))
        self.assertIn(">Pasos<", asistencia)
        self.assertNotIn("Parte 1", asistencia)
        self.assertIn("mrp-help-where", help_ui.steps_html(guides.guide_for("", "Proveedores")))

    def test_hero_example_and_callouts(self):
        guide = guides.guide_for("", "Inventario")
        hero = help_ui.hero_html(guide)
        self.assertIn("Inventario", hero)
        self.assertIn("pasos", hero)
        self.assertIn("<svg", hero)
        self.assertIn("con ejemplo", hero)
        example = help_ui.example_html(guide)
        self.assertEqual(example.count("<li>"), len(guide["example"]["steps"]))
        self.assertEqual(help_ui.example_html(guides.guide_for("", "Asistencia")), "")
        callouts = help_ui.callouts_html(guides.guide_for("", "Órdenes de compra"))
        self.assertIn("mrp-help-warn", callouts)
        self.assertIn("mrp-help-no", callouts)
        self.assertIn("Lo que el sistema no hace", callouts)

    def test_no_raw_markdown_left_in_any_guide_html(self):
        for title in guides.GUIDES:
            guide = guides.guide_for("", title)
            for fragment in (help_ui.hero_html(guide), help_ui.steps_html(guide), help_ui.example_html(guide), help_ui.callouts_html(guide)):
                plain = re.sub(r"<[^>]+>", "", fragment)
                self.assertNotIn("**", plain, title)
                self.assertNotIn("`", plain, title)

    def test_lists_are_forced_to_full_width_against_streamlit_fit_content(self):
        css = (Path(__file__).resolve().parent.parent / "modules" / "styles" / "45_help.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.mrp-help-steps,\s*\.mrp-help-timeline\s*\{[^}]*width:\s*100%\s*!important")

    def test_css_for_every_help_class_exists(self):
        css = (Path(__file__).resolve().parent.parent / "modules" / "styles" / "45_help.css").read_text(encoding="utf-8")
        every = ""
        for title in guides.GUIDES:
            guide = guides.guide_for("", title)
            every += help_ui.hero_html(guide) + help_ui.steps_html(guide) + help_ui.example_html(guide) + help_ui.callouts_html(guide)
        for name in sorted(set(re.findall(r'class="(mrp-help-[a-z-]+)"', every))):
            self.assertIn("." + name, css, f"falta el estilo de {name}")


if __name__ == "__main__":
    unittest.main()
