from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO, Iterable, Optional
from uuid import uuid4


DEFAULT_CV_STORAGE_ROOT = Path("/sftp/cv_tech/files")
DEFAULT_CV_LIBRARY_ROOT = DEFAULT_CV_STORAGE_ROOT / "CV_Theque"
DEFAULT_STAGING_PATH = DEFAULT_CV_STORAGE_ROOT / "staging"


class StoragePathError(ValueError):
    """Raised when a path would escape the configured storage root."""


class StagingWriteError(OSError):
    """Raised when an upload cannot be safely published into staging."""


def normalize_profile(profile: str) -> str:
    profile_mapping = {
        "full_stack": "FullStack",
        "fullstack": "FullStack",
        "full stack": "FullStack",
        "devops": "DevOps",
        "data_analyst": "Data_Analyst",
        "data scientist": "Data_Scientist",
        "data_scientist": "Data_Scientist",
        "data engineer": "Data_Engineer",
        "data_engineer": "Data_Engineer",
        "backend": "Backend",
        "frontend": "Frontend",
        "mobile": "Mobile",
        "qa": "QA",
        "product_manager": "Product_Manager",
        "product manager": "Product_Manager",
        "scrum_master": "Scrum_Master",
        "scrum master": "Scrum_Master",
        "project_manager": "Project_Manager",
        "project manager": "Project_Manager",
        "business_analyst": "BusinessAnalyst",
        "business analyst": "BusinessAnalyst",
        "businessanalyst": "BusinessAnalyst",
        "moa": "BusinessAnalyst",
        "analyse_fonctionnelle": "BusinessAnalyst",
        "functional_analyst": "BusinessAnalyst",
        "chef_de_projet_fonctionnel": "BusinessAnalyst",
    }
    key = profile.strip().lower().replace("-", "_").replace(" ", "_")
    return profile_mapping.get(key, profile.strip().title().replace(" ", "_"))


def normalize_seniority(seniority: str) -> str:
    seniority_mapping = {
        "junior": "Junior",
        "confirme": "Confirme",
        "confirmé": "Confirme",
        "confirmée": "Confirme",
        "confirmed": "Confirme",
        "intermédiaire": "Confirme",
        "intermediaire": "Confirme",
        "senior": "Senior",
        "expert": "Expert",
    }
    key = seniority.strip().lower()
    return seniority_mapping.get(key, seniority.strip().title())


def sanitize_filename_component(filename: str | None) -> str:
    """Return a safe single filename component while preserving Unicode names."""
    raw = filename or ""
    if (
        not raw
        or raw in {".", ".."}
        or raw.startswith(".")
        or len(raw) > 255
        or "/" in raw
        or "\\" in raw
        or Path(raw).is_absolute()
        or Path(raw).anchor
        or PurePosixPath(raw).is_absolute()
        or PureWindowsPath(raw).is_absolute()
        or PureWindowsPath(raw).drive
    ):
        raise StoragePathError("Unsafe filename")
    return raw


def validate_staging_component(value: str, *, field_name: str) -> str:
    """Validate profile/seniority values before canonicalization."""
    raw = (value or "").strip()
    if (
        not raw
        or raw in {".", ".."}
        or "/" in raw
        or "\\" in raw
        or Path(raw).is_absolute()
        or Path(raw).anchor
        or PurePosixPath(raw).is_absolute()
        or PureWindowsPath(raw).is_absolute()
        or PureWindowsPath(raw).drive
        or ":" in raw
    ):
        raise StoragePathError(f"Unsafe {field_name}")
    return raw


def _assert_single_component(component: str, *, field_name: str) -> str:
    if (
        not component
        or component in {".", ".."}
        or "/" in component
        or "\\" in component
        or Path(component).is_absolute()
        or Path(component).anchor
        or PurePosixPath(component).is_absolute()
        or PureWindowsPath(component).is_absolute()
        or PureWindowsPath(component).drive
        or ":" in component
    ):
        raise StoragePathError(f"Unsafe canonical {field_name}")
    return component


def canonical_staging_profile(profile: str) -> str:
    raw = validate_staging_component(profile, field_name="profile")
    return _assert_single_component(normalize_profile(raw), field_name="profile")


def canonical_staging_seniority(seniority: str) -> str:
    raw = validate_staging_component(seniority, field_name="seniority")
    return _assert_single_component(normalize_seniority(raw), field_name="seniority")


def _resolve_under_staging(staging_root: Path | str, path: Path) -> Path:
    root = Path(staging_root).resolve(strict=False)
    resolved = path.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise StoragePathError("Path escapes staging")
    return resolved


def resolve_staging_upload_path(
    *,
    staging_root: Path | str,
    filename: str,
    profile: Optional[str] = None,
    seniority: Optional[str] = None,
) -> Path:
    """Resolve a CV upload destination that is confined to the staging tree."""
    safe_name = sanitize_filename_component(filename)
    root = Path(staging_root)
    parts: list[str] = []
    if profile:
        parts.append(canonical_staging_profile(profile))
    if seniority:
        if not profile:
            raise StoragePathError("Seniority requires profile")
        parts.append(canonical_staging_seniority(seniority))
    candidate = root.joinpath(*parts, safe_name)
    return _resolve_under_staging(root, candidate)


