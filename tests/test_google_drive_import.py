import unittest

from service.google_drive_import import DriveFile, dedupe_files, extract_drive_id


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


if __name__ == "__main__":
    unittest.main()
