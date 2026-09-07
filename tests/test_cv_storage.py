from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from service.cv_storage import LocalCVStorage, StoragePathError


class LocalCVStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.storage = LocalCVStorage(
            storage_root=self.root,
            library_root=self.root / "CV_Theque",
            staging_path=self.root / "staging",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_store_json_original_and_duplicate_original_name(self) -> None:
        src = self.root / "staging" / "CV JAOUAD (2).pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"pdf")

        json_path = self.storage.store_extracted("FullStack", "Senior", "CV JAOUAD (2)", {"ok": True})
        first = self.storage.store_original(src, "FullStack", "Senior")
        second = self.storage.store_original(src, "FullStack", "Senior")

        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), {"ok": True})
        self.assertEqual(first.name, "CV JAOUAD (2).pdf")
        self.assertEqual(second.name, "CV JAOUAD (2) (1).pdf")

    def test_unicode_filename_and_processed_move(self) -> None:
        src = self.root / "staging" / "développeur confirmé.docx"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"docx")

        moved = self.storage.move(src, self.root / "staging" / "processed" / src.name)

        self.assertFalse(src.exists())
        self.assertTrue(moved.exists())
        self.assertEqual(moved.name, "développeur confirmé.docx")

    def test_directory_traversal_is_rejected(self) -> None:
        with self.assertRaises(StoragePathError):
            self.storage.write_json(self.root.parent / "escape.json", {"bad": True})

    def test_list_files_ignores_reserved_directories(self) -> None:
        staging = self.root / "staging"
        (staging / "processed").mkdir(parents=True)
        (staging / "processed" / "old.pdf").write_bytes(b"old")
        nested = staging / "Full Stack" / "Senior" / "CV Test.pdf"
        nested.parent.mkdir(parents=True)
        nested.write_bytes(b"new")

        files = self.storage.list_files(staging, extensions={".pdf"}, ignored_dirs={"processed", "failed"})

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "CV Test.pdf")


if __name__ == "__main__":
    unittest.main()
