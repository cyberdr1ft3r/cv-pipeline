#!/usr/bin/env python3
"""Backfill candidates.profiles.annees_experience from extracted CV JSON on SFTP."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / "config" / ".env")

import psycopg2
import psycopg2.extras

from script.audit_cv_theque_dedup import _read_remote_json
from script.staging_watcher import StagingWatcherSFTP
from service.candidate_store import _resolve_annees_experience, update_annees_experience


def _load_json_local(cv_sftp_path: str) -> dict | None:
    path = Path(cv_sftp_path)
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def main() -> int:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        print("DATABASE_URL is not set")
        return 1

    with psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, full_name, cv_sftp_path, annees_experience
                FROM candidates.profiles
                WHERE deleted_at IS NULL AND cv_sftp_path IS NOT NULL
                ORDER BY full_name
                """
            )
            rows = cur.fetchall()

    print(f"Candidates to process: {len(rows)}")

    sftp = StagingWatcherSFTP(
        host=os.getenv("SFTP_HOST", ""),
        username=os.getenv("SFTP_USER", ""),
        password=os.getenv("SFTP_PASSWORD", ""),
        port=int(os.getenv("SFTP_PORT", "22")),
        root_path=os.getenv("SFTP_ROOT_PATH", "/sftp/cv_tech/files/CV_Theque").rstrip("/"),
    )
    sftp_ok = sftp.connect()
    if not sftp_ok:
        print(f"[warn] SFTP unavailable ({sftp.last_error}); local mount only")

    updated = 0
    empty = 0
    failed = 0

    try:
        for row in rows:
            cid = row["id"]
            path = row["cv_sftp_path"]
            data = _load_json_local(path)
            if data is None and sftp_ok:
                try:
                    if sftp.exists(path):
                        data = _read_remote_json(sftp, path)
                except Exception as exc:
                    print(f"[fail] {row['full_name']}: {exc}")
                    failed += 1
                    continue
            if data is None:
                print(f"[skip] {row['full_name']}: JSON not found ({path})")
                failed += 1
                continue

            years = _resolve_annees_experience(data)
            if years != (row.get("annees_experience") or None):
                update_annees_experience(cid, years)
                updated += 1
                print(f"[ok] {row['full_name']}: {years!r}")
            elif years:
                print(f"[keep] {row['full_name']}: {years!r}")
            else:
                empty += 1
                print(f"[empty] {row['full_name']}: no computable years")
    finally:
        if sftp_ok:
            sftp.disconnect()

    print(f"\nDone: updated={updated} empty={empty} failed={failed} total={len(rows)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
