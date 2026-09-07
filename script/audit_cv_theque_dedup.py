#!/usr/bin/env python3
"""
Audit CV_Theque + candidates.profiles for duplicates and seniority misplacement.

Keeps one canonical copy per (profile, candidate identity) in the folder that
matches computed seniority from annees_experience. Soft-deletes duplicate DB
rows and reassigns offer appearances when safe.

Usage:
  python script/audit_cv_theque_dedup.py              # dry-run report
  python script/audit_cv_theque_dedup.py --apply      # execute fixes
  python script/audit_cv_theque_dedup.py --profiles DevOps,FullStack
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / "config" / ".env")

import psycopg2
import psycopg2.extras

from script.experience_years import enrich_annees_experience
from script.staging_watcher import StagingWatcherSFTP, _seniority_from_years

KNOWN_SENIORITIES = ("Junior", "Confirme", "Senior", "Expert")
SFTP_ROOT = os.getenv("SFTP_ROOT_PATH", "/sftp/cv_tech/files/CV_Theque").rstrip("/")


def _ascii_lower(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", _ascii_lower(name or ""))
    return " ".join(cleaned.split())


def _stem_key(filename: str) -> str:
    return _ascii_lower(Path(filename).stem)


@dataclass
class CvLocation:
    profile: str
    seniority: str
    json_path: str
    original_path: Optional[str]
    stem: str
    full_name: str
    email: str
    annees_experience: str
    computed_seniority: Optional[str]
    aligned: bool


@dataclass
class Action:
    kind: str  # keep | delete_sftp | move_sftp | soft_delete_db | merge_db
    detail: str
    payload: dict = field(default_factory=dict)


def _connect_db():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _read_remote_json(sftp: StagingWatcherSFTP, remote_path: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        if not sftp.sftp and not sftp.connect():
            raise RuntimeError(sftp.last_error or "SFTP connect failed")
        sftp.sftp.get(remote_path, tmp_path)
        return json.loads(Path(tmp_path).read_text(encoding="utf-8"))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _candidate_identity(profile: str, data: dict, stem: str) -> str:
    info = data.get("informations_personnelles") or {}
    email = _ascii_lower(str(info.get("email") or "").strip())
    if email and "@" in email:
        return f"{profile}|email:{email}"
    name = _normalize_name(str(info.get("nom_complet") or ""))
    if name and name != "inconnu":
        return f"{profile}|name:{name}"
    return f"{profile}|stem:{stem}"


def _infer_seniority(data: dict) -> tuple[str, Optional[str]]:
    enriched = json.loads(json.dumps(data))  # copy
    enrich_annees_experience(enriched)
    annees = str((enriched.get("profil_resume") or {}).get("annees_experience") or "").strip()
    return annees, _seniority_from_years(annees)


def _find_original(sftp: StagingWatcherSFTP, profile: str, seniority: str, stem: str) -> Optional[str]:
    originals_dir = f"{SFTP_ROOT}/{profile}/{seniority}/originals"
    if not sftp.exists(originals_dir):
        return None
    try:
        for name in sftp.sftp.listdir(originals_dir):
            if _stem_key(name) == _stem_key(stem):
                return f"{originals_dir}/{name}"
    except Exception:
        return None
    return None


def scan_cv_theque(sftp: StagingWatcherSFTP, profiles: list[str]) -> list[CvLocation]:
    rows: list[CvLocation] = []
    if not sftp.sftp and not sftp.connect():
        raise RuntimeError(sftp.last_error or "SFTP connect failed")

    for profile in profiles:
        profile_path = f"{SFTP_ROOT}/{profile}"
        if not sftp.exists(profile_path):
            print(f"[warn] profile missing: {profile}")
            continue
        for seniority in KNOWN_SENIORITIES:
            extracted_dir = f"{profile_path}/{seniority}/extracted"
            if not sftp.exists(extracted_dir):
                continue
            for fname in sorted(sftp.sftp.listdir(extracted_dir)):
                if not fname.lower().endswith(".json"):
                    continue
                json_path = f"{extracted_dir}/{fname}"
                try:
                    data = _read_remote_json(sftp, json_path)
                except Exception as exc:
                    print(f"[warn] cannot read {json_path}: {exc}")
                    continue
                annees, computed = _infer_seniority(data)
                info = data.get("informations_personnelles") or {}
                stem = Path(fname).stem
                orig = _find_original(sftp, profile, seniority, stem)
                rows.append(CvLocation(
                    profile=profile,
                    seniority=seniority,
                    json_path=json_path,
                    original_path=orig,
                    stem=stem,
                    full_name=str(info.get("nom_complet") or stem),
                    email=str(info.get("email") or ""),
                    annees_experience=annees,
                    computed_seniority=computed,
                    aligned=(computed == seniority) if computed else False,
                ))
    return rows


def plan_sftp_actions(locations: list[CvLocation]) -> list[Action]:
    actions: list[Action] = []
    by_identity: dict[str, list[CvLocation]] = defaultdict(list)
    for loc in locations:
        # Re-read identity from stored fields
        key = _candidate_identity(
            loc.profile,
            {
                "informations_personnelles": {
                    "email": loc.email,
                    "nom_complet": loc.full_name,
                }
            },
            loc.stem,
        )
        by_identity[key].append(loc)

    for key, group in by_identity.items():
        if len(group) == 1:
            loc = group[0]
            if loc.computed_seniority and loc.seniority != loc.computed_seniority:
                target = loc.computed_seniority
                actions.append(Action(
                    kind="move_sftp",
                    detail=f"{loc.full_name}: {loc.seniority} -> {target}",
                    payload={
                        "profile": loc.profile,
                        "from_seniority": loc.seniority,
                        "to_seniority": target,
                        "json_path": loc.json_path,
                        "original_path": loc.original_path,
                        "stem": loc.stem,
                    },
                ))
            else:
                actions.append(Action(
                    kind="keep",
                    detail=f"{loc.full_name} @ {loc.profile}/{loc.seniority}",
                    payload={"json_path": loc.json_path},
                ))
            continue

        # Multiple copies — pick canonical in computed seniority folder (newest path order)
        with_target = [g for g in group if g.computed_seniority]
        target_seniority = with_target[0].computed_seniority if with_target else group[0].seniority
        canonical = None
        for g in group:
            if g.seniority == target_seniority:
                canonical = g
                break
        if canonical is None:
            canonical = sorted(group, key=lambda x: (x.seniority, x.json_path))[0]
            target_seniority = canonical.computed_seniority or canonical.seniority

        if canonical.computed_seniority and canonical.seniority != canonical.computed_seniority:
            actions.append(Action(
                kind="move_sftp",
                detail=f"{canonical.full_name}: {canonical.seniority} -> {canonical.computed_seniority} (canonical)",
                payload={
                    "profile": canonical.profile,
                    "from_seniority": canonical.seniority,
                    "to_seniority": canonical.computed_seniority,
                    "json_path": canonical.json_path,
                    "original_path": canonical.original_path,
                    "stem": canonical.stem,
                },
            ))
            keep_path = (
                f"{SFTP_ROOT}/{canonical.profile}/{canonical.computed_seniority}"
                f"/extracted/{canonical.stem}.json"
            )
        else:
            actions.append(Action(
                kind="keep",
                detail=f"{canonical.full_name} @ {canonical.profile}/{canonical.seniority} (canonical)",
                payload={"json_path": canonical.json_path},
            ))
            keep_path = canonical.json_path

        for g in group:
            if g.json_path == canonical.json_path:
                continue
            actions.append(Action(
                kind="delete_sftp",
                detail=f"duplicate {g.full_name}: remove {g.profile}/{g.seniority}",
                payload={
                    "json_path": g.json_path,
                    "original_path": g.original_path,
                    "keep_path": keep_path,
                },
            ))
    return actions


def scan_db_duplicates(cur) -> list[dict]:
    cur.execute(
        """
        SELECT cv_filename, profile,
               array_agg(id::text ORDER BY updated_at DESC) AS ids,
               array_agg(seniority ORDER BY updated_at DESC) AS seniorities,
               array_agg(cv_sftp_path ORDER BY updated_at DESC) AS paths,
               COUNT(*) AS cnt
        FROM candidates.profiles
        WHERE deleted_at IS NULL AND profile IS NOT NULL
        GROUP BY cv_filename, profile
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        """
    )
    return [dict(r) for r in cur.fetchall()]


def plan_db_actions(cur, sftp_keep_paths: set[str]) -> list[Action]:
    actions: list[Action] = []
    for row in scan_db_duplicates(cur):
        ids = row["ids"]
        paths = row["paths"]
        seniorities = row["seniorities"]
        keep_id = ids[0]
        for i, path in enumerate(paths):
            if path in sftp_keep_paths:
                keep_id = ids[i]
                break
        for dup_id in ids:
            if dup_id == keep_id:
                continue
            actions.append(Action(
                kind="merge_db",
                detail=f"soft-delete duplicate profile {dup_id} -> keep {keep_id}",
                payload={"duplicate_id": dup_id, "canonical_id": keep_id},
            ))
    return actions


def _apply_move(sftp: StagingWatcherSFTP, payload: dict) -> None:
    profile = payload["profile"]
    to_sen = payload["to_seniority"]
    stem = payload["stem"]
    dst_json = f"{SFTP_ROOT}/{profile}/{to_sen}/extracted/{stem}.json"
    sftp.makedirs(f"{SFTP_ROOT}/{profile}/{to_sen}/extracted")
    sftp.makedirs(f"{SFTP_ROOT}/{profile}/{to_sen}/originals")
    if sftp.exists(dst_json):
        sftp.remove(dst_json)
    sftp.move(payload["json_path"], dst_json)
    orig = payload.get("original_path")
    if orig and sftp.exists(orig):
        orig_name = orig.rsplit("/", 1)[-1]
        dst_orig = f"{SFTP_ROOT}/{profile}/{to_sen}/originals/{orig_name}"
        if sftp.exists(dst_orig):
            sftp.remove(dst_orig)
        sftp.move(orig, dst_orig)


def _apply_delete(sftp: StagingWatcherSFTP, payload: dict) -> None:
    sftp.remove(payload["json_path"])
    if payload.get("original_path"):
        sftp.remove(payload["original_path"])


def _apply_merge_db(cur, payload: dict) -> None:
    dup_id = payload["duplicate_id"]
    canon_id = payload["canonical_id"]
    cur.execute(
        """
        UPDATE candidates.offer_appearances oa
        SET candidate_id = %s::uuid, updated_at = NOW()
        WHERE candidate_id = %s::uuid
          AND NOT EXISTS (
            SELECT 1 FROM candidates.offer_appearances x
            WHERE x.candidate_id = %s::uuid AND x.offer_id = oa.offer_id
          )
        """,
        (canon_id, dup_id, canon_id),
    )
    cur.execute(
        "DELETE FROM candidates.offer_appearances WHERE candidate_id = %s::uuid",
        (dup_id,),
    )
    cur.execute(
        "UPDATE candidates.notes SET candidate_id = %s::uuid WHERE candidate_id = %s::uuid",
        (canon_id, dup_id),
    )
    cur.execute(
        """
        UPDATE candidates.profiles
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE id = %s::uuid AND deleted_at IS NULL
        """,
        (dup_id,),
    )


def _upsert_canonical_from_sftp(cur, sftp: StagingWatcherSFTP, json_path: str) -> None:
    from service.candidate_store import upsert_candidate

    parts = json_path.replace("\\", "/").split("/")
    try:
        idx = parts.index("CV_Theque") if "CV_Theque" in parts else -1
        if idx < 0:
            # path like /sftp/cv_tech/files/CV_Theque/Profile/Senior/extracted/x.json
            profile = parts[-4]
            seniority = parts[-3]
        else:
            profile = parts[idx + 1]
            seniority = parts[idx + 2]
    except (IndexError, ValueError):
        return
    data = _read_remote_json(sftp, json_path)
    upsert_candidate(json_path, profile, seniority, data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and dedupe CV_Theque + DB profiles")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (default: dry-run)")
    parser.add_argument("--sftp-only", action="store_true", help="Skip database steps")
    parser.add_argument(
        "--profiles",
        default="",
        help="Comma-separated profile filter (default: all SFTP profiles)",
    )
    args = parser.parse_args()
    dry_run = not args.apply

    sftp = StagingWatcherSFTP(
        host=os.getenv("SFTP_HOST", ""),
        username=os.getenv("SFTP_USER", ""),
        password=os.getenv("SFTP_PASSWORD", ""),
        port=int(os.getenv("SFTP_PORT", "22")),
        root_path=SFTP_ROOT,
    )

    try:
        if args.profiles.strip():
            profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
        else:
            profiles = sftp.list_profiles()
        print(f"Scanning {len(profiles)} profile(s) on {SFTP_ROOT} …")
        locations = scan_cv_theque(sftp, profiles)
        print(f"Found {len(locations)} extracted JSON file(s)")

        misaligned = [l for l in locations if l.computed_seniority and not l.aligned]
        empty_years = [l for l in locations if not l.annees_experience]
        print(f"  Seniority misaligned: {len(misaligned)}")
        print(f"  Empty annees_experience (after enrich): {len(empty_years)}")

        sftp_actions = plan_sftp_actions(locations)
        keep_paths = {
            a.payload["json_path"]
            for a in sftp_actions
            if a.kind == "keep"
        }
        for a in sftp_actions:
            if a.kind == "move_sftp":
                p = a.payload
                keep_paths.add(
                    f"{SFTP_ROOT}/{p['profile']}/{p['to_seniority']}/extracted/{p['stem']}.json"
                )

        print("\n--- SFTP actions ---")
        for a in sftp_actions:
            if a.kind == "keep":
                continue
            print(f"  [{a.kind}] {a.detail}")

        db_actions: list[Action] = []
        conn = None
        if not args.sftp_only:
            try:
                conn = _connect_db()
            except Exception as exc:
                print(f"\n[warn] Database unavailable ({exc}); SFTP-only apply.")
            if conn is not None:
                with conn.cursor() as cur:
                    db_dups = scan_db_duplicates(cur)
                    print(f"\nDB duplicate rows (filename+profile): {len(db_dups)}")
                    db_actions = plan_db_actions(cur, keep_paths)
                    print("\n--- DB actions ---")
                    for a in db_actions:
                        print(f"  [{a.kind}] {a.detail}")

        if dry_run:
            print("\nDry-run only. Re-run with --apply to execute.")
            return 0

        for a in sftp_actions:
            if a.kind == "move_sftp":
                _apply_move(sftp, a.payload)
            elif a.kind == "delete_sftp":
                _apply_delete(sftp, a.payload)

        if conn is not None:
            with conn.cursor() as cur:
                for a in sftp_actions:
                    if a.kind == "keep":
                        _upsert_canonical_from_sftp(cur, sftp, a.payload["json_path"])
                    elif a.kind == "move_sftp":
                        p = a.payload
                        new_path = (
                            f"{SFTP_ROOT}/{p['profile']}/{p['to_seniority']}"
                            f"/extracted/{p['stem']}.json"
                        )
                        _upsert_canonical_from_sftp(cur, sftp, new_path)
                for a in db_actions:
                    if a.kind == "merge_db":
                        _apply_merge_db(cur, a.payload)
                conn.commit()
            conn.close()
            print("\nApplied SFTP + DB successfully.")
        else:
            print("\nApplied SFTP actions successfully (database skipped).")
        return 0
    finally:
        sftp.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
