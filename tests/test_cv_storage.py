from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from pathlib import Path

from service.cv_storage import (
    LocalCVStorage,
    StoragePathError,
    atomic_write_staging_upload,
    canonical_staging_profile,
    canonical_staging_seniority,
    resolve_staging_upload_path,
)


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

    def test_rejects_unsafe_profile_components(self) -> None:
        bad_profiles = [
            "../../escape",
            "Full/Stack",
            "Full\\Stack",
            "/tmp/escape",
            "C:\\escape",
            "valid/../../escape",
        ]
        for profile in bad_profiles:
            with self.subTest(profile=profile):
                with self.assertRaises(StoragePathError):
                    canonical_staging_profile(profile)

    def test_valid_profile_and_seniority_are_canonical(self) -> None:
        self.assertEqual(canonical_staging_profile("full stack"), "FullStack")
        self.assertEqual(canonical_staging_seniority("confirmée"), "Confirme")

    def test_unicode_cv_filename_is_preserved(self) -> None:
        written, size = atomic_write_staging_upload(
            staging_root=self.root / "staging",
            filename="développeur confirmé.pdf",
            source=io.BytesIO(b"pdf"),
            max_bytes=10,
            profile="full stack",
            seniority="senior",
        )

        self.assertEqual(size, 3)
        self.assertEqual(written.name, "développeur confirmé.pdf")
        self.assertEqual(written.read_bytes(), b"pdf")

    def test_duplicate_filename_does_not_overwrite_existing_content(self) -> None:
        first, _ = atomic_write_staging_upload(
            staging_root=self.root / "staging",
            filename="cv.pdf",
            source=io.BytesIO(b"first"),
            max_bytes=10,
            profile="backend",
        )
        second, _ = atomic_write_staging_upload(
            staging_root=self.root / "staging",
            filename="cv.pdf",
            source=io.BytesIO(b"second"),
            max_bytes=10,
            profile="backend",
        )

        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), b"first")
        self.assertEqual(second.read_bytes(), b"second")

    def test_resolved_destination_must_stay_under_staging(self) -> None:
        path = resolve_staging_upload_path(
            staging_root=self.root / "staging",
            filename="cv.pdf",
            profile="backend",
            seniority="junior",
        )
        self.assertTrue(path.is_relative_to((self.root / "staging").resolve(strict=False)))

    def test_symlink_inside_staging_cannot_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        staging = self.root / "staging"
        staging.mkdir()
        link = staging / "Backend"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        with self.assertRaises(StoragePathError):
            atomic_write_staging_upload(
                staging_root=staging,
                filename="cv.pdf",
                source=io.BytesIO(b"pdf"),
                max_bytes=10,
                profile="backend",
            )

    def test_final_name_is_not_visible_until_publish(self) -> None:
        staging = self.root / "staging"
        final_path = staging / "Backend" / "cv.pdf"
        observations = []

        class ObservedReader(io.BytesIO):
            def read(self, size=-1):
                observations.append(final_path.exists())
                return super().read(size)

        written, _ = atomic_write_staging_upload(
            staging_root=staging,
            filename="cv.pdf",
            source=ObservedReader(b"pdf"),
            max_bytes=10,
            profile="backend",
            chunk_size=1,
        )

        self.assertEqual(written, final_path.resolve(strict=False))
        self.assertTrue(written.exists())
        self.assertTrue(observations)
        self.assertFalse(any(observations))


if __name__ == "__main__":
    unittest.main()
