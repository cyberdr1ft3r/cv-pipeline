"""
service/candidate_store.py

PostgreSQL-backed store for candidates.profiles, candidates.notes,
and candidates.offer_appearances.
Schema defined in service/migrations/008_candidates_schema.sql
                 + service/migrations/009_ref_tables.sql.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()


def _connect() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL env var is not set.")
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _serialize_value(val: Any) -> Any:
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    return val


def _row_to_dict(row: dict) -> dict:
    return {k: _serialize_value(v) for k, v in dict(row).items()}


def _extract_personal_fields(extracted_json: dict) -> dict:
    ip = extracted_json.get("informations_personnelles") or {}
    return {
        "full_name": (ip.get("nom_complet") or "").strip() or "Inconnu",
        "email": ip.get("email") or None,
        "phone": ip.get("telephone") or ip.get("phone") or None,
        "location": ip.get("adresse") or None,
    }


def _resolve_annees_experience(extracted_json: dict) -> Optional[str]:
    """Return formatted years string from CV JSON (with date-based enrich fallback)."""
    try:
        from script.experience_years import enrich_annees_experience
    except ImportError:
        from experience_years import enrich_annees_experience

    data = json.loads(json.dumps(extracted_json))
    enrich_annees_experience(data)
    value = str((data.get("profil_resume") or {}).get("annees_experience") or "").strip()
    return value or None


_CANDIDATE_SELECT = """
    SELECT p.*,
           rp.code AS profile_code,
           rp.label_fr AS profile_label_fr,
           rs.code AS seniority_code,
           rs.label_fr AS seniority_label_fr
    FROM candidates.profiles p
    LEFT JOIN ref.profiles rp ON rp.id = p.profile_id
    LEFT JOIN ref.seniorities rs ON rs.id = p.seniority_id
