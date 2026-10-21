"""Logotipo de proveedores y botones de contacto con mensajes preestablecidos."""
import base64
import io
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image

from db import local_repository as repo
from modules import ui
from utils import contact, logo, pdf_style


def png(width=400, height=200, color=(200, 30, 60), mode="RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color).save(buffer, "PNG")
    return buffer.getvalue()


class LogoTests(unittest.TestCase):
    def test_images_are_reduced_and_become_a_data_url(self):
        url = logo.process(png(1200, 600))
        self.assertTrue(url.startswith("data:image/png;base64,"))
        image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        self.assertEqual(max(image.size), logo.MAX_SIDE)
        self.assertEqual(image.size, (160, 80))               # conserva la proporción
        self.assertLess(len(url), 20000)

    def test_small_images_are_kept_and_transparency_survives(self):
        url = logo.process(png(64, 64, (10, 20, 30, 0), "RGBA"))
        image = Image.open(io.BytesIO(logo.to_bytes(url)))
        self.assertEqual(image.size, (64, 64))
        self.assertEqual(image.mode, "RGBA")
        self.assertEqual(image.getpixel((5, 5))[3], 0)

    def test_bad_files_are_refused_with_a_clear_message(self):
        for data, expected in ((b"", "vacío"), (b"no soy una imagen", "No se pudo leer"), (png(8, 8), "pequeña"), (b"0" * (logo.MAX_UPLOAD_BYTES + 1), "pesa más")):
            with self.assertRaises(logo.LogoError) as caught:
                logo.process(data)
            self.assertIn(expected, str(caught.exception))

    def test_to_bytes_is_safe_with_garbage(self):
        for bad in (None, "", "http://x/y.png", "data:image/png;base64,@@@", "data:text/html,<script>"):
            self.assertIsNone(logo.to_bytes(bad))
        self.assertFalse(logo.is_valid("nada"))
        self.assertTrue(logo.is_valid(logo.process(png())))


class LogoStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        repo.upsert_supplier("Aceros del Sur", "Pedro", "987654321", "p@x.pe", None)
        self.supplier = repo.list_suppliers().iloc[0]["id"]

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_logo_is_saved_listed_and_removed(self):
        self.assertIsNone(repo.list_suppliers().iloc[0]["logo"])
        url = logo.process(png())
        repo.set_supplier_logo(self.supplier, url)
        self.assertEqual(repo.list_suppliers().iloc[0]["logo"], url)
        repo.upsert_supplier("Aceros del Sur", "Pedro", "987654321", "p@x.pe", "nota", self.supplier)   # editar datos no borra el logotipo
        self.assertEqual(repo.list_suppliers().iloc[0]["logo"], url)
        repo.set_supplier_logo(self.supplier, None)
        self.assertIsNone(repo.list_suppliers().iloc[0]["logo"])


class AvatarTests(unittest.TestCase):
    def test_avatar_shows_the_logo_or_the_initial(self):
        self.assertIn("<img", ui.avatar("Aceros", logo.process(png())))
        self.assertIn("mrp-logo", ui.avatar("Aceros", logo.process(png())))
        self.assertIn(">A<", ui.avatar("Aceros"))
        self.assertNotIn("<img", ui.avatar("Aceros", "javascript:alert(1)"))
        evil = ui.avatar('x"><script>', logo.process(png()))
        self.assertNotIn("<script>", evil)


class ContactTests(unittest.TestCase):
    def test_phone_numbers(self):
        self.assertEqual(contact.whatsapp_number("+51 987 654 321"), "51987654321")
        self.assertEqual(contact.whatsapp_number("987654321"), "51987654321")        # celular peruano sin código
        self.assertEqual(contact.whatsapp_number("(01) 234-5678"), "012345678")
        self.assertEqual(contact.dial_number("+51 987-654 321"), "+51987654321")
        self.assertEqual(contact.whatsapp_number(None), "")

    def test_supplier_messages_are_varied_and_formal(self):
        msgs = contact.messages("Ana María Ruiz", "Constructora Ejemplo")
        self.assertGreaterEqual(len(msgs), 5)
        self.assertEqual(len({m["key"] for m in msgs}), len(msgs))
        self.assertEqual(len({m["email"] for m in msgs}), len(msgs))
        for m in msgs:
            self.assertTrue(m["label"] and m["hint"] and m["subject"])
            self.assertIn("Buen día, Ana:", m["email"])
            self.assertIn("Le escribe Constructora Ejemplo.", m["email"])
            self.assertIn("Quedo atento", m["email"])
        anonymous = contact.messages(None, None)
        self.assertTrue(all(m["email"].startswith("Buen día:") for m in anonymous))

    def test_messages_are_formatted_per_channel(self):
        m = contact.messages("Ana", "Ejemplo SAC")[0]
        wa, mail = m["whatsapp"], m["email"]
        self.assertTrue(wa.startswith("*Solicitud de cotización*\n\nBuen día, Ana:"))   # título en negrita de WhatsApp
        self.assertTrue(wa.rstrip().endswith("_Ejemplo SAC_"))                            # firma en cursiva
        self.assertIn("\n   •  Precio unitario", wa)                                       # sangría y viñeta
        self.assertNotIn("*", mail)                                                        # el correo va en texto limpio
        self.assertIn("\n   •  Precio unitario", mail)
        self.assertTrue(mail.rstrip().endswith("Saludos cordiales,\nEjemplo SAC"))
        self.assertNotIn("\n\n\n", wa)
        data = contact.messages("Ana", None)[1]["whatsapp"]                               # datos por completar con su campo en negrita
        self.assertIn("*Material:* ____", data)

    def test_worker_messages_are_completely_different_and_informal(self):
        workers = contact.messages("Juan Pérez", "Constructora Ejemplo", "worker", "Torre Central", "Maestro de obra")
        suppliers = contact.messages("Juan Pérez", "Constructora Ejemplo")
        self.assertGreaterEqual(len(workers), 6)
        self.assertFalse({m["key"] for m in workers} & {m["key"] for m in suppliers})        # ninguna opción se repite
        self.assertFalse({m["label"] for m in workers} & {m["label"] for m in suppliers})
        for m in workers:
            self.assertIn("Hola Juan, buen día.", m["whatsapp"])
            self.assertNotIn("cotiza", m["whatsapp"].lower())                                  # a un trabajador no se le pide un catálogo
            self.assertNotIn("catálogo", m["whatsapp"].lower())
            self.assertNotIn("Le escribe", m["whatsapp"])                                      # trato de tú, no de usted
        convoca = next(m for m in workers if m["key"] == "convocatoria")["whatsapp"]
        self.assertIn("*Obra:* Torre Central", convoca)                                        # usa la obra y el puesto del trabajador
        self.assertIn("*Puesto:* Maestro de obra", convoca)
        self.assertIn("Gracias por tu apoyo.", convoca)
        no_site = next(m for m in contact.messages("Juan", None, "worker") if m["key"] == "convocatoria")["whatsapp"]
        self.assertIn("*Obra:* ____", no_site)
        self.assertTrue(no_site.rstrip().endswith("_Equipo de obra_"))

    def test_links_carry_the_text_encoded(self):
        body = "Hola, ¿cómo está? Precio & plazo: 100%"
        wa = urlparse(contact.whatsapp_url("987654321", body))
        self.assertEqual((wa.netloc, wa.path), ("wa.me", "/51987654321"))
        self.assertEqual(unquote(parse_qs(wa.query)["text"][0]), body)
        gm = urlparse(contact.gmail_url("a@b.pe", "Asunto ñ", body))
        self.assertEqual(gm.netloc, "mail.google.com")
        self.assertEqual(parse_qs(gm.query)["to"], ["a@b.pe"])
        self.assertEqual(parse_qs(gm.query)["body"], [body])
        ol = urlparse(contact.outlook_url("a@b.pe", "Asunto", body))
        self.assertEqual(ol.netloc, "outlook.live.com")
        self.assertTrue(contact.mailto_url("a@b.pe", "S", body).startswith("mailto:a%40b.pe?subject="))

    def test_buttons_html(self):
        html = ui.contact_links("987654321", "a@b.pe", "Ana", "Ejemplo")
        self.assertNotIn("\n\n", html)
        self.assertEqual(html.count("<details"), 3)                 # WhatsApp, Gmail y Outlook
        for kind in ("call", "wa", "gmail", "outlook"):
            self.assertIn(f"mrp-cbtn {kind}", html)
        self.assertEqual(html.count("wa.me/"), len(contact.messages()))
        self.assertIn("Elige un mensaje", html)
        self.assertIn("mail.google.com", html)
        self.assertIn("outlook.live.com", html)
        self.assertIn("mailto:", html)
        self.assertIn("tel:987654321", html)
        only_phone = ui.contact_links("987654321", None)
        self.assertNotIn("gmail", only_phone)
        only_mail = ui.contact_links(None, "a@b.pe")
        self.assertNotIn("wa.me", only_mail)
        self.assertIn("Sin datos de contacto", ui.contact_links(None, None))
        self.assertNotIn("<script", ui.contact_links("1", 'x"><script>alert(1)</script>@a.pe'))

    def test_worker_buttons_have_their_own_menu(self):
        html = ui.contact_links("987654321", None, "Juan Pérez", "Ejemplo", "worker", "Torre Central", "Albañil")
        self.assertIn("Mensaje para tu equipo", html)
        self.assertEqual(html.count("<details"), 1)               # solo WhatsApp: a un trabajador no se le escribe por Gmail
        self.assertEqual(html.count("wa.me/"), len(contact.messages(audience="worker")))
        self.assertIn("Convocatoria de trabajo", unquote(html))
        self.assertNotIn("Solicitar cotización", html)
        self.assertNotIn("gmail", html)

    def test_every_class_used_has_a_style(self):
        css = (Path(__file__).resolve().parent.parent / "modules" / "styles" / "56_contact.css").read_text(encoding="utf-8")
        html = ui.contact_links("987654321", "a@b.pe") + ui.avatar("x", logo.process(png()))
        for name in sorted(set(re.findall(r"mrp-(?:cbtn|menu|contact|logo)[a-z-]*", html))):
            self.assertIn("." + name, css, name)


class PdfLogoTests(unittest.TestCase):
    def test_logo_is_drawn_inside_its_box_and_bad_ones_are_ignored(self):
        pdf = pdf_style.BrandPDF("Doc", "D-1")
        pdf.add_page()
        self.assertTrue(pdf.logo(logo.process(png(400, 100)), 20, 20, 14))
        self.assertFalse(pdf.logo(None, 20, 20))
        self.assertFalse(pdf.logo("data:image/png;base64,@@@", 20, 20))
        self.assertTrue(bytes(pdf.output()).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
