import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bundled_documents as documents


class EmbeddedDocumentTests(unittest.TestCase):
    def make_bundle(self, root):
        data = b"Copyright original author\r\nAll original license terms.\r\n"
        entry = {"path": "licenses/author.txt", "title": "Author license",
                 "sha256": hashlib.sha256(data).hexdigest()}
        (root / "licenses").mkdir()
        (root / entry["path"]).write_bytes(data)
        (root / "index.json").write_text(json.dumps([entry]), "utf-8")
        return entry, data

    def test_frozen_documents_are_inside_exe_bundle_not_beside_exe(self):
        with patch.object(documents.sys, "frozen", True, create=True), \
                patch.object(documents.sys, "_MEIPASS", "/private/bundle", create=True):
            self.assertEqual(documents.document_root(), Path("/private/bundle/documents"))

    def test_read_preserves_original_bytes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            entry, raw = self.make_bundle(root)
            with patch.object(documents, "document_root", return_value=root):
                self.assertEqual(documents.read_document(entry), raw)

    def test_missing_or_modified_license_fails_validation(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            entry, _ = self.make_bundle(root)
            (root / entry["path"]).write_bytes(b"truncated")
            with patch.object(documents, "document_root", return_value=root), self.assertRaisesRegex(ValueError, "校验失败"):
                documents.read_document(entry)

    def test_manifest_cannot_read_outside_document_bundle(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "bundle"
            root.mkdir()
            (root.parent / "outside.txt").write_text("private")
            entry = {"path": "../outside.txt", "sha256": "unused"}
            with patch.object(documents, "document_root", return_value=root), self.assertRaisesRegex(ValueError, "路径无效"):
                documents.read_document(entry)
