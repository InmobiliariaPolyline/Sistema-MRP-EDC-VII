"""Sistema visual: iconos en lugar de emojis, valores con color, hojas de estilo y pantalla de acceso."""
import re
import unittest
from pathlib import Path

import pandas as pd

from modules import login, ui, ui_styles
from utils import icons

ROOT = Path(__file__).resolve().parent.parent
TEXT_GLYPHS = {"✕", "✓", "★"}   # ✕, ✓ y ★ son símbolos de texto (toman el color de la letra), no emojis
EMOJI_RANGE = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⬆⬇✅❌ℹ⚠⏰⏱]")


class IconTests(unittest.TestCase):
    def test_every_emoji_in_the_code_has_an_icon(self):
        """Un emoji sin icono asignado se vería como emoji de color en pantalla."""
        missing = {}
        for path in sorted((ROOT / "modules").glob("*.py")) + sorted((ROOT / "core").glob("*.py")) + [ROOT / "utils" / "pricing.py"]:
            if path.name in ("icons.py", "guides.py") or path.name.startswith("manual_"):
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for found in EMOJI_RANGE.findall(line.replace("️", "")):
                    if found in TEXT_GLYPHS:
                        continue
                    if not any(found in key for key in icons.EMOJI):
                        missing[f"{path.name}:{number}"] = found
        self.assertEqual(missing, {}, "emojis sin icono")

    def test_icon_mapping_points_to_real_icons(self):
        for emoji, (name, material) in icons.EMOJI.items():
            self.assertIn(name, icons.ICONS, emoji)
            self.assertRegex(material, r"^[a-z0-9_]+$")

    def test_render_tokens_swaps_emojis_and_material_codes(self):
        html_text = icons.render_tokens("<b>📦 Stock</b> <i>:material/delete:</i> :material/no_existe:")
        self.assertEqual(html_text.count("<svg"), 2)
        self.assertNotIn("📦", html_text)
        self.assertIn(":material/no_existe:", html_text)   # un código desconocido se deja tal cual

    def test_components_draw_vector_icons(self):
        card = ui.stat_card("🚚", 5, "Despachos")
        self.assertIn("<svg", card)
        self.assertNotIn("🚚", card)
        self.assertIn("<svg", ui.timeline_item("🧱", "Material", "sub"))
        self.assertIn("<svg", ui.pill("📅 5 d", "red"))
        self.assertEqual(icons.split_lead("🗑 Eliminar"), (":material/delete:", "Eliminar"))
        self.assertTrue(ui._toast_icon("🧮").startswith(":material/"))
        self.assertEqual(ui._toast_icon(":material/key:"), ":material/key:")
        self.assertEqual(ui._toast_icon("desconocido"), ":material/check_circle:")

    def test_brand_mark_is_a_vector(self):
        self.assertIn("mrp-mark-draw", icons.brand_mark(30, animated=True))
        self.assertNotIn("mrp-mark-draw", icons.brand_mark(30))


class SignedValueTests(unittest.TestCase):
    def test_signed_colors_by_sign(self):
        self.assertIn("mrp-num-pos", ui.signed(5))
        self.assertIn("mrp-num-neg", ui.signed(-5))
        self.assertIn("mrp-num-zero", ui.signed(0))
        self.assertIn("mrp-num-neg", ui.signed(5, good_when_positive=False))   # p. ej. una merma: más es peor
        self.assertIn(">1,200<", ui.signed(1200, "1,200"))

    def test_tint_frame_paints_only_the_requested_columns(self):
        df = pd.DataFrame({"Material": ["a", "b"], "Diferencia": [3, -2], "Entrada": [4, 0], "Salida": [0, 7]})
        styler = ui.tint_frame(df, signed=["Diferencia"], good=["Entrada"], bad=["Salida"])
        styler._compute()
        painted = {(row, col): styles for (row, col), styles in styler.ctx.items()}
        flat = {key: " ".join(f"{prop}:{value}" for prop, value in styles) for key, styles in painted.items()}
        self.assertTrue(any("color" in v for k, v in flat.items() if k[1] == 1))       # Diferencia
        self.assertTrue(any("color" in v for k, v in flat.items() if k[1] == 2))       # Entrada
        self.assertFalse(any(k[1] == 0 for k in flat))                                  # Material sin color


class StyleSheetTests(unittest.TestCase):
    def test_every_palette_variable_used_is_defined(self):
        sheets = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "modules" / "styles").glob("*.css") if p.name[:2].isdigit())
        for name in ("palette_light.css", "palette_dark.css"):
            palette = (ROOT / "modules" / "styles" / name).read_text(encoding="utf-8")
            defined = set(re.findall(r"(--mrp-[a-z0-9-]+):", palette))
            used = set(re.findall(r"var\((--mrp-[a-z0-9-]+)", sheets)) - {"--mrp-enter"}
            self.assertEqual(sorted(used - defined), [], f"variables sin definir en {name}")

    def test_motion_tokens_and_keyframes_exist(self):
        css = (ROOT / "modules" / "styles" / "05_motion.css").read_text(encoding="utf-8")
        for token in ("--ease-out", "--ease-spring", "--dur-base"):
            self.assertIn(token, css)
        used = set()
        for path in (ROOT / "modules" / "styles").glob("*.css"):
            used |= set(re.findall(r"animation:\s*(mrp[A-Za-z]+)", path.read_text(encoding="utf-8")))
        defined = set(re.findall(r"@keyframes\s+(mrp[A-Za-z]+)", css + (ROOT / "modules" / "styles" / "00_base.css").read_text(encoding="utf-8")))
        self.assertEqual(sorted(used - defined), [])

    def test_motion_is_switched_off_for_people_who_ask(self):
        base = (ROOT / "modules" / "styles" / "00_base.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", base)

    def test_bundle_loads_in_order_and_is_minified(self):
        bundle = ui_styles.bundle()
        self.assertNotIn("\n\n", bundle["css"])
        self.assertLess(bundle["css"].index("--ease-out"), bundle["css"].index(".mrp-hero"))


class LoginScreenTests(unittest.TestCase):
    def test_login_and_boot_styles_are_safe_for_markdown(self):
        for css in (login._SHELL_CSS, login._BOOT_CSS):
            self.assertTrue(css.startswith("<style>") and css.endswith("</style>"))
            self.assertNotIn("\n\n", css)
            self.assertNotIn("/*", css)
        self.assertIn("bootBar", login._BOOT_CSS)
        self.assertIn("lpCount", login._SHELL_CSS)

    def test_login_screens_carry_no_emoji(self):
        source = (ROOT / "modules" / "login.py").read_text(encoding="utf-8")
        self.assertIsNone(EMOJI_RANGE.search(source))


if __name__ == "__main__":
    unittest.main()