"""


def _resolve_profile_id(cur, profile: Optional[str]) -> Optional[int]:
    if not profile:
        return None
    cur.execute(
        "SELECT id FROM ref.profiles WHERE LOWER(code) = LOWER(%s) LIMIT 1",
        (profile.strip(),),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _resolve_seniority_id(cur, seniority: Optional[str]) -> Optional[int]:
    if not seniority:
        return None
    cur.execute(
        "SELECT id FROM ref.seniorities WHERE LOWER(code) = LOWER(%s) LIMIT 1",
        (seniority.strip(),),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


_MAX_SKILL_NAME_LEN = 100


def _skill_name(item: Any) -> Optional[str]:
    if isinstance(item, str):
        name = item.strip()
    elif isinstance(item, dict):
        name = (item.get("nom") or item.get("name") or "").strip()
    else:
        return None
    if not name:
        return None
    if len(name) > _MAX_SKILL_NAME_LEN:
        name = name[:_MAX_SKILL_NAME_LEN].rstrip()
    return name or None


def _extract_skill_names(extracted_json: dict) -> List[str]:
    competences = extracted_json.get("competences") or {}
    names: list[str] = []
    seen: set[str] = set()
    for key in ("technologies", "methodologies_et_outils"):
        for item in competences.get(key) or []:
            name = _skill_name(item)
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
    return names


def _get_or_create_skill_id(cur, name: str) -> int:
    cur.execute(
        """
        INSERT INTO ref.skills (name, category)
        VALUES (%s, 'other')
        ON CONFLICT (name) DO NOTHING
        RETURNING id
        """,
        (name,),
    )
    row = cur.fetchone()
    if row:
        return int(row["id"])
    cur.execute("SELECT id FROM ref.skills WHERE name = %s LIMIT 1", (name,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Could not resolve skill id for {name!r}")
    return int(row["id"])


def _sync_candidate_skills(cur, candidate_id: str, extracted_json: dict) -> None:
    skill_names = _extract_skill_names(extracted_json)
    if not skill_names:
        return
    cur.execute(
        "DELETE FROM candidates.candidate_skills WHERE candidate_id = %s",
        (candidate_id,),
    )
    for name in skill_names:
        skill_id = _get_or_create_skill_id(cur, name)
        cur.execute(
            """
            INSERT INTO candidates.candidate_skills (candidate_id, skill_id, level)
            VALUES (%s, %s, 'known')
            ON CONFLICT (candidate_id, skill_id) DO NOTHING
            """,
            (candidate_id, skill_id),
        )


def _fetch_skills_for_candidates(cur, candidate_ids: List[str]) -> dict[str, list]:
    if not candidate_ids:
        return {}
    cur.execute(
        """
        SELECT cs.candidate_id, s.id, s.name, s.category, cs.level
        FROM candidates.candidate_skills cs
        JOIN ref.skills s ON s.id = cs.skill_id
        WHERE cs.candidate_id = ANY(%s::uuid[])
        ORDER BY s.name
        """,
        (candidate_ids,),
    )
    by_candidate: dict[str, list] = {}
    for row in cur.fetchall():
        cid = str(row["candidate_id"])
        by_candidate.setdefault(cid, []).append(_row_to_dict(row))
    return by_candidate


def _enrich_candidate(row: dict, skills: Optional[list] = None) -> dict:
    out = _row_to_dict(row)
    if skills is not None:
        out["skills"] = skills
    return out


def _find_existing_candidate_id(
    cur,
    cv_sftp_path: str,
    cv_filename: str,
    profile: Optional[str],
    full_name: str,
) -> Optional[str]:
    """Resolve one profile row when the same CV is reclassified to a new seniority path."""
    cur.execute(
        "SELECT id FROM candidates.profiles WHERE cv_sftp_path = %s AND deleted_at IS NULL LIMIT 1",
        (cv_sftp_path,),
    )
    row = cur.fetchone()
    if row:
        return str(row["id"])

    if profile:
        cur.execute(
            """
            SELECT id FROM candidates.profiles
            WHERE deleted_at IS NULL
              AND cv_filename = %s
              AND LOWER(profile) = LOWER(%s)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (cv_filename, profile),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"])

    if full_name and full_name != "Inconnu" and profile:
        cur.execute(
            """
            SELECT id FROM candidates.profiles
            WHERE deleted_at IS NULL
              AND LOWER(full_name) = LOWER(%s)
              AND LOWER(profile) = LOWER(%s)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (full_name, profile),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"])

    return None


def upsert_candidate(
    cv_sftp_path: str,
    profile: Optional[str],
    seniority: Optional[str],
    extracted_json: dict,
) -> str:
    """Insert or update a candidate profile keyed by cv_sftp_path. Returns candidate_id."""
    fields = _extract_personal_fields(extracted_json)
    annees_experience = _resolve_annees_experience(extracted_json)
    cv_filename = Path(cv_sftp_path).name
    with _connect() as conn:
        with conn.cursor() as cur:
            existing_id = _find_existing_candidate_id(
                cur, cv_sftp_path, cv_filename, profile, fields["full_name"],
            )
            profile_id = _resolve_profile_id(cur, profile)
            seniority_id = _resolve_seniority_id(cur, seniority)
            if existing_id:
                if profile:
                    cur.execute(
                        """
                        UPDATE candidates.profiles
                        SET deleted_at = NOW()
                        WHERE deleted_at IS NULL
                          AND cv_filename = %s
                          AND LOWER(profile) = LOWER(%s)
                          AND id <> %s::uuid
                        """,
                        (cv_filename, profile, existing_id),
                    )
                cur.execute(
                    """
                    UPDATE candidates.profiles
                    SET cv_filename = %s,
                        cv_sftp_path = %s,
                        profile = COALESCE(%s, profile),
                        seniority = COALESCE(%s, seniority),
                        profile_id = COALESCE(%s, profile_id),
                        seniority_id = COALESCE(%s, seniority_id),
                        full_name = %s,
                        email = COALESCE(%s, email),
                        phone = COALESCE(%s, phone),
                        location = COALESCE(%s, location),
                        annees_experience = %s,
                        updated_at = NOW()
                    WHERE id = %s AND deleted_at IS NULL
                    RETURNING id
                    """,
                    (
                        cv_filename, cv_sftp_path, profile, seniority, profile_id, seniority_id,
                        fields["full_name"], fields["email"], fields["phone"], fields["location"],
                        annees_experience,
                        existing_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO candidates.profiles (
                        cv_filename, cv_sftp_path, profile, seniority,
                        profile_id, seniority_id,
                        full_name, email, phone, location,
                        annees_experience, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                    """,
                    (
                        cv_filename, cv_sftp_path, profile, seniority,
                        profile_id, seniority_id,
                        fields["full_name"], fields["email"], fields["phone"], fields["location"],
                        annees_experience,
                    ),
                )
            row = cur.fetchone()
            candidate_id = str(row["id"])
            _sync_candidate_skills(cur, candidate_id, extracted_json)
            conn.commit()
            return candidate_id


def get_candidate(candidate_id: str) -> Optional[dict]:
    sql = f"{_CANDIDATE_SELECT} WHERE p.id = %s AND p.deleted_at IS NULL LIMIT 1"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (candidate_id,))
            row = cur.fetchone()
            if not row:
                return None
            skills_map = _fetch_skills_for_candidates(cur, [candidate_id])
            return _enrich_candidate(row, skills_map.get(candidate_id, []))


def get_annees_experience_map(candidate_ids: List[str]) -> dict[str, str]:
    """Bulk lookup formatted years of experience for pipeline/matching enrichment."""
    if not candidate_ids:
        return {}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, annees_experience
                FROM candidates.profiles
                WHERE deleted_at IS NULL
                  AND id = ANY(%s::uuid[])
                  AND annees_experience IS NOT NULL
                  AND TRIM(annees_experience) <> ''
                """,
                (candidate_ids,),
            )
            return {
                str(row["id"]): row["annees_experience"]
                for row in cur.fetchall()
            }


def update_annees_experience(candidate_id: str, annees_experience: Optional[str]) -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE candidates.profiles
                SET annees_experience = %s, updated_at = NOW()
                WHERE id = %s::uuid AND deleted_at IS NULL
                """,
                (annees_experience, candidate_id),
            )
            conn.commit()


