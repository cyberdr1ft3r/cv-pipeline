import unittest
from unittest.mock import patch

from service.google_drive_import import (
    DRIVE_FOLDER_MIME,
    DriveFile,
    GoogleDriveImportError,
    dedupe_files,
    extract_drive_id,
    list_folder_files,
)


PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class GoogleDriveImportTests(unittest.TestCase):
    def test_extract_file_id_from_standard_drive_url(self):
        self.assertEqual(
            extract_drive_id("https://drive.google.com/file/d/abc123/view?usp=sharing"),
            "abc123",
        )

    def test_extract_folder_id_from_drive_folder_url(self):
        self.assertEqual(
            extract_drive_id("https://drive.google.com/drive/folders/folder123?usp=sharing", folder=True),
            "folder123",
        )

    def test_extract_id_from_open_url(self):
        self.assertEqual(
            extract_drive_id("https://drive.google.com/open?id=file456"),
            "file456",
        )

    def test_dedupe_files_preserves_order(self):
        files = [
            DriveFile("one", "one.pdf", "application/pdf"),
            DriveFile("two", "two.pdf", "application/pdf"),
            DriveFile("one", "one-copy.pdf", "application/pdf"),
        ]
        self.assertEqual([item.file_id for item in dedupe_files(files)], ["one", "two"])

    @patch("service.google_drive_import._drive_json")
    def test_recursively_lists_nested_folders(self, drive_json):
        drive_json.side_effect = [
            {
                "files": [
                    {"id": "root-file", "name": "root.pdf", "mimeType": PDF},
                    {"id": "nested", "name": "Nested", "mimeType": DRIVE_FOLDER_MIME},
                ]
            },
            {"files": [{"id": "nested-file", "name": "nested.docx", "mimeType": DOCX}]},
        ]

        files = list_folder_files("root", max_files=10)

        self.assertEqual([item.file_id for item in files], ["root-file", "nested-file"])
        self.assertIn("'nested' in parents", drive_json.call_args_list[1].args[1]["q"])

    @patch("service.google_drive_import._drive_json")
    def test_follows_page_tokens_and_keeps_shared_drive_parameters(self, drive_json):
        drive_json.side_effect = [
            {"nextPageToken": "next-page", "files": [{"id": "one", "mimeType": PDF}]},
            {"files": [{"id": "two", "mimeType": PDF}]},
        ]

        files = list_folder_files("root", max_files=10)

        self.assertEqual([item.file_id for item in files], ["one", "two"])
        second_params = drive_json.call_args_list[1].args[1]
        self.assertEqual(second_params["pageToken"], "next-page")
        self.assertEqual(second_params["supportsAllDrives"], "true")
        self.assertEqual(second_params["includeItemsFromAllDrives"], "true")

    @patch("service.google_drive_import._drive_json")
    def test_duplicate_file_ids_do_not_consume_max_files(self, drive_json):
        drive_json.return_value = {
            "files": [
                {"id": "one", "name": "one.pdf", "mimeType": PDF},
                {"id": "one", "name": "one-copy.pdf", "mimeType": PDF},
                {"id": "two", "name": "two.pdf", "mimeType": PDF},
            ]
        }

        files = list_folder_files("root", max_files=2)

        self.assertEqual([item.file_id for item in files], ["one", "two"])

    @patch("service.google_drive_import._drive_json")
    def test_max_files_stops_traversal(self, drive_json):
        drive_json.return_value = {
            "nextPageToken": "unused-page",
            "files": [
                {"id": "one", "mimeType": PDF},
                {"id": "two", "mimeType": PDF},
                {"id": "three", "mimeType": PDF},
            ],
        }

        files = list_folder_files("root", max_files=2)

        self.assertEqual([item.file_id for item in files], ["one", "two"])
        drive_json.assert_called_once()

    @patch("service.google_drive_import._drive_json")
    def test_repeated_and_cyclic_folder_ids_are_visited_once(self, drive_json):
        responses = {
            "root": {
                "files": [
                    {"id": "child", "mimeType": DRIVE_FOLDER_MIME},
                    {"id": "child", "mimeType": DRIVE_FOLDER_MIME},
                ]
            },
            "child": {
                "files": [
                    {"id": "root", "mimeType": DRIVE_FOLDER_MIME},
                    {"id": "cv", "mimeType": PDF},
                ]
            },
        }

        def response_for_folder(_path, params):
            folder_id = params["q"].split("'")[1]
            return responses[folder_id]

        drive_json.side_effect = response_for_folder

        files = list_folder_files("root", max_files=10)

        self.assertEqual([item.file_id for item in files], ["cv"])
        self.assertEqual(drive_json.call_count, 2)

    @patch("service.google_drive_import._drive_json")
    def test_unsupported_mime_types_are_ignored(self, drive_json):
        drive_json.return_value = {
            "files": [
                {"id": "sheet", "mimeType": "application/vnd.google-apps.spreadsheet"},
                {"id": "image", "mimeType": "image/png"},
                {"id": "cv", "mimeType": PDF},
            ]
        }

        files = list_folder_files("root", max_files=10)

        self.assertEqual([item.file_id for item in files], ["cv"])

    @patch("service.google_drive_import.MAX_FOLDER_SCAN", 1)
    @patch("service.google_drive_import._drive_json")
    def test_folder_scan_safety_ceiling(self, drive_json):
        drive_json.side_effect = [
            {"files": [{"id": "child", "mimeType": DRIVE_FOLDER_MIME}]},
            {"files": []},
        ]

        with self.assertRaisesRegex(GoogleDriveImportError, "too large"):
            list_folder_files("root", max_files=10)


if __name__ == "__main__":
    unittest.main()
