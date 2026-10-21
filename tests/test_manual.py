"""Manual de usuario: datos, maquetas fieles a los formularios reales, marcas, búsqueda y página."""
import re
import unittest
from pathlib import Path

from modules import manual_data as data
from modules import manual_ui as mui
from utils import icons

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"


def _procedures():
    for c_no, chapter in enumerate(data.CHAPTERS, start=1):
        for p_no, proc in enumerate(chapter["procedures"], start=1):
            yield c_no, p_no, chapter, proc


def _source(name):
    """Código de un archivo citado por una maqueta: ruta desde la raíz del proyecto o desde modules/."""
    path = ROOT / name
    if not path.exists():
        path = MODULES / name
    return path.read_text(encoding="utf-8")


def _labels(mock):
    """(texto a comprobar, descripción) de cada etiqueta de la maqueta."""
    out = []
    for row in mock["rows"]:
        fields = row.get("fields") or ([row] if "field" in row else [])
        for f in fields:
            out.append((f.get("check", f["field"]), f"campo {f['field']}"))
        for key, text in (row.get("stats") or []):
            out.append((key.split("(")[0], f"dato {key}"))   # «IGV (18%)» lleva la tasa dinámica
        for button in row.get("buttons", []):
            out.append((button[0].lstrip("＋+ ").strip(), f"botón {button[0]}"))
        for tab in row.get("tabs", []):
            out.append((tab, f"pestaña {tab}"))
        if "table" in row:
            out.extend((col, f"columna {col}") for col in row["table"]["cols"])
    return out


class ManualDataTests(unittest.TestCase):
    def test_structure(self):
        self.assertGreaterEqual(len(data.CHAPTERS), 5)
        ids = [c["id"] for c in data.CHAPTERS]
        self.assertEqual(len(ids), len(set(ids)))
        for chapter in data.CHAPTERS:
            self.assertIn(chapter["icon"], icons.ICONS, chapter["id"])
            self.assertTrue(chapter["summary"].endswith("."))
            for block in chapter.get("blocks", []):
                self.assertIn(block, mui.BLOCKS)
        for _c, _p, chapter, proc in _procedures():
            with self.subTest(proc=proc["title"]):
                self.assertTrue(proc["goal"] and proc["steps"])
                for step in proc["steps"]:
                    self.assertTrue(step["title"] and step["text"])
                    self.assertNotRegex(step["title"], r"^\d")

    def test_marks_in_the_mock_match_the_steps(self):
        for _c, _p, _chapter, proc in _procedures():
            if not proc.get("mock"):
                continue
            html_text = mui.mock_html(proc["mock"])
            marks = {int(n) for n in re.findall(r'<span class="mrp-mock-mark">(\d+)</span>', html_text)}
            self.assertLessEqual(max(marks, default=0), len(proc["steps"]), f"marca sin paso en «{proc['title']}»")

    def test_mock_labels_are_the_real_ones(self):
        """Cada etiqueta, botón, dato y columna de la maqueta existe en el código del módulo que la dibuja."""
        for _c, _p, _chapter, proc in _procedures():
            mock = proc.get("mock")
            if not mock:
                continue
            source = " ".join("".join(_source(name) for name in mock["source"]).split())
            for text, what in _labels(mock):
                with self.subTest(proc=proc["title"], item=what):
                    if " ".join(text.split()) not in source:
                        self.fail(f"«{text}» no está en {mock['source']}")

    def test_money_wording(self):
        text = repr(data.CHAPTERS) + repr(data.FAQ) + repr(data.GLOSSARY) + repr(data.DOES) + repr(data.DOES_NOT)
        low = text.lower()
        for forbidden in ("pérdida de dinero", "dinero perdido", "compra formal", "pasarela de pago", "emitir el documento"):
            self.assertNotIn(forbidden, low)
        self.assertIn("no se conecta", low)


class ManualHtmlTests(unittest.TestCase):
    def test_every_mock_and_block_renders_balanced_and_escaped(self):
        pieces = [mui.mock_html(p["mock"]) for *_x, p in _procedures() if p.get("mock")] + [fn() for fn in mui.BLOCKS.values()] + [mui.glossary_html()]
        for html_text in pieces:
            self.assertEqual(html_text.count("<div"), html_text.count("</div>"))
            self.assertNotIn("\n\n", html_text)
            self.assertNotIn("**", re.sub(r"<[^>]+>", "", html_text))

    def test_escaping(self):
        self.assertEqual(mui.esc("<b>&"), "&lt;b&gt;&amp;")
        html_text = mui.mock_html({"title": "<x>", "source": [], "rows": [{"field": "<i>", "kind": "text", "value": "<script>"}]})
        self.assertNotIn("<script>", html_text)
        self.assertNotIn("<x>", html_text)

    def test_steps_are_numbered_like_the_marks(self):
        steps = [{"title": "A", "text": "uno"}, {"title": "B", "text": "dos"}]
        html_text = mui.steps_html(steps)
        self.assertEqual(re.findall(r'mrp-mock-mark big">(\d+)<', html_text), ["1", "2"])

    def test_unknown_row_is_rejected(self):
        with self.assertRaises(ValueError):
            mui.mock_html({"title": "t", "source": [], "rows": [{"nope": 1}]})

    def test_css_for_every_class_exists(self):
        css = (MODULES / "styles" / "47_manual.css").read_text(encoding="utf-8") + (MODULES / "styles" / "45_help.css").read_text(encoding="utf-8")
        every = "".join(mui.mock_html(p["mock"]) for *_x, p in _procedures() if p.get("mock"))
        every += "".join(fn() for fn in mui.BLOCKS.values()) + mui.glossary_html()
        every += "".join(mui.proc_head_html(1, 1, p) for *_x, p in _procedures()) + mui.chapter_head_html(1, 7, data.CHAPTERS[0], 3)
        for name in sorted(set(re.findall(r"mrp-(?:mock|man)-[a-z0-9-]+", every))):
            if "." + name not in css:
                self.fail(f"falta el estilo de {name}")

    def test_lists_are_forced_to_full_width(self):
        css = (MODULES / "styles" / "47_manual.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.mrp-man-steps\s*\{[^}]*width:\s*100%\s*!important")


class ManualSearchTests(unittest.TestCase):
    def test_search_ignores_accents_and_case(self):
        self.assertEqual(mui.search("RECEPCION")[:1] and True, True)
        self.assertEqual({id(r[3]) for r in mui.search("recepción")}, {id(r[3]) for r in mui.search("RECEPCION")})
        self.assertEqual(mui.search(""), [])
        self.assertEqual(mui.search("zzzzxxxx"), [])
        self.assertTrue(mui.search("igv"))


class ManualPageTests(unittest.TestCase):
    def test_page_renders_every_chapter_and_search(self):
        from streamlit.testing.v1 import AppTest

        script = "import streamlit as st\nfrom modules import manual_Usuario\nmanual_Usuario.show()\n"
        at = AppTest.from_string(script, default_timeout=60).run()
        self.assertFalse(at.exception, at.exception)
        for chapter in mui.chapters():
            at.session_state[mui.CHAPTER_KEY] = chapter["id"]
            at.run()
            self.assertFalse(at.exception, f"{chapter['id']}: {at.exception}")
        at.text_input(key="manual_query").set_value("recepción").run()
        self.assertFalse(at.exception, at.exception)


if __name__ == "__main__":
    unittest.main()