def get_candidate_by_cv_path(cv_sftp_path: str) -> Optional[dict]:
    sql = """
        SELECT * FROM candidates.profiles
        WHERE cv_sftp_path = %s AND deleted_at IS NULL
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (cv_sftp_path,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def get_candidate_by_cv_filename(cv_filename: str) -> Optional[dict]:
    """Resolve a candidate by JSON basename (matching pipeline uses cv_filename)."""
    if not cv_filename:
        return None
    basename = Path(cv_filename).name
    sql = """
        SELECT * FROM candidates.profiles
        WHERE deleted_at IS NULL
          AND (
            cv_filename = %s
            OR cv_filename = %s
            OR cv_filename ILIKE %s
            OR cv_sftp_path LIKE %s
            OR cv_sftp_path LIKE %s
          )
        ORDER BY updated_at DESC
        LIMIT 1
    """
    like_suffix = f"%/{basename}"
    like_suffix_raw = f"%/{cv_filename}"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (cv_filename, basename, basename, like_suffix, like_suffix_raw),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def get_candidate_by_id(candidate_id: str) -> Optional[dict]:
    sql = """
        SELECT * FROM candidates.profiles
        WHERE id = %s::uuid AND deleted_at IS NULL
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(candidate_id),))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def _normalize_person_name(name: str) -> str:
    import re
    import unicodedata

    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[''`´]", "", text)
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text


def resolve_candidate_from_matching_item(item: dict) -> Optional[dict]:
    """Best-effort candidate lookup from a matching/final result row."""
    candidate_id = item.get("candidate_id")
    if candidate_id:
        cand = get_candidate_by_id(str(candidate_id))
        if cand:
            return cand

    cv_filename = item.get("cv_filename")
    if cv_filename:
        cand = get_candidate_by_cv_filename(cv_filename)
        if cand:
            return cand

    email = (item.get("email") or "").strip()
    if email:
        sql = """
            SELECT * FROM candidates.profiles
            WHERE deleted_at IS NULL AND LOWER(email) = LOWER(%s)
            ORDER BY updated_at DESC
            LIMIT 1
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (email,))
                row = cur.fetchone()
                if row:
                    return _row_to_dict(row)

    name = item.get("candidate_name") or item.get("name")
    if name:
        cand = get_candidate_by_full_name(name)
        if cand:
            return cand
        norm = _normalize_person_name(name)
        if norm:
            sql = """
                SELECT * FROM candidates.profiles
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC
            """
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        d = _row_to_dict(row)
                        if _normalize_person_name(d.get("full_name") or "") == norm:
                            return d
    return None


def get_candidate_by_full_name(full_name: str) -> Optional[dict]:
    """Resolve a candidate by exact name (case-insensitive)."""
    sql = """
        SELECT * FROM candidates.profiles
        WHERE deleted_at IS NULL AND full_name ILIKE %s
        ORDER BY updated_at DESC
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (full_name,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


_LATEST_SCORE_SQL = """
    (
      SELECT CASE
        WHEN COALESCE(oa.final_score, oa.matching_score) IS NULL THEN NULL
        WHEN COALESCE(oa.final_score, oa.matching_score) <= 1
          THEN COALESCE(oa.final_score, oa.matching_score) * 100
        ELSE COALESCE(oa.final_score, oa.matching_score)
      END
      FROM candidates.offer_appearances oa
      WHERE oa.candidate_id = p.id
      ORDER BY oa.created_at DESC
      LIMIT 1
    )
"""


def list_candidates(
    profile: Optional[str] = None,
    seniority: Optional[str] = None,
    open_to_work: Optional[bool] = None,
    search: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Paginated candidate list with latest_score from most recent appearance."""
    conditions = ["p.deleted_at IS NULL"]
    params: list = []

    if profile:
        conditions.append("(p.profile = %s OR LOWER(rp.code) = LOWER(%s))")
        params.extend([profile, profile])
    if seniority:
        conditions.append(
            "(LOWER(p.seniority) = LOWER(%s) OR LOWER(rs.code) = LOWER(%s))"
        )
        params.extend([seniority, seniority])
    if open_to_work is not None:
        conditions.append("p.open_to_work = %s")
        params.append(open_to_work)
    if search:
        conditions.append("(p.full_name ILIKE %s OR p.email ILIKE %s)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern])
    if score_min is not None and score_max is not None:
        conditions.append(f"{_LATEST_SCORE_SQL} BETWEEN %s AND %s")
        params.extend([score_min, score_max])

    where = " AND ".join(conditions)
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM candidates.profiles p
        LEFT JOIN ref.profiles rp ON rp.id = p.profile_id
        LEFT JOIN ref.seniorities rs ON rs.id = p.seniority_id
        WHERE {where}
    """
    list_sql = f"""
        SELECT p.*,
               rp.code AS profile_code,
               rp.label_fr AS profile_label_fr,
               rs.code AS seniority_code,
               rs.label_fr AS seniority_label_fr,
               {_LATEST_SCORE_SQL} AS latest_score,
               (
                 SELECT oa.decision
                 FROM candidates.offer_appearances oa
                 WHERE oa.candidate_id = p.id
                 ORDER BY oa.created_at DESC
                 LIMIT 1
               ) AS latest_decision
        FROM candidates.profiles p
        LEFT JOIN ref.profiles rp ON rp.id = p.profile_id
        LEFT JOIN ref.seniorities rs ON rs.id = p.seniority_id
        WHERE {where}
        ORDER BY p.updated_at DESC
        LIMIT %s OFFSET %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            total = int(cur.fetchone()["total"])
            cur.execute(list_sql, params + [limit, offset])
            rows = cur.fetchall()
            ids = [str(r["id"]) for r in rows]
            skills_map = _fetch_skills_for_candidates(cur, ids)
            candidates = [
                _enrich_candidate(r, skills_map.get(str(r["id"]), []))
                for r in rows
            ]
            return {"total": total, "limit": limit, "offset": offset, "candidates": candidates}


def update_candidate(candidate_id: str, fields: dict) -> Optional[dict]:
    allowed = {
        "open_to_work", "availability_date", "current_salary",
        "expected_salary", "onboarded", "onboarding_date",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_candidate(candidate_id)

    set_parts = [f"{k} = %s" for k in updates]
    set_parts.append("updated_at = NOW()")
    sql = f"""
        UPDATE candidates.profiles
        SET {', '.join(set_parts)}
        WHERE id = %s AND deleted_at IS NULL
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, list(updates.values()) + [candidate_id])
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row) if row else None


def add_note(
    candidate_id: str,
    author_id: Optional[str],
    author_name: str,
    author_role: str,
    content: str,
    note_type: str = "general",
) -> dict:
    sql = """
        INSERT INTO candidates.notes (
            candidate_id, author_id, author_name, author_role, content, note_type
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (candidate_id, author_id, author_name, author_role, content, note_type),
            )
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row)


def get_notes(candidate_id: str) -> List[dict]:
    sql = """
        SELECT * FROM candidates.notes
        WHERE candidate_id = %s
        ORDER BY created_at DESC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (candidate_id,))
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_note(note_id: str) -> Optional[dict]:
    sql = "SELECT * FROM candidates.notes WHERE id = %s LIMIT 1"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (note_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def update_note(note_id: str, content: str, note_type: str) -> Optional[dict]:
    sql = """
        UPDATE candidates.notes
        SET content = %s, note_type = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (content, note_type, note_id))
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row) if row else None


def delete_note(note_id: str) -> bool:
    sql = "DELETE FROM candidates.notes WHERE id = %s RETURNING id"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (note_id,))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def upsert_appearance(
    candidate_id: str,
    offer_id: str,
    job_id: Optional[str],
    matching_score: Optional[float],
    final_score: Optional[float],
    rank: Optional[int],
) -> str:
    sql = """
        INSERT INTO candidates.offer_appearances (
            candidate_id, offer_id, job_id,
            matching_score, final_score, rank, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (candidate_id, offer_id)
        DO UPDATE SET
            job_id = COALESCE(EXCLUDED.job_id, candidates.offer_appearances.job_id),
            matching_score = COALESCE(EXCLUDED.matching_score, candidates.offer_appearances.matching_score),
            final_score = COALESCE(EXCLUDED.final_score, candidates.offer_appearances.final_score),
            rank = COALESCE(EXCLUDED.rank, candidates.offer_appearances.rank),
            updated_at = NOW()
        RETURNING id
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (candidate_id, offer_id, job_id, matching_score, final_score, rank),
            )
            row = cur.fetchone()
            conn.commit()
            return str(row["id"])


def update_appearance_final_scores(
    candidate_id: str,
    offer_id: str,
    final_score: Optional[float],
    rank: Optional[int],
) -> None:
    sql = """
        UPDATE candidates.offer_appearances
        SET final_score = COALESCE(%s, final_score),
            rank = COALESCE(%s, rank),
            updated_at = NOW()
        WHERE candidate_id = %s AND offer_id = %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (final_score, rank, candidate_id, offer_id))
            conn.commit()


def update_decision(
    appearance_id: str,
    decision: str,
    decision_notes: Optional[str],
    decision_by: Optional[str],
) -> Optional[dict]:
    sql = """
        UPDATE candidates.offer_appearances
        SET decision = %s,
            decision_notes = %s,
            decision_by = %s,
            decision_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (decision, decision_notes, decision_by, appearance_id))
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row) if row else None


_APPEARANCE_STATUS_JOINS = """
    LEFT JOIN ref.matching_statuses ms ON ms.id = oa.matching_status_id
    LEFT JOIN ref.final_statuses fs ON fs.id = oa.final_status_id
    LEFT JOIN ref.format_statuses fts ON fts.id = oa.format_status_id
"""


def _attach_phase_statuses(row: dict) -> dict:
    row["matching_status"] = {
        "code": row.pop("matching_status_code", None) or "en_attente",
        "label_fr": row.pop("matching_status_label_fr", None) or "En attente",
    }
    row["final_status"] = {
        "code": row.pop("final_status_code", None) or "en_attente",
        "label_fr": row.pop("final_status_label_fr", None) or "En attente",
    }
    row["format_status"] = {
        "code": row.pop("format_status_code", None) or "en_attente",
        "label_fr": row.pop("format_status_label_fr", None) or "En attente",
    }
    return row


def get_appearances(candidate_id: str) -> List[dict]:
    sql = f"""
        SELECT oa.*, jo.title AS offer_title,
               jo.created_at AS offer_created_at,
               jo.created_by AS recruiter_id,
               recruiter_u.full_name AS recruiter_name,
               ms.code AS matching_status_code,
               ms.label_fr AS matching_status_label_fr,
               fs.code AS final_status_code,
               fs.label_fr AS final_status_label_fr,
               fts.code AS format_status_code,
               fts.label_fr AS format_status_label_fr,
               (
                 SELECT COUNT(*)::int
                 FROM offers.offer_skills os
                 WHERE os.offer_id = oa.offer_id
               ) AS total_offer_skills,
               (
                 SELECT COUNT(*)::int
                 FROM candidates.candidate_skills cs
                 INNER JOIN offers.offer_skills os
                   ON os.skill_id = cs.skill_id AND os.offer_id = oa.offer_id
                 WHERE cs.candidate_id = oa.candidate_id
               ) AS matching_skills_count
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        LEFT JOIN auth.users recruiter_u ON recruiter_u.id = jo.created_by
        {_APPEARANCE_STATUS_JOINS}
        WHERE oa.candidate_id = %s
        ORDER BY oa.created_at DESC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (candidate_id,))
            return [_attach_phase_statuses(_row_to_dict(r)) for r in cur.fetchall()]


def get_offer_appearances(offer_id: str) -> List[dict]:
    sql = f"""
        SELECT oa.*,
               p.full_name, p.email, p.profile, p.seniority,
               rp.code AS profile_code, rp.label_fr AS profile_label_fr,
               rs.code AS seniority_code, rs.label_fr AS seniority_label_fr,
               p.expected_salary, p.cv_sftp_path, p.cv_filename,
               ms.code AS matching_status_code,
               ms.label_fr AS matching_status_label_fr,
               fs.code AS final_status_code,
               fs.label_fr AS final_status_label_fr,
               fts.code AS format_status_code,
               fts.label_fr AS format_status_label_fr,
               (
                 SELECT COUNT(*)::int
                 FROM candidates.offer_appearances oa2
                 WHERE oa2.candidate_id = oa.candidate_id
                   AND oa2.offer_id != oa.offer_id
               ) AS other_offers_count
        FROM candidates.offer_appearances oa
        JOIN candidates.profiles p ON p.id = oa.candidate_id
        LEFT JOIN ref.profiles rp ON rp.id = p.profile_id
        LEFT JOIN ref.seniorities rs ON rs.id = p.seniority_id
        {_APPEARANCE_STATUS_JOINS}
        WHERE oa.offer_id = %s AND p.deleted_at IS NULL
        ORDER BY oa.rank ASC NULLS LAST, oa.matching_score DESC NULLS LAST
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (offer_id,))
            return [_attach_phase_statuses(_row_to_dict(r)) for r in cur.fetchall()]


def get_appearance_by_id(appearance_id: str) -> Optional[dict]:
    sql = """
        SELECT oa.*,
               jo.created_by, jo.assigned_to
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        WHERE oa.id = %s AND jo.deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (appearance_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def update_appearance_note(
    appearance_id: str,
    note: str,
    role: str,
) -> Optional[dict]:
    column = "sourcer_note" if role == "sourcer" else "recruiter_note"
    sql = f"""
        UPDATE candidates.offer_appearances
        SET {column} = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (note, appearance_id))
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row) if row else None


def get_candidate_offer_history(
    candidate_id: str,
    exclude_offer_id: Optional[str] = None,
) -> List[dict]:
    sql = """
        SELECT oa.offer_id,
               jo.title AS offer_title,
               jo.status_id,
               os.label_fr AS offer_status,
               oa.matching_score,
               oa.final_score,
               oa.decision,
               oa.created_at,
               jo.created_by AS recruiter_id,
               recruiter_u.full_name AS recruiter_name,
               sourcer_u.full_name AS sourcer_name
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        LEFT JOIN ref.offer_statuses os ON os.id = jo.status_id
        LEFT JOIN auth.users recruiter_u ON recruiter_u.id = jo.created_by
        LEFT JOIN auth.users sourcer_u ON sourcer_u.id = jo.assigned_to
        WHERE oa.candidate_id = %s AND jo.deleted_at IS NULL
    """
    params: list[Any] = [candidate_id]
    if exclude_offer_id:
        sql += " AND oa.offer_id != %s"
        params.append(exclude_offer_id)
    sql += " ORDER BY oa.created_at DESC"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_row_to_dict(r) for r in cur.fetchall()]


def sync_appearances_from_matching(
    session_id: str,
    offer_id: str,
    job_id: str,
    matching_dir: Path,
) -> int:
    """Best-effort: create offer_appearances from matching JSON files. Returns rows upserted."""
    try:
        if not matching_dir.exists():
            return 0
    except OSError:
        return 0
    json_files = sorted(matching_dir.glob("*.json"))
    if not json_files:
        return 0

    candidates: list[dict] = []
    for json_path in json_files:
        try:
            with open(json_path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        candidates.extend(payload.get("candidates") or [])

    synced = 0
    for rank, item in enumerate(candidates, 1):
        if not isinstance(item, dict):
            continue
        cand = resolve_candidate_from_matching_item(item)
        if not cand:
            continue
        upsert_appearance(
            candidate_id=cand["id"],
            offer_id=offer_id,
            job_id=job_id,
            matching_score=item.get("overall_score"),
            final_score=None,
            rank=rank,
        )
        synced += 1
    return synced


def sync_appearances_for_offer(offer_id: str) -> int:
    """Idempotent sync of offer_appearances from the offer's pipeline matching results."""
    from service.job_store import get_job, get_job_by_session_id

    sql = """
        SELECT job_id, session_id
        FROM offers.job_offers
        WHERE id = %s::uuid AND deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (offer_id,))
            offer = cur.fetchone()
    if not offer:
        return 0

    job_id = offer.get("job_id")
    session_id = offer.get("session_id")
    if not job_id and session_id:
        job = get_job_by_session_id(session_id)
        job_id = job.id if job else None
    if not session_id and job_id:
        job = get_job(job_id)
        session_id = job.session_id if job else None
    if not session_id or not job_id:
        return 0

    from service.config import CURRENT_DIR, ARCHIVE_DIR

    matching_dirs = [
        CURRENT_DIR / "matching_results" / session_id,
        ARCHIVE_DIR / session_id / "matching_results",
        ARCHIVE_DIR / session_id / "matching",
    ]
    synced = 0
    for matching_dir in matching_dirs:
        if _path_exists(matching_dir):
            synced += sync_appearances_from_matching(
                session_id, offer_id, job_id, matching_dir
            )
            break

    final_path = _resolve_final_path(session_id)
    if final_path:
        sync_final_scores_from_result(session_id, offer_id, final_path)
    return synced


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _resolve_final_path(session_id: str) -> Optional[Path]:
    from service.config import CURRENT_DIR, ARCHIVE_DIR

    for candidate in (
        CURRENT_DIR / "final_result" / session_id / "final_result.json",
        ARCHIVE_DIR / session_id / "final_result" / "final_result.json",
        ARCHIVE_DIR / session_id / "final" / "final_result.json",
    ):
        if _path_exists(candidate):
            return candidate
    return None


def backfill_appearances_from_pipeline() -> int:
    """Idempotent sync of offer_appearances from existing pipeline jobs (Action 238)."""
    from service.config import CURRENT_DIR, ARCHIVE_DIR

    sql = """
        SELECT job_id, session_id, offer_id
        FROM jobs.pipeline_jobs
        WHERE offer_id IS NOT NULL
          AND stage IN (
            'matching_complete', 'running_final', 'final_complete',
            'running_format', 'format_complete'
          )
    """
    synced = 0
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            jobs = cur.fetchall()
    for job in jobs:
        session_id = job["session_id"]
        offer_id = str(job["offer_id"])
        job_id = job["job_id"]
        matching_dirs = [
            CURRENT_DIR / "matching_results" / session_id,
            ARCHIVE_DIR / session_id / "matching_results",
            ARCHIVE_DIR / session_id / "matching",
        ]
        for matching_dir in matching_dirs:
            if _path_exists(matching_dir):
                synced += sync_appearances_from_matching(session_id, offer_id, job_id, matching_dir)
                break
        final_path = _resolve_final_path(session_id)
        if final_path:
            sync_final_scores_from_result(session_id, offer_id, final_path)
    return synced


def get_recruiter_candidate_stats(recruiter_id: str) -> dict:
    """Aggregate candidate CRM stats scoped to a recruiter's offers."""
    sql = """
        SELECT
          COUNT(DISTINCT oa.candidate_id) AS candidates_seen,
          COUNT(*) FILTER (WHERE oa.matching_status_id = 2) AS shortlisted,
          COUNT(*) FILTER (
            WHERE oa.matching_status_id = 3
               OR oa.final_status_id = 2
               OR oa.format_status_id = 5
          ) AS in_process,
          COUNT(*) FILTER (WHERE oa.format_status_id = 6) AS hired,
          AVG(
            CASE
              WHEN COALESCE(oa.final_score, oa.matching_score) IS NULL THEN NULL
              WHEN COALESCE(oa.final_score, oa.matching_score) <= 1
                THEN COALESCE(oa.final_score, oa.matching_score) * 100
              ELSE COALESCE(oa.final_score, oa.matching_score)
            END
          ) AS avg_score
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        WHERE jo.created_by = %s AND jo.deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(recruiter_id),))
            row = dict(cur.fetchone() or {})
    avg = row.get("avg_score")
    return {
        "candidates_seen": int(row.get("candidates_seen") or 0),
        "candidates_shortlisted": int(row.get("shortlisted") or 0),
        "candidates_in_process": int(row.get("in_process") or 0),
        "candidates_hired": int(row.get("hired") or 0),
        "average_matching_score": round(float(avg), 1) if avg is not None else None,
    }


def get_candidates_matching_offer_skills(offer_id: str, limit: int = 20) -> List[dict]:
    """Return candidates ranked by overlap with an offer's required skills."""
    sql = """
        SELECT c.id, c.full_name,
               c.profile_id, c.seniority_id,
               rp.code AS profile_code,
               rp.label_fr AS profile_label_fr,
               rs.code AS seniority_code,
               rs.label_fr AS seniority_label_fr,
               COUNT(DISTINCT cs.skill_id) AS matching_skills_count,
               (
                 SELECT COUNT(*)::int
                 FROM offers.offer_skills os2
                 WHERE os2.offer_id = %s
               ) AS total_offer_skills
        FROM candidates.profiles c
        JOIN candidates.candidate_skills cs ON cs.candidate_id = c.id
        JOIN offers.offer_skills os
          ON os.skill_id = cs.skill_id AND os.offer_id = %s
        LEFT JOIN ref.profiles rp ON rp.id = c.profile_id
        LEFT JOIN ref.seniorities rs ON rs.id = c.seniority_id
        WHERE c.deleted_at IS NULL
        GROUP BY c.id, c.full_name, c.profile_id, c.seniority_id,
                 rp.code, rp.label_fr, rs.code, rs.label_fr
        ORDER BY matching_skills_count DESC, c.full_name
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(offer_id), str(offer_id), limit))
            rows = []
            for row in cur.fetchall():
                d = _row_to_dict(row)
                total = int(d.get("total_offer_skills") or 0)
                matching = int(d.get("matching_skills_count") or 0)
                d["match_percentage"] = (
                    round(100.0 * matching / total, 1) if total > 0 else 0.0
                )
                d["profile"] = d.get("profile_label_fr") or d.get("profile_code")
                d["seniority"] = d.get("seniority_label_fr") or d.get("seniority_code")
                rows.append(d)
            return rows


def sync_final_scores_from_result(
    session_id: str,
    offer_id: str,
    final_path: Path,
) -> None:
    """Best-effort: update appearances with final_score from final_result.json."""
    try:
        if not final_path.exists():
            return
    except OSError:
        return
    with open(final_path, encoding="utf-8") as f:
        payload = json.load(f)
    raw = payload.get("candidates") or []
    if isinstance(raw, dict):
        items = [
            {"name": name, **data} if isinstance(data, dict) else {"name": name}
            for name, data in raw.items()
        ]
    else:
        items = raw
    for item in items:
        if not isinstance(item, dict):
            continue
        cv_filename = item.get("cv_filename")
        name = item.get("name") or item.get("candidate_name")
        cand = resolve_candidate_from_matching_item(item)
        if not cand:
            continue
        update_appearance_final_scores(
            candidate_id=cand["id"],
            offer_id=offer_id,
            final_score=item.get("final_score") or item.get("overall_score"),
            rank=item.get("rank"),
        )


def get_matching_statuses() -> List[dict]:
    sql = """
        SELECT id, code, label_fr, sort_order
        FROM ref.matching_statuses
        ORDER BY sort_order
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_final_statuses() -> List[dict]:
    sql = """
        SELECT id, code, label_fr, sort_order
        FROM ref.final_statuses
        ORDER BY sort_order
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_format_statuses() -> List[dict]:
    sql = """
        SELECT id, code, label_fr, sort_order, triggers_flag
        FROM ref.format_statuses
        ORDER BY sort_order
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [_row_to_dict(r) for r in cur.fetchall()]


def _resolve_phase_status_id(cur, phase: str, status_code: str) -> Optional[int]:
    table = {
        "matching": "ref.matching_statuses",
        "final": "ref.final_statuses",
        "format": "ref.format_statuses",
    }.get(phase)
    if not table:
        return None
    cur.execute(f"SELECT id FROM {table} WHERE code = %s LIMIT 1", (status_code,))
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _insert_appearance_status_history(
    cur,
    appearance_id: str,
    phase: str,
    status_id: int,
    status_code: str,
    changed_by: Optional[str] = None,
) -> None:
    cur.execute(
        """
        INSERT INTO candidates.appearance_status_history
          (appearance_id, phase, status_id, status_code, changed_at, changed_by)
        VALUES (%s, %s, %s, %s, NOW(), %s::uuid)
        """,
        (appearance_id, phase, status_id, status_code, changed_by),
    )


def update_appearance_status(
    appearance_id: str,
    phase: str,
    status_code: str,
    changed_by: Optional[str] = None,
) -> Optional[dict]:
    column = {
        "matching": "matching_status_id",
        "final": "final_status_id",
        "format": "format_status_id",
    }.get(phase)
    if not column:
        return None
    with _connect() as conn:
        with conn.cursor() as cur:
            status_id = _resolve_phase_status_id(cur, phase, status_code)
            if status_id is None:
                return None
            cur.execute(
                f"SELECT {column} FROM candidates.offer_appearances WHERE id = %s",
                (appearance_id,),
            )
            current = cur.fetchone()
            if not current:
                conn.rollback()
                return None
            if current[column] is not None and int(current[column]) == status_id:
                conn.commit()
                return get_appearance_with_statuses(appearance_id)
            changed_col = {
                "matching": "matching_status_changed_at",
                "final": "final_status_changed_at",
                "format": "format_status_changed_at",
            }[phase]
            sql = f"""
                UPDATE candidates.offer_appearances
                SET {column} = %s,
                    {changed_col} = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id
            """
            cur.execute(sql, (status_id, appearance_id))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            _insert_appearance_status_history(
                cur, appearance_id, phase, status_id, status_code, changed_by,
            )
            conn.commit()
    return get_appearance_with_statuses(appearance_id)


def get_appearance_with_statuses(appearance_id: str) -> Optional[dict]:
    sql = f"""
        SELECT oa.*,
               ms.code AS matching_status_code,
               ms.label_fr AS matching_status_label_fr,
               fs.code AS final_status_code,
               fs.label_fr AS final_status_label_fr,
               fts.code AS format_status_code,
               fts.label_fr AS format_status_label_fr
        FROM candidates.offer_appearances oa
        {_APPEARANCE_STATUS_JOINS}
        WHERE oa.id = %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (appearance_id,))
            row = cur.fetchone()
            if not row:
                return None
            return _attach_phase_statuses(_row_to_dict(row))


def get_active_unreliability_flag(candidate_id: str) -> Optional[dict]:
    sql = """
        SELECT uf.*, jo.title AS offer_title
        FROM candidates.unreliability_flags uf
        LEFT JOIN offers.job_offers jo ON jo.id = uf.offer_id
        WHERE uf.candidate_id = %s AND uf.resolved_at IS NULL
        ORDER BY uf.created_at DESC
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (candidate_id,))
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_dict(row)


def get_active_unreliability_flags_bulk(candidate_ids: List[str]) -> Dict[str, dict]:
    if not candidate_ids:
        return {}
    sql = """
        SELECT DISTINCT ON (uf.candidate_id)
               uf.*, jo.title AS offer_title
        FROM candidates.unreliability_flags uf
        LEFT JOIN offers.job_offers jo ON jo.id = uf.offer_id
        WHERE uf.candidate_id = ANY(%s::uuid[]) AND uf.resolved_at IS NULL
        ORDER BY uf.candidate_id, uf.created_at DESC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (candidate_ids,))
            rows = cur.fetchall()
            return {str(r["candidate_id"]): _row_to_dict(r) for r in rows}


def format_unreliability_flag(flag: Optional[dict]) -> Optional[dict]:
    if not flag:
        return None
    return {
        "id": flag.get("id"),
        "reason": flag.get("reason"),
        "flagged_by_name": flag.get("flagged_by_name"),
        "offer_title": flag.get("offer_title"),
        "created_at": flag.get("created_at"),
    }


def create_unreliability_flag(
    candidate_id: str,
    offer_id: Optional[str],
    appearance_id: Optional[str],
    reason: str,
    flagged_by: Optional[str],
    flagged_by_name: str,
) -> dict:
    sql = """
        INSERT INTO candidates.unreliability_flags (
            candidate_id, offer_id, appearance_id,
            reason, flagged_by, flagged_by_name
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (candidate_id, offer_id, appearance_id, reason, flagged_by, flagged_by_name),
            )
            row = cur.fetchone()
            conn.commit()
            result = _row_to_dict(row)
    if offer_id:
        offer = None
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title FROM offers.job_offers WHERE id = %s",
                    (offer_id,),
                )
                offer = cur.fetchone()
        if offer:
            result["offer_title"] = offer["title"]
    return result


def resolve_unreliability_flag(
    flag_id: str,
    resolved_by: Optional[str],
    resolved_reason: str,
) -> Optional[dict]:
    sql = """
        UPDATE candidates.unreliability_flags
        SET resolved_at = NOW(),
            resolved_by = %s,
            resolved_reason = %s
        WHERE id = %s AND resolved_at IS NULL
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (resolved_by, resolved_reason, flag_id))
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row) if row else None


def get_unreliability_flag_by_id(flag_id: str) -> Optional[dict]:
    sql = """
        SELECT uf.*, jo.title AS offer_title
        FROM candidates.unreliability_flags uf
        LEFT JOIN offers.job_offers jo ON jo.id = uf.offer_id
        WHERE uf.id = %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (flag_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
