"""
script/backfill_candidates.py

Reads all extracted JSON files from CV_Theque on SFTP and upserts
candidate records in PostgreSQL. Idempotent — safe to run multiple times.

Usage:
    python script/backfill_candidates.py
    python script/backfill_candidates.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import stat as stat_module
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service.config  # noqa: F401 — loads config/.env

from service.candidate_store import get_candidate_by_cv_path, upsert_candidate
from service.sftp_loader import SFTPCVLoader

SFTP_ROOT_PATH = os.getenv("SFTP_ROOT_PATH", "/sftp/cv_tech/files/CV_Theque")


def _make_sftp() -> SFTPCVLoader:
    return SFTPCVLoader(
        host=os.getenv("SFTP_HOST", ""),
        username=os.getenv("SFTP_USER", ""),
        password=os.getenv("SFTP_PASSWORD", ""),
        port=int(os.getenv("SFTP_PORT", "22")),
        root_path=SFTP_ROOT_PATH,
    )


def _is_dir(sftp: SFTPCVLoader, path: str) -> bool:
    try:
        attr = sftp._require_sftp().stat(path)
        return stat_module.S_ISDIR(attr.st_mode)
    except Exception:
        return False


def _list_json_files(sftp: SFTPCVLoader) -> list[tuple[str, str, str]]:
    """Return list of (cv_sftp_path, profile, seniority) for every extracted JSON."""
    results: list[tuple[str, str, str]] = []
    if not sftp.connect():
        raise RuntimeError(f"SFTP connection failed: {sftp.last_error}")

    client = sftp._require_sftp()
    sftp._configure_operation_timeout()

    try:
        profile_entries = client.listdir(SFTP_ROOT_PATH)
    except FileNotFoundError as exc:
        raise RuntimeError(f"CV_Theque root not found: {SFTP_ROOT_PATH}") from exc

    for profile in profile_entries:
        profile_path = f"{SFTP_ROOT_PATH}/{profile}"
        if not _is_dir(sftp, profile_path):
            continue
        try:
            seniority_entries = client.listdir(profile_path)
        except Exception:
            continue
        for seniority in seniority_entries:
            seniority_path = f"{profile_path}/{seniority}"
            if not _is_dir(sftp, seniority_path):
                continue
            extracted_path = f"{seniority_path}/extracted"
            if not _is_dir(sftp, extracted_path):
                continue
            try:
                files = client.listdir(extracted_path)
            except Exception:
                continue
            for filename in files:
                if not filename.lower().endswith(".json"):
                    continue
                results.append((
                    f"{extracted_path}/{filename}",
                    profile,
                    seniority,
                ))
    return results


def run_backfill(dry_run: bool = False) -> dict:
    sftp = _make_sftp()
    files = _list_json_files(sftp)

    created = 0
    updated = 0
    failed = 0
    skipped = 0

    print(f"Fichiers JSON trouvés: {len(files)}")
    if dry_run:
        for path, profile, seniority in files:
            print(f"  [dry-run] {profile}/{seniority} — {Path(path).name}")
        sftp.disconnect()
        return {"created": 0, "updated": 0, "failed": 0, "skipped": 0, "dry_run": len(files)}

    client = sftp._require_sftp()
    for cv_sftp_path, profile, seniority in files:
        filename = Path(cv_sftp_path).name
        try:
            existing = get_candidate_by_cv_path(cv_sftp_path)
            with tempfile.TemporaryDirectory(prefix="backfill_") as tmp:
                local_path = Path(tmp) / filename
                client.get(cv_sftp_path, str(local_path))
                extracted_json = json.loads(local_path.read_text(encoding="utf-8"))

            full_name = (
                extracted_json.get("informations_personnelles", {}).get("nom_complet")
                or filename
            )
            upsert_candidate(
                cv_sftp_path=cv_sftp_path,
                profile=profile,
                seniority=seniority,
                extracted_json=extracted_json,
            )
            if existing:
                updated += 1
                print(f"[MAJ] {full_name} ({profile}/{seniority})")
            else:
                created += 1
                print(f"[OK] {full_name} ({profile}/{seniority})")
        except Exception as exc:
            failed += 1
            print(f"[ERREUR] {filename} - {exc}")

    sftp.disconnect()
    print(
        f"\nBackfill terminé: {created} créés, "
        f"{updated} mis à jour, {failed} erreurs"
    )
    return {"created": created, "updated": updated, "failed": failed, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill candidates from CV_Theque SFTP")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List JSON files without inserting into the database",
    )
    args = parser.parse_args()

    required = ("SFTP_HOST", "SFTP_USER", "SFTP_PASSWORD", "DATABASE_URL")
    missing = [v for v in required if not os.getenv(v)]
    if missing and not args.dry_run:
        print(f"Variables manquantes: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    stats = run_backfill(dry_run=args.dry_run)
    if stats.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
