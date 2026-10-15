"""Documentos adjuntos: reglas de archivo y guardado (base local)."""
import tempfile
import unittest
import uuid
from pathlib import Path

from db import local_repository as repo
from utils import attachments as rules


class RulesTests(unittest.TestCase):
    def test_accepts_pdf_and_images_and_cleans_the_name(self):
        self.assertEqual(rules.validate("Factura N° 001 – Ferretería.PDF", 1000), ("Factura_N_001_Ferreteria.pdf", "application/pdf"))
        self.assertEqual(rules.validate("foto.JPG", 10)[1], "image/jpeg")
        self.assertEqual(rules.validate("../../etc/passwd.png", 10)[0], "passwd.png")  # sin rutas

    def test_rejects_other_types_empty_and_big_files(self):
        for name in ("virus.exe", "datos.xlsx", "sin_extension", "script.pdf.js"):
            with self.assertRaises(ValueError):
                rules.validate(name, 10)
        with self.assertRaises(ValueError):
            rules.validate("a.pdf", 0)
        with self.assertRaises(ValueError):
            rules.validate("a.pdf", rules.MAX_BYTES + 1)
        rules.validate("a.pdf", rules.MAX_BYTES)

    def test_storage_path_is_unique_and_checks_the_type(self):
        a = rules.storage_path("orden", "123", "f.pdf")
        b = rules.storage_path("orden", "123", "f.pdf")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("orden/123/") and a.endswith("-f.pdf"))
        with self.assertRaises(ValueError):
            rules.storage_path("otro", "123", "f.pdf")

    def test_human_size(self):
        self.assertEqual(rules.human_size(500), "500 B")
        self.assertEqual(rules.human_size(2048), "2 KB")
        self.assertEqual(rules.human_size(3 * 1024 * 1024), "3.0 MB")


class LocalAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = repo.DB_PATH
        repo.DB_PATH = Path(self.tmp.name) / "t.db"
        repo._init_db()
        self.entity = str(uuid.uuid4())

    def tearDown(self):
        repo.DB_PATH = self._old
        self.tmp.cleanup()

    def test_upload_list_read_and_delete(self):
        aid = repo.add_attachment("orden", self.entity, "Guía 001.pdf", b"%PDF-1.4 contenido", "admin")
        files = repo.list_attachments("orden", self.entity)
        self.assertEqual(len(files), 1)
        self.assertEqual(files.iloc[0]["filename"], "Guia_001.pdf")
        self.assertEqual(int(files.iloc[0]["size_bytes"]), len(b"%PDF-1.4 contenido"))
        meta, content = repo.read_attachment(aid)
        self.assertEqual(content, b"%PDF-1.4 contenido")
        self.assertEqual(meta["content_type"], "application/pdf")
        stored = repo._attachments_dir() / meta["storage_path"]
        self.assertTrue(stored.exists())
        repo.delete_attachment(aid)
        self.assertFalse(stored.exists())
        self.assertTrue(repo.list_attachments("orden", self.entity).empty)
        with self.assertRaises(ValueError):
            repo.read_attachment(aid)

    def test_attachments_are_per_entity(self):
        repo.add_attachment("orden", self.entity, "a.png", b"x", "admin")
        repo.add_attachment("vale", self.entity, "b.png", b"x", "admin")
        self.assertEqual(repo.list_attachments("orden", self.entity)["filename"].tolist(), ["a.png"])
        self.assertEqual(repo.list_attachments("vale", self.entity)["filename"].tolist(), ["b.png"])

    def test_invalid_upload_saves_nothing(self):
        with self.assertRaises(ValueError):
            repo.add_attachment("orden", self.entity, "malo.exe", b"x", "admin")
        self.assertTrue(repo.list_attachments("orden", self.entity).empty)
        self.assertFalse(repo._attachments_dir().exists() and any(repo._attachments_dir().rglob("*.exe")))


if __name__ == "__main__":
    unittest.main()
