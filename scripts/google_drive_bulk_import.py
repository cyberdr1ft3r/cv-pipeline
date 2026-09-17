"""Resumable one-off Google Drive migration into watcher staging.

This module inventories a Shared Drive, records durable per-file state in
SQLite, and publishes supported CVs atomically without invoking the watcher or
the extraction pipeline.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from service.cv_storage import (
    StoragePathError,
    atomic_write_staging_upload,
    sanitize_filename_component,
)
from service.google_drive_import import (
    DriveFile,
    GoogleDriveImportError,
    download_file,
    list_shared_drive_files,
)


PDF_MIME = "application/pdf"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
DOC_MIME = "application/msword"
MIME_EXTENSIONS = {
    PDF_MIME: ".pdf",
    DOCX_MIME: ".docx",
    DOC_MIME: ".doc",
}
TERMINAL_STATUSES = frozenset(
    {"imported", "already_present", "quarantined_doc"}
)
ALL_STATUSES = (
    "pending",
    "imported",
    "already_present",
    "quarantined_doc",
    "failed",
)
RESERVED_STAGING_DIRS = frozenset({"processed", "failed"})
DEFAULT_STORAGE_ROOT = Path(
    os.getenv("CV_STORAGE_ROOT", "/sftp/cv_tech/files")
)
DEFAULT_STAGING_ROOT = Path(
    os.getenv(
        "WATCHER_STAGING_PATH",
        str(DEFAULT_STORAGE_ROOT / "staging"),
    )
)
DEFAULT_STATE_FILE = Path(
    os.getenv(
        "GOOGLE_DRIVE_BULK_STATE_FILE",
        str(
            DEFAULT_STORAGE_ROOT
            / "import_state"
            / "google_drive_bulk.sqlite3"
        ),
    )
)
DEFAULT_MAX_BYTES = int(
    os.getenv("GOOGLE_DRIVE_BULK_MAX_BYTES", str(50 * 1024 * 1024))
)
DEFAULT_MAX_ATTEMPTS = int(
    os.getenv("GOOGLE_DRIVE_BULK_MAX_ATTEMPTS", "3")
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ImportRecord:
    drive_file_id: str
    name: str
    mime_type: str
    size: int | None
    modified_time: str | None
    md5_checksum: str | None
    status: str
    attempts: int
    sha256: str | None
    local_path: str | None
    last_error_class: str | None
    last_error_summary: str | None
    updated_at: str


@dataclass(frozen=True)
class MigrationSummary:
    completed: int
    imported: int
    already_present: int
    quarantined_doc: int
    failed: int
    remaining: int
    processed_this_run: int


class BulkImportState:
    """Durable SQLite state with explicit commits at per-file transitions."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA journal_mode=DELETE")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS drive_files (
                drive_file_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size INTEGER,
                modified_time TEXT,
                md5_checksum TEXT,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT,
                local_path TEXT,
                last_error_class TEXT,
                last_error_summary TEXT,
                updated_at TEXT NOT NULL,
                CHECK (status IN (
                    'pending',
                    'imported',
                    'already_present',
                    'quarantined_doc',
                    'failed'
                ))
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "BulkImportState":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get(self, drive_file_id: str) -> ImportRecord | None:
        row = self.connection.execute(
            "SELECT * FROM drive_files WHERE drive_file_id = ?",
            (drive_file_id,),
        ).fetchone()
        return ImportRecord(**dict(row)) if row else None

    def upsert_inventory(self, files: Iterable[DriveFile]) -> None:
        """Refresh metadata, requeueing completed files only when changed."""
        now = _utc_now()
        with self.connection:
            for drive_file in files:
                existing = self.get(drive_file.file_id)
                if existing is None:
                    self.connection.execute(
                        """
                        INSERT INTO drive_files (
                            drive_file_id, name, mime_type, size,
                            modified_time, md5_checksum, status, attempts,
                            sha256, local_path, last_error_class,
                            last_error_summary, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, NULL, NULL,
                                  NULL, NULL, ?)
                        """,
                        (
                            drive_file.file_id,
                            drive_file.name,
                            drive_file.mime_type,
                            drive_file.size,
                            drive_file.modified_time,
                            drive_file.md5_checksum,
                            now,
                        ),
                    )
                    continue

                changed = (
                    existing.mime_type != drive_file.mime_type
                    or existing.size != drive_file.size
                    or existing.modified_time != drive_file.modified_time
                    or existing.md5_checksum != drive_file.md5_checksum
                )
                if changed:
                    self.connection.execute(
                        """
                        UPDATE drive_files
                        SET name = ?, mime_type = ?, size = ?,
                            modified_time = ?, md5_checksum = ?,
                            status = 'pending', attempts = 0, sha256 = NULL,
                            local_path = NULL, last_error_class = NULL,
                            last_error_summary = NULL, updated_at = ?
                        WHERE drive_file_id = ?
                        """,
                        (
                            drive_file.name,
                            drive_file.mime_type,
                            drive_file.size,
                            drive_file.modified_time,
                            drive_file.md5_checksum,
                            now,
                            drive_file.file_id,
                        ),
                    )
                else:
                    self.connection.execute(
                        """
                        UPDATE drive_files
                        SET name = ?, mime_type = ?, updated_at = ?
                        WHERE drive_file_id = ?
                        """,
                        (
                            drive_file.name,
                            drive_file.mime_type,
                            now,
                            drive_file.file_id,
                        ),
                    )

    def should_process(
        self,
        drive_file_id: str,
        *,
        max_attempts: int,
    ) -> bool:
        record = self.get(drive_file_id)
        return bool(
            record
            and record.status not in TERMINAL_STATUSES
            and record.attempts < max_attempts
        )

    def begin_attempt(self, drive_file_id: str) -> ImportRecord:
        with self.connection:
            self.connection.execute(
                """
                UPDATE drive_files
                SET attempts = attempts + 1, status = 'pending',
                    last_error_class = NULL, last_error_summary = NULL,
                    updated_at = ?
                WHERE drive_file_id = ?
                """,
                (_utc_now(), drive_file_id),
            )
        record = self.get(drive_file_id)
        if record is None:
            raise KeyError(drive_file_id)
        return record

    def record_sha256(self, drive_file_id: str, sha256: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE drive_files
                SET sha256 = ?, updated_at = ?
                WHERE drive_file_id = ?
                """,
                (sha256, _utc_now(), drive_file_id),
            )

    def complete(
        self,
        drive_file_id: str,
        *,
        status: str,
        sha256: str,
        local_path: Path | str,
    ) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Invalid completed status: {status}")
        with self.connection:
            self.connection.execute(
                """
                UPDATE drive_files
                SET status = ?, sha256 = ?, local_path = ?,
                    last_error_class = NULL, last_error_summary = NULL,
                    updated_at = ?
                WHERE drive_file_id = ?
                """,
                (
                    status,
                    sha256,
                    str(local_path),
                    _utc_now(),
                    drive_file_id,
                ),
            )

    def fail(
        self,
        drive_file_id: str,
        *,
        error_class: str,
        error_summary: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE drive_files
                SET status = 'failed', last_error_class = ?,
                    last_error_summary = ?, updated_at = ?
                WHERE drive_file_id = ?
                """,
                (
                    error_class[:120],
                    error_summary[:240],
                    _utc_now(),
                    drive_file_id,
                ),
            )

    def summary(self, current_ids: Sequence[str]) -> MigrationSummary:
        counts = {status: 0 for status in ALL_STATUSES}
        if current_ids:
            placeholders = ",".join("?" for _ in current_ids)
            rows = self.connection.execute(
                f"""
                SELECT status, COUNT(*) AS count
                FROM drive_files
                WHERE drive_file_id IN ({placeholders})
                GROUP BY status
                """,
                tuple(current_ids),
            ).fetchall()
            for row in rows:
                counts[row["status"]] = int(row["count"])
        completed = sum(counts[status] for status in TERMINAL_STATUSES)
        return MigrationSummary(
            completed=completed,
            imported=counts["imported"],
            already_present=counts["already_present"],
            quarantined_doc=counts["quarantined_doc"],
            failed=counts["failed"],
            remaining=counts["pending"] + counts["failed"],
            processed_this_run=0,
        )


class ImporterAlreadyRunningError(RuntimeError):
    pass


class ImporterLock:
    """Non-blocking process lock adjacent to the durable state database."""

    def __init__(self, state_path: Path | str) -> None:
        state = Path(state_path)
        self.path = Path(f"{state}.lock")
        self._handle = None

    def __enter__(self) -> "ImporterLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(
                self._handle.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError as exc:
            self._handle.close()
            self._handle = None
            raise ImporterAlreadyRunningError(
                "Another Google Drive bulk importer is already using this state file."
            ) from exc
        return self

    def __exit__(self, *_args: object) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _is_safe_index_file(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if path.is_symlink() or not path.is_file():
        return False
    if any(part.startswith(".") for part in relative.parts):
        return False
    if any(
        part.casefold() in RESERVED_STAGING_DIRS
        for part in relative.parts[:-1]
    ):
        return False
    return path.suffix.casefold() in MIME_EXTENSIONS.values()


def build_staging_sha256_index(
    staging_root: Path | str,
) -> dict[str, Path]:
    """Hash active staging files, excluding watcher-reserved and hidden paths."""
    root = Path(staging_root).resolve(strict=False)
    if not root.exists():
        return {}
    result: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        resolved = path.resolve(strict=False)
        if root not in resolved.parents or not _is_safe_index_file(resolved, root):
            continue
        result.setdefault(sha256_file(resolved), resolved)
    return result


def build_quarantine_sha256_index(
    staging_root: Path | str,
) -> dict[str, Path]:
    """Build a recovery index for previously published legacy DOC files."""
    quarantine = (
        Path(staging_root) / "failed" / "legacy-doc"
    ).resolve(strict=False)
    if not quarantine.exists():
        return {}
    result: dict[str, Path] = {}
    for path in sorted(quarantine.rglob("*")):
        if (
            path.is_file()
            and not path.is_symlink()
            and not any(part.startswith(".") for part in path.relative_to(quarantine).parts)
            and path.suffix.casefold() == ".doc"
        ):
            result.setdefault(sha256_file(path), path.resolve(strict=False))
    return result


def safe_drive_filename(drive_file: DriveFile) -> str:
    """Return a safe name with the MIME-authoritative extension."""
    extension = MIME_EXTENSIONS.get(drive_file.mime_type)
    if extension is None:
        raise ValueError("Unsupported Drive MIME type")
    try:
        safe_name = sanitize_filename_component(drive_file.name)
        stem = Path(safe_name).stem.strip()
        if not stem:
            raise StoragePathError("Unsafe filename")
        return sanitize_filename_component(f"{stem}{extension}")
    except (StoragePathError, ValueError):
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "", drive_file.file_id)[:64]
        if not safe_id:
            safe_id = hashlib.sha256(
                drive_file.file_id.encode("utf-8")
            ).hexdigest()[:16]
        return f"drive-{safe_id}{extension}"


def _safe_error(exc: Exception) -> tuple[str, str]:
    error_class = type(exc).__name__
    if isinstance(exc, GoogleDriveImportError):
        return error_class, str(exc)
    if isinstance(exc, (StoragePathError, ValueError)):
        return error_class, str(exc)
    return error_class, "Unexpected bulk import failure"


def inventory_counts(files: Sequence[DriveFile]) -> dict[str, int]:
    counts = {"total": len(files), "pdf": 0, "docx": 0, "doc": 0}
    keys = {PDF_MIME: "pdf", DOCX_MIME: "docx", DOC_MIME: "doc"}
    for drive_file in files:
        key = keys.get(drive_file.mime_type)
        if key:
            counts[key] += 1
    return counts


class GoogleDriveBulkImporter:
    """Sequential importer that commits durable state after every file."""

    def __init__(
        self,
        *,
        state: BulkImportState,
        staging_root: Path | str = DEFAULT_STAGING_ROOT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        downloader: Callable[..., bytes] = download_file,
        publisher: Callable[..., tuple[Path, int]] = atomic_write_staging_upload,
        after_publish: Callable[[DriveFile, Path], None] | None = None,
    ) -> None:
        self.state = state
        self.staging_root = Path(staging_root).resolve(strict=False)
        self.max_bytes = max_bytes
        self.downloader = downloader
        self.publisher = publisher
        self.after_publish = after_publish

    @property
    def quarantine_root(self) -> Path:
        return self.staging_root / "failed" / "legacy-doc"

    def _status_for_path(self, drive_file: DriveFile, path: Path) -> str:
        if (
            drive_file.mime_type == DOC_MIME
            and self.quarantine_root.resolve(strict=False)
            in path.resolve(strict=False).parents
        ):
            return "quarantined_doc"
        return "already_present"

    def run(
        self,
        files: Sequence[DriveFile],
        *,
        max_files: int | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        progress_every: int = 25,
    ) -> MigrationSummary:
        if max_files is not None and max_files < 1:
            raise ValueError("max_files must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")

        self.staging_root.mkdir(parents=True, exist_ok=True)
        active_index = build_staging_sha256_index(self.staging_root)
        quarantine_index = build_quarantine_sha256_index(self.staging_root)
        known_content = {**quarantine_index, **active_index}
        processed = 0

        for drive_file in files:
            if max_files is not None and processed >= max_files:
                break
            if not self.state.should_process(
                drive_file.file_id,
                max_attempts=max_attempts,
            ):
                continue

            processed += 1
            record = self.state.begin_attempt(drive_file.file_id)
            print(
                f"migration: file={processed} name={safe_drive_filename(drive_file)}"
            )
            try:
                if drive_file.size is not None and drive_file.size > self.max_bytes:
                    raise GoogleDriveImportError(
                        "Google Drive file exceeds the configured bulk file limit."
                    )

                # Reconcile a prior publication whose final status commit was
                # interrupted. No redownload or duplicate publication is needed.
                if record.sha256 and record.sha256 in known_content:
                    existing = known_content[record.sha256]
                    self.state.complete(
                        drive_file.file_id,
                        status=self._status_for_path(drive_file, existing),
                        sha256=record.sha256,
                        local_path=existing,
                    )
                    continue

                content = self.downloader(
                    drive_file.file_id,
                    max_bytes=self.max_bytes,
                )
                if len(content) > self.max_bytes:
                    raise GoogleDriveImportError(
                        "Google Drive file exceeds the configured bulk file limit."
                    )
                digest = sha256_bytes(content)
                self.state.record_sha256(drive_file.file_id, digest)

                existing = known_content.get(digest)
                if existing is not None:
                    self.state.complete(
                        drive_file.file_id,
                        status=self._status_for_path(drive_file, existing),
                        sha256=digest,
                        local_path=existing,
                    )
                    continue

                destination_root = (
                    self.quarantine_root
                    if drive_file.mime_type == DOC_MIME
                    else self.staging_root
                )
                published, _size = self.publisher(
                    staging_root=destination_root,
                    filename=safe_drive_filename(drive_file),
                    source=io.BytesIO(content),
                    max_bytes=self.max_bytes,
                    unique=True,
                )
                known_content[digest] = published
                if self.after_publish:
                    self.after_publish(drive_file, published)
                status = (
                    "quarantined_doc"
                    if drive_file.mime_type == DOC_MIME
                    else "imported"
                )
                self.state.complete(
                    drive_file.file_id,
                    status=status,
                    sha256=digest,
                    local_path=published,
                )
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                error_class, summary = _safe_error(exc)
                self.state.fail(
                    drive_file.file_id,
                    error_class=error_class,
                    error_summary=summary,
                )
                print(
                    f"migration: failed name={safe_drive_filename(drive_file)} "
                    f"error={error_class}"
                )

            if progress_every and processed % progress_every == 0:
                self._print_migration_summary(files, processed)

        summary = self.state.summary(
            [drive_file.file_id for drive_file in files]
        )
        return MigrationSummary(
            completed=summary.completed,
            imported=summary.imported,
            already_present=summary.already_present,
            quarantined_doc=summary.quarantined_doc,
            failed=summary.failed,
            remaining=summary.remaining,
            processed_this_run=processed,
        )

    def _print_migration_summary(
        self,
        files: Sequence[DriveFile],
        processed: int,
    ) -> None:
        summary = self.state.summary(
            [drive_file.file_id for drive_file in files]
        )
        print(
            "migration: "
            f"completed={summary.completed} imported={summary.imported} "
            f"already_present={summary.already_present} "
            f"quarantined_doc={summary.quarantined_doc} "
            f"failed={summary.failed} remaining={summary.remaining} "
            f"processed_this_run={processed}"
        )


def _print_inventory(files: Sequence[DriveFile]) -> None:
    counts = inventory_counts(files)
    print(
        "inventory: "
        f"total={counts['total']} pdf={counts['pdf']} "
        f"docx={counts['docx']} doc={counts['doc']}"
    )


def _print_final(summary: MigrationSummary) -> None:
    print(
        "migration: "
        f"completed={summary.completed} imported={summary.imported} "
        f"already_present={summary.already_present} "
        f"quarantined_doc={summary.quarantined_doc} "
        f"failed={summary.failed} remaining={summary.remaining}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory and resumably import CVs from a Shared Drive."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
    )
    parser.add_argument("--max-files", type=int)
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_files is not None and args.max_files < 1:
        raise SystemExit("--max-files must be positive")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be positive")

    try:
        with ImporterLock(args.state_file), BulkImportState(
            args.state_file
        ) as state:
            files = list_shared_drive_files()
            state.upsert_inventory(files)
            _print_inventory(files)
            if args.inventory_only:
                return 0

            importer = GoogleDriveBulkImporter(state=state)
            summary = importer.run(
                files,
                max_files=args.max_files,
                max_attempts=args.max_attempts,
            )
            _print_final(summary)
            if args.max_files is None and summary.failed:
                return 1
            return 0
    except ImporterAlreadyRunningError as exc:
        print(f"bulk import unavailable: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("bulk import interrupted; resume state is durable", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
