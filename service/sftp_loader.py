from __future__ import annotations

from pathlib import Path
from typing import Optional

from service.cv_storage import LocalCVStorage, normalize_profile, normalize_seniority
from service.logging_config import app_logger
from service import config  # noqa: F401 - load environment files
from script.storage_paths import CV_THEQUE_DIR


class LocalCVLoader:
    """Compatibility wrapper for CV_Theque filesystem access.

    The historical name of several database fields still says ``sftp``. Runtime
    access is local-only: files are read from the mounted storage tree.
    """

    _normalize_profile = staticmethod(normalize_profile)
    _normalize_seniority = staticmethod(normalize_seniority)

    def __init__(
        self,
        root_path: str | Path = CV_THEQUE_DIR,
        stdout_log: Optional[Path] = None,
        stderr_log: Optional[Path] = None,
        **_legacy_kwargs: object,
    ) -> None:
        self.root_path = Path(root_path)
        self.stdout_log = stdout_log
        self.stderr_log = stderr_log
        storage_root = self.root_path.parent if self.root_path.name == "CV_Theque" else self.root_path
        self.storage = LocalCVStorage(storage_root=storage_root, library_root=self.root_path)
        self.last_error: Optional[str] = None

    def _log(self, message: str) -> None:
        if self.stdout_log:
            self.stdout_log.parent.mkdir(parents=True, exist_ok=True)
            with self.stdout_log.open("a", encoding="utf-8") as f:
                f.write(f"[CV_STORAGE] {message}\n")
        else:
            app_logger.info("[CV_STORAGE] %s", message)

    def _log_warning(self, message: str) -> None:
        if self.stderr_log:
            self.stderr_log.parent.mkdir(parents=True, exist_ok=True)
            with self.stderr_log.open("a", encoding="utf-8") as f:
                f.write(f"[CV_STORAGE] WARNING: {message}\n")
        else:
            app_logger.warning("[CV_STORAGE] %s", message)

    def connect(self) -> bool:
        self.last_error = None
        try:
            self.root_path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def disconnect(self) -> None:
        return None

    def is_connected(self) -> bool:
        return True

    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def makedirs(self, path: str | Path) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    def upload(self, local_path: Path, remote_path: str | Path) -> None:
        self.storage.copy(local_path, remote_path)

    def move(self, src_path: str | Path, dst_path: str | Path) -> None:
        self.storage.move(src_path, dst_path)

    def remove(self, path: str | Path) -> None:
        target = Path(path)
        if target.exists():
            target.unlink()

    def rmtree(self, path: str | Path) -> None:
        import shutil

        target = Path(path)
        if target.exists():
            shutil.rmtree(target)

    def list_profiles(self) -> list[str]:
        try:
            if not self.root_path.exists():
                return []
            return sorted(p.name for p in self.root_path.iterdir() if p.is_dir())
        except OSError as exc:
            self.last_error = str(exc)
            return []

    def list_seniority_levels(self, profile: str) -> list[str]:
        profile_path = self.root_path / normalize_profile(profile)
        try:
            if not profile_path.exists():
                return []
            return sorted(p.name for p in profile_path.iterdir() if p.is_dir())
        except OSError as exc:
            self.last_error = str(exc)
            return []

    def load_cvs(
        self,
        profile: str,
        seniority: str,
        local_dest_dir: Path,
        max_retries: int = 3,
    ) -> tuple[int, Optional[str]]:
        del max_retries
        profile_normalized = normalize_profile(profile)
        seniority_normalized = normalize_seniority(seniority)
        src_dir = self.root_path / profile_normalized / seniority_normalized / "extracted"
        if not src_dir.is_dir():
            return 0, f"CV library path not found: {src_dir}"
        json_files = sorted(p for p in src_dir.glob("*.json") if p.is_file())
        if not json_files:
            return 0, f"No JSON files found in {src_dir}"
        local_dest_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for src in json_files:
            self.storage.copy(src, local_dest_dir / src.name)
            count += 1
        return count, None

    def __enter__(self):
        if not self.connect():
            raise RuntimeError(self.last_error or "CV storage unavailable")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def get_cv_loader(stdout_log: Optional[Path] = None, stderr_log: Optional[Path] = None) -> LocalCVLoader:
    return LocalCVLoader(stdout_log=stdout_log, stderr_log=stderr_log)


def get_data_loader(stdout_log: Optional[Path] = None, stderr_log: Optional[Path] = None) -> LocalCVLoader:
    from script.storage_paths import DATA_ROOT

    return LocalCVLoader(root_path=DATA_ROOT, stdout_log=stdout_log, stderr_log=stderr_log)


# Backward-compatible import aliases. Do not use for new code.
SFTPCVLoader = LocalCVLoader
get_sftp_loader = get_cv_loader
get_sftp_data_loader = get_data_loader
