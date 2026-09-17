from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from script.staging_watcher import StagingScanner
from scripts.google_drive_bulk_import import (
    DOCX_MIME,
    DOC_MIME,
    PDF_MIME,
    BulkImportState,
    GoogleDriveBulkImporter,
    ImporterAlreadyRunningError,
    ImporterLock,
    build_staging_sha256_index,
    safe_drive_filename,
)
from service.cv_storage import LocalCVStorage
from service.google_drive_import import (
    DriveFile,
    GoogleDriveImportError,
    list_shared_drive_files,
)


def _drive_file(
    file_id: str,
    *,
    name: str | None = None,
    mime_type: str = PDF_MIME,
    size: int | None = 10,
    modified_time: str = "2026-01-01T00:00:00Z",
    md5_checksum: str | None = "md5",
) -> DriveFile:
    return DriveFile(
        file_id=file_id,
        name=name or f"{file_id}.pdf",
        mime_type=mime_type,
        size=size,
        modified_time=modified_time,
        md5_checksum=md5_checksum,
    )


class SharedDriveInventoryTests(unittest.TestCase):
    @patch("service.google_drive_import._drive_json")
    def test_full_inventory_paginates_beyond_one_thousand(self, drive_json) -> None:
        first = [
            {
                "id": f"pdf-{index}",
                "name": f"{index}.pdf",
                "mimeType": PDF_MIME,
                "size": "10",
            }
            for index in range(1000)
        ]
        second = [
            {
                "id": f"docx-{index}",
                "name": f"{index}.docx",
                "mimeType": DOCX_MIME,
                "size": "20",
            }
            for index in range(1000)
        ]
        remaining = [
            {
                "id": f"doc-{index}",
                "name": f"{index}.doc",
                "mimeType": DOC_MIME,
                "size": "30",
            }
            for index in range(12)
        ]
        drive_json.side_effect = [
            {"files": first, "nextPageToken": "page-2"},
            {"files": second, "nextPageToken": "page-3"},
            {"files": remaining},
        ]

        files = list_shared_drive_files("shared-drive")

        self.assertEqual(len(files), 2012)
        self.assertEqual(drive_json.call_count, 3)
        self.assertEqual(
            drive_json.call_args_list[1].args[1]["pageToken"],
            "page-2",
        )
        self.assertEqual(
            drive_json.call_args_list[2].args[1]["pageToken"],
            "page-3",
        )

    @patch("service.google_drive_import._drive_json")
    def test_inventory_uses_shared_drive_parameters_and_mime_query(
        self,
        drive_json,
    ) -> None:
        drive_json.return_value = {"files": []}

        list_shared_drive_files("shared-drive")

        path, params = drive_json.call_args.args
        self.assertEqual(path, "/files")
        self.assertEqual(params["corpora"], "drive")
        self.assertEqual(params["driveId"], "shared-drive")
        self.assertEqual(params["includeItemsFromAllDrives"], "true")
        self.assertEqual(params["supportsAllDrives"], "true")
        self.assertEqual(params["spaces"], "drive")
        self.assertEqual(params["pageSize"], "1000")
        self.assertIn("trashed = false", params["q"])
        self.assertIn(PDF_MIME, params["q"])
        self.assertIn(DOCX_MIME, params["q"])
        self.assertIn(DOC_MIME, params["q"])
        self.assertIn("modifiedTime", params["fields"])
        self.assertIn("md5Checksum", params["fields"])

    @patch("service.google_drive_import._drive_json")
    def test_inventory_filters_mimes_and_dedupes_exact_drive_ids(
        self,
        drive_json,
    ) -> None:
        drive_json.return_value = {
            "files": [
                {"id": "pdf", "name": "a.pdf", "mimeType": PDF_MIME},
                {"id": "docx", "name": "a.docx", "mimeType": DOCX_MIME},
                {"id": "doc", "name": "a.doc", "mimeType": DOC_MIME},
                {"id": "pdf", "name": "duplicate.pdf", "mimeType": PDF_MIME},
                {"id": "image", "name": "a.png", "mimeType": "image/png"},
            ]
        }

        files = list_shared_drive_files("shared-drive")

        self.assertEqual([item.file_id for item in files], ["pdf", "docx", "doc"])

    @patch("service.google_drive_import._drive_json")
    def test_interactive_caps_do_not_limit_bulk_inventory(self, drive_json) -> None:
        drive_json.return_value = {
            "files": [
                {"id": str(index), "name": f"{index}.pdf", "mimeType": PDF_MIME}
                for index in range(150)
            ]
        }

        files = list_shared_drive_files("shared-drive")

        self.assertEqual(len(files), 150)
        self.assertEqual(drive_json.call_count, 1)


class BulkImportStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_state_survives_reopen(self) -> None:
        drive_file = _drive_file("one")
        with BulkImportState(self.path) as state:
            state.upsert_inventory([drive_file])
            state.begin_attempt("one")
            state.complete(
                "one",
                status="imported",
                sha256="abc",
                local_path="/staging/one.pdf",
            )

        with BulkImportState(self.path) as reopened:
            record = reopened.get("one")

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "imported")
        self.assertEqual(record.attempts, 1)
        self.assertEqual(record.sha256, "abc")

    def test_completed_unchanged_file_is_skipped_on_resume(self) -> None:
        drive_file = _drive_file("one")
        with BulkImportState(self.path) as state:
            state.upsert_inventory([drive_file])
            state.begin_attempt("one")
            state.complete(
                "one",
                status="imported",
                sha256="abc",
                local_path="/staging/one.pdf",
            )
            state.upsert_inventory([drive_file])

            self.assertFalse(state.should_process("one", max_attempts=3))
            self.assertEqual(state.get("one").status, "imported")

    def test_failed_file_is_retryable_until_max_attempts(self) -> None:
        with BulkImportState(self.path) as state:
            state.upsert_inventory([_drive_file("one")])
            state.begin_attempt("one")
            state.fail(
                "one",
                error_class="NetworkError",
                error_summary="safe failure",
            )

            self.assertTrue(state.should_process("one", max_attempts=3))
            self.assertFalse(state.should_process("one", max_attempts=1))

    def test_materially_changed_metadata_requeues_completed_file(self) -> None:
        original = _drive_file("one", size=10, md5_checksum="old")
        changed = _drive_file(
            "one",
            size=11,
            modified_time="2026-02-01T00:00:00Z",
            md5_checksum="new",
        )
        with BulkImportState(self.path) as state:
            state.upsert_inventory([original])
            state.begin_attempt("one")
            state.complete(
                "one",
                status="imported",
                sha256="abc",
                local_path="/staging/one.pdf",
            )
            state.upsert_inventory([changed])
            record = state.get("one")

        assert record is not None
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.attempts, 0)
        self.assertIsNone(record.sha256)
        self.assertIsNone(record.local_path)

    def test_each_file_transition_is_committed_for_other_readers(self) -> None:
        with BulkImportState(self.path) as state:
            state.upsert_inventory([_drive_file("one")])
            state.begin_attempt("one")
            state.complete(
                "one",
                status="already_present",
                sha256="abc",
                local_path="/staging/existing.pdf",
            )
            reader = sqlite3.connect(self.path)
            try:
                row = reader.execute(
                    "SELECT status, sha256 FROM drive_files WHERE drive_file_id = ?",
                    ("one",),
                ).fetchone()
            finally:
                reader.close()

        self.assertEqual(row, ("already_present", "abc"))

    def test_single_instance_lock_rejects_second_importer(self) -> None:
        with ImporterLock(self.path):
            with self.assertRaises(ImporterAlreadyRunningError):
                with ImporterLock(self.path):
                    pass


class BulkImportContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.staging = self.root / "staging"
        self.state_path = self.root / "state.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(
        self,
        files: list[DriveFile],
        downloader,
        **kwargs,
    ):
        with BulkImportState(self.state_path) as state:
            state.upsert_inventory(files)
            summary = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=downloader,
                **kwargs,
            ).run(files)
            records = {item.file_id: state.get(item.file_id) for item in files}
        return summary, records

    def test_sha_duplicate_against_existing_staging_is_not_written(self) -> None:
        self.staging.mkdir()
        existing = self.staging / "existing.pdf"
        existing.write_bytes(b"same-content")
        drive_file = _drive_file("one", name="new.pdf")

        summary, records = self._run(
            [drive_file],
            lambda *_args, **_kwargs: b"same-content",
        )

        self.assertEqual(summary.already_present, 1)
        self.assertEqual(records["one"].status, "already_present")
        self.assertEqual(records["one"].local_path, str(existing.resolve()))
        self.assertFalse((self.staging / "new.pdf").exists())

    def test_duplicate_content_in_current_run_is_not_written_twice(self) -> None:
        files = [_drive_file("one"), _drive_file("two")]

        summary, records = self._run(
            files,
            lambda *_args, **_kwargs: b"same-content",
        )

        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.already_present, 1)
        self.assertEqual(len(list(self.staging.glob("*.pdf"))), 1)
        self.assertEqual(records["two"].status, "already_present")

    def test_same_filename_with_different_content_gets_unique_names(self) -> None:
        files = [
            _drive_file("one", name="candidate.pdf"),
            _drive_file("two", name="candidate.pdf"),
        ]

        self._run(
            files,
            lambda file_id, **_kwargs: file_id.encode("utf-8"),
        )

        self.assertEqual(
            sorted(path.name for path in self.staging.glob("*.pdf")),
            ["candidate (1).pdf", "candidate.pdf"],
        )

    def test_unsafe_filename_uses_deterministic_fallback(self) -> None:
        drive_file = _drive_file("safe-id", name="../../escape.pdf")

        summary, records = self._run(
            [drive_file],
            lambda *_args, **_kwargs: b"content",
        )

        self.assertEqual(summary.imported, 1)
        self.assertEqual(safe_drive_filename(drive_file), "drive-safe-id.pdf")
        self.assertTrue((self.staging / "drive-safe-id.pdf").exists())
        self.assertFalse((self.root / "escape.pdf").exists())
        self.assertEqual(records["safe-id"].status, "imported")

    def test_hidden_and_reserved_files_are_excluded_from_baseline_index(self) -> None:
        self.staging.mkdir()
        visible = self.staging / "visible.pdf"
        visible.write_bytes(b"visible")
        hidden = self.staging / ".hidden.pdf"
        hidden.write_bytes(b"hidden")
        failed = self.staging / "failed" / "old.pdf"
        failed.parent.mkdir()
        failed.write_bytes(b"failed")

        index = build_staging_sha256_index(self.staging)

        self.assertEqual(list(index.values()), [visible.resolve()])


class LegacyDocAndFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.staging = self.root / "staging"
        self.state_path = self.root / "state.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_doc_is_downloaded_to_ignored_quarantine(self) -> None:
        drive_file = _drive_file(
            "legacy",
            name="legacy.doc",
            mime_type=DOC_MIME,
        )
        downloaded = MagicMock(return_value=b"legacy-bytes")
        with BulkImportState(self.state_path) as state:
            state.upsert_inventory([drive_file])
            summary = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=downloaded,
            ).run([drive_file])
            record = state.get("legacy")

        path = self.staging / "failed" / "legacy-doc" / "legacy.doc"
        self.assertEqual(path.read_bytes(), b"legacy-bytes")
        self.assertEqual(summary.quarantined_doc, 1)
        self.assertEqual(record.status, "quarantined_doc")
        downloaded.assert_called_once()

        storage = LocalCVStorage(
            storage_root=self.root,
            library_root=self.root / "CV_Theque",
            staging_path=self.staging,
        )
        scanner = StagingScanner(storage, str(self.staging))
        self.assertEqual(scanner.scan(), [])

    def test_download_error_records_failure_without_partial_file(self) -> None:
        drive_file = _drive_file("one")
        with BulkImportState(self.state_path) as state:
            state.upsert_inventory([drive_file])
            summary = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=MagicMock(
                    side_effect=GoogleDriveImportError("network unavailable")
                ),
            ).run([drive_file])
            record = state.get("one")

        self.assertEqual(summary.failed, 1)
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.last_error_class, "GoogleDriveImportError")
        self.assertEqual(list(self.staging.rglob("*.pdf")), [])

    def test_oversize_metadata_fails_without_download_or_partial_file(self) -> None:
        drive_file = _drive_file("large", size=101)
        downloader = MagicMock()
        with BulkImportState(self.state_path) as state:
            state.upsert_inventory([drive_file])
            summary = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                max_bytes=100,
                downloader=downloader,
            ).run([drive_file])
            record = state.get("large")

        self.assertEqual(summary.failed, 1)
        self.assertEqual(record.status, "failed")
        downloader.assert_not_called()
        self.assertEqual(list(self.staging.rglob("*.*")), [])

    def test_interruption_before_publish_is_safely_resumable(self) -> None:
        drive_file = _drive_file("one")
        interrupting_publisher = MagicMock(side_effect=KeyboardInterrupt)
        with BulkImportState(self.state_path) as state:
            state.upsert_inventory([drive_file])
            importer = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=lambda *_args, **_kwargs: b"content",
                publisher=interrupting_publisher,
            )
            with self.assertRaises(KeyboardInterrupt):
                importer.run([drive_file])
            self.assertEqual(state.get("one").status, "pending")

            resumed = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=lambda *_args, **_kwargs: b"content",
            ).run([drive_file])

        self.assertEqual(resumed.imported, 1)
        self.assertEqual(len(list(self.staging.glob("*.pdf"))), 1)

    def test_interruption_after_publish_reconciles_without_redownload(self) -> None:
        drive_file = _drive_file("one")
        with BulkImportState(self.state_path) as state:
            state.upsert_inventory([drive_file])
            importer = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=lambda *_args, **_kwargs: b"content",
                after_publish=lambda *_args: (_ for _ in ()).throw(
                    KeyboardInterrupt
                ),
            )
            with self.assertRaises(KeyboardInterrupt):
                importer.run([drive_file])
            self.assertEqual(state.get("one").status, "pending")
            self.assertEqual(len(list(self.staging.glob("*.pdf"))), 1)

            downloader = MagicMock(side_effect=AssertionError("redownloaded"))
            resumed = GoogleDriveBulkImporter(
                state=state,
                staging_root=self.staging,
                downloader=downloader,
            ).run([drive_file])
            record = state.get("one")

        downloader.assert_not_called()
        self.assertEqual(resumed.already_present, 1)
        self.assertEqual(record.status, "already_present")
        self.assertEqual(len(list(self.staging.glob("*.pdf"))), 1)


class PilotResumeTests(unittest.TestCase):
    def test_max_files_limits_pilot_and_resume_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [_drive_file(str(index)) for index in range(15)]
            downloader = MagicMock(
                side_effect=lambda file_id, **_kwargs: file_id.encode("utf-8")
            )
            with BulkImportState(root / "state.sqlite3") as state:
                state.upsert_inventory(files)
                importer = GoogleDriveBulkImporter(
                    state=state,
                    staging_root=root / "staging",
                    downloader=downloader,
                )

                pilot = importer.run(files, max_files=10)
                resumed = importer.run(files)

            self.assertEqual(pilot.processed_this_run, 10)
            self.assertEqual(pilot.remaining, 5)
            self.assertEqual(resumed.processed_this_run, 5)
            self.assertEqual(resumed.imported, 15)
            self.assertEqual(downloader.call_count, 15)


if __name__ == "__main__":
    unittest.main()
