#!/usr/bin/env python3
"""List CVs where enrich_annees_experience still leaves annees_experience empty."""
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

from script.audit_cv_theque_dedup import (
    KNOWN_SENIORITIES,
    SFTP_ROOT,
    _infer_seniority,
    _read_remote_json,
)
from script.experience_years import (
    _experience_like_records,
    _is_internship,
    _parse_date_range,
    _parse_duree_months,
    _total_months_from_experiences,
    compute_annees_experience_from_cv,
    enrich_annees_experience,
)
from script.staging_watcher import StagingWatcherSFTP


def diagnose_record(exp: dict) -> dict:
    dates = str(exp.get("dates", "")).strip()
    duree = str(exp.get("duree", "")).strip()
    period = _parse_date_range(dates) if dates else None
    duree_m = _parse_duree_months(duree) if duree else None
    return {
        "titre": str(exp.get("titre_poste", ""))[:60],
        "type_contrat": str(exp.get("type_contrat", "")),
        "dates": dates,
        "duree": duree,
        "internship": _is_internship(exp),
        "parsed_range": f"{period[0]} -> {period[1]}" if period else None,
        "parsed_duree_months": duree_m,
    }


def main() -> int:
    sftp = StagingWatcherSFTP(
        host=os.getenv("SFTP_HOST", ""),
        username=os.getenv("SFTP_USER", ""),
        password=os.getenv("SFTP_PASSWORD", ""),
        port=int(os.getenv("SFTP_PORT", "22")),
        root_path=SFTP_ROOT,
    )
    try:
        if not sftp.connect():
            print(sftp.last_error or "SFTP connect failed")
            return 1
        profiles = sftp.list_profiles()
        empty: list[dict] = []
        for profile in profiles:
            for seniority in KNOWN_SENIORITIES:
                extracted_dir = f"{SFTP_ROOT}/{profile}/{seniority}/extracted"
                if not sftp.exists(extracted_dir):
                    continue
                for fname in sorted(sftp.sftp.listdir(extracted_dir)):
                    if not fname.lower().endswith(".json"):
                        continue
                    json_path = f"{extracted_dir}/{fname}"
                    data = _read_remote_json(sftp, json_path)
                    annees, computed = _infer_seniority(data)
                    if annees:
                        continue
                    info = data.get("informations_personnelles") or {}
                    profil = data.get("profil_resume") or {}
                    records = _experience_like_records(data)
                    enriched = json.loads(json.dumps(data))
                    enrich_annees_experience(enriched)
                    empty.append({
                        "path": json_path,
                        "name": info.get("nom_complet") or Path(fname).stem,
                        "profile": profile,
                        "folder_seniority": seniority,
                        "llm_annees": profil.get("annees_experience", ""),
                        "computed": compute_annees_experience_from_cv(data),
                        "total_months": _total_months_from_experiences(records),
                        "exp_count": len(data.get("experiences_professionnelles") or []),
                        "proj_count": len(data.get("projets_realises") or []),
                        "records": [diagnose_record(r) for r in records[:12]],
                    })

        print(f"Empty annees_experience after enrich: {len(empty)}\n")
        for i, row in enumerate(empty, 1):
            print(f"--- {i}. {row['name']} ({row['profile']}/{row['folder_seniority']}) ---")
            print(f"  path: {row['path']}")
            print(f"  LLM annees: {row['llm_annees']!r}  computed: {row['computed']!r}  months: {row['total_months']}")
            print(f"  experiences: {row['exp_count']}  projets: {row['proj_count']}")
            records = row["records"]
            if not records:
                print("  (no date-bearing records)")
            for rec in records:
                flags = []
                if rec["internship"]:
                    flags.append("internship")
                if not rec["parsed_range"] and not rec["parsed_duree_months"]:
                    flags.append("UNPARSED")
                flag = f" [{', '.join(flags)}]" if flags else ""
                print(f"  - {rec['titre']!r} dates={rec['dates']!r} duree={rec['duree']!r}{flag}")
                if rec["parsed_range"]:
                    print(f"      -> range: {rec['parsed_range']}")
                if rec["parsed_duree_months"]:
                    print(f"      -> duree months: {rec['parsed_duree_months']}")
            print()
        return 0
    finally:
        sftp.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