def _unique_no_overwrite_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def atomic_write_staging_upload(
    *,
    staging_root: Path | str,
    filename: str,
    source: BinaryIO,
    max_bytes: int,
    profile: Optional[str] = None,
    seniority: Optional[str] = None,
    unique: bool = True,
    chunk_size: int = 1024 * 1024,
) -> tuple[Path, int]:
    """Stream a CV into staging via a hidden temp file, then publish atomically."""
    destination = resolve_staging_upload_path(
        staging_root=staging_root,
        filename=filename,
        profile=profile,
        seniority=seniority,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = Path(staging_root).resolve(strict=False)
    parent = destination.parent.resolve(strict=False)
    if parent != root and root not in parent.parents:
        raise StoragePathError("Staging destination parent escapes staging")
    if unique:
        destination = _unique_no_overwrite_path(destination)
    elif destination.exists():
        raise FileExistsError(destination)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.{uuid4().hex}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    tmp_path = Path(tmp_name)
    total = 0
    try:
        with os.fdopen(fd, "wb") as tmp:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise StagingWriteError("Upload exceeds configured limit")
                tmp.write(chunk)
            tmp.flush()
            os.fsync(tmp.fileno())

        while True:
            destination = _resolve_under_staging(staging_root, destination)
            try:
                os.link(tmp_path, destination)
                break
            except FileExistsError:
                if not unique:
                    raise
                destination = _unique_no_overwrite_path(destination)
            except OSError:
                if destination.exists():
                    if not unique:
                        raise FileExistsError(destination)
                    destination = _unique_no_overwrite_path(destination)
                    continue
                os.replace(tmp_path, destination)
                tmp_path = destination
                break

        if destination.stat().st_size != total:
            raise StagingWriteError("Staging write size mismatch")
        return destination, total
    finally:
        try:
            if tmp_path.exists() and tmp_path != destination:
                tmp_path.unlink()
        except OSError:
            pass


class LocalCVStorage:
    """Filesystem-backed storage for the mounted CV storage tree."""

    def __init__(
        self,
        storage_root: Path | str = DEFAULT_CV_STORAGE_ROOT,
        library_root: Path | str | None = None,
        staging_path: Path | str | None = None,
    ) -> None:
        self.storage_root = Path(storage_root)
        self.library_root = Path(library_root) if library_root else self.storage_root / "CV_Theque"
        self.staging_path = Path(staging_path) if staging_path else self.storage_root / "staging"
        self._allowed_roots = tuple(
            root.resolve(strict=False)
            for root in (self.storage_root, self.library_root, self.staging_path)
        )

    def resolve(self, path: Path | str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.storage_root / candidate
        resolved = candidate.resolve(strict=False)
        if not any(resolved == root or root in resolved.parents for root in self._allowed_roots):
            raise StoragePathError(f"Path escapes CV storage root: {path}")
        return resolved

    def relative_to_staging(self, path: Path | str) -> Path:
        resolved = self.resolve(path)
        try:
            rel = resolved.relative_to(self.staging_path.resolve(strict=False))
        except ValueError as exc:
            raise StoragePathError(f"Path is outside staging: {path}") from exc
        if any(part == ".." for part in rel.parts):
            raise StoragePathError(f"Unsafe staging path: {path}")
        return rel

    def list_files(
        self,
        root: Path | str,
        extensions: Optional[Iterable[str]] = None,
        ignored_dirs: Iterable[str] = (),
    ) -> list[Path]:
        directory = self.resolve(root)
        if not directory.exists():
            return []
        ext_set = {ext.lower() for ext in extensions} if extensions else None
        ignored = {name.lower() for name in ignored_dirs}
        files: list[Path] = []
        for child in directory.rglob("*"):
            try:
                rel = child.relative_to(directory)
            except ValueError:
                continue
            if any(part.lower() in ignored for part in rel.parts[:-1]):
                continue
            if child.is_file() and (ext_set is None or child.suffix.lower() in ext_set):
                files.append(child)
        return sorted(files)

    def exists(self, path: Path | str) -> bool:
        return self.resolve(path).exists()

    def read_bytes(self, path: Path | str) -> bytes:
        return self.resolve(path).read_bytes()

    def mkdirs(self, path: Path | str) -> Path:
        resolved = self.resolve(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def write_json(self, path: Path | str, payload: dict) -> Path:
        resolved = self.resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return resolved

    def copy(self, src: Path | str, dst: Path | str) -> Path:
        source = self.resolve(src)
        dest = self.resolve(dst)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return dest

    def move(self, src: Path | str, dst: Path | str) -> Path:
        source = self.resolve(src)
        dest = self.resolve(dst)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = self.unique_destination(dest)
        if not source.exists() and dest.exists():
            return dest
        shutil.move(str(source), str(dest))
        return dest

    def remove(self, path: Path | str) -> None:
        resolved = self.resolve(path)
        if resolved.exists():
            resolved.unlink()

    def unique_destination(self, path: Path | str) -> Path:
        resolved = self.resolve(path)
        if not resolved.exists():
            return resolved
        stem = resolved.stem
        suffix = resolved.suffix
        parent = resolved.parent
        index = 1
        while True:
            candidate = parent / f"{stem} ({index}){suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def store_extracted(self, profile: str, seniority: str, stem: str, payload: dict) -> Path:
        path = self.library_root / profile / seniority / "extracted" / f"{stem}.json"
        return self.write_json(path, payload)

    def store_original(self, source: Path | str, profile: str, seniority: str) -> Path:
        src = self.resolve(source)
        path = self.library_root / profile / seniority / "originals" / src.name
        return self.copy(src, self.unique_destination(path))
