"""
service/offer_store.py

PostgreSQL-backed store for offers.job_offers and offers.offer_assignments.
Schema defined in service/migrations/001_auth_offers_schema.sql
                 + service/migrations/002_offer_columns.sql.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()


# ── Offer status reference (mirrors ref.offer_statuses, migration 005) ─────────
# status_id is the authoritative status as of Action 220. The legacy text `status`
# column is deprecated (kept in sync only within its CHECK set: open/in_progress/
# closed/archived) — new lifecycle states live only in status_id.
OFFER_STATUSES = [
    {"id": 1, "code": "open",         "label_fr": "Ouverte",        "sort_order": 1, "visible_to": "all"},
    {"id": 2, "code": "assigned",     "label_fr": "Assignée",       "sort_order": 2, "visible_to": "all"},
    {"id": 3, "code": "in_progress",  "label_fr": "En cours",       "sort_order": 3, "visible_to": "all"},
    {"id": 4, "code": "matched",      "label_fr": "Matchée",        "sort_order": 4, "visible_to": "all"},
    {"id": 5, "code": "final_result", "label_fr": "Résultat final", "sort_order": 5, "visible_to": "recruiter_only"},
    {"id": 6, "code": "formatted",    "label_fr": "Formatée",       "sort_order": 6, "visible_to": "recruiter_only"},
    {"id": 7, "code": "archived",     "label_fr": "Archivée",       "sort_order": 7, "visible_to": "all"},
]
_STATUS_BY_ID = {s["id"]: s for s in OFFER_STATUSES}
_STATUS_BY_CODE = {s["code"]: s for s in OFFER_STATUSES}

# Legacy text `status` column has a CHECK (open|in_progress|closed|archived).
# Dual-write it to the nearest legal value so existing recruiter/admin views keep
# working while status_id is the authoritative lifecycle state.
_LEGACY_TEXT_BY_ID = {
    1: "open", 2: "in_progress", 3: "in_progress", 4: "in_progress",
    5: "in_progress", 6: "in_progress", 7: "archived",
}


@dataclass
class Offer:
    id: UUID
    title: str
    description: str
    experience_level: Optional[str]
    location: Optional[str]
    salary_range: Optional[str]
    status: str                     # legacy text (deprecated): open|in_progress|closed|archived
    status_id: Optional[int]        # authoritative status (ref.offer_statuses)
    status_code: Optional[str]      # derived from status_id
    status_label: Optional[str]     # French label derived from status_id
    contract_type_id: Optional[int]
    experience_range_id: Optional[int]
    created_by: UUID
    assigned_to: Optional[UUID]
    session_id: Optional[str]
    offer_sftp_path: Optional[str]
    source_storage_path: Optional[str]
    source_original_filename: Optional[str]
    source_file_size: Optional[int]
    source_sha256: Optional[str]
    source_created_at: Optional[datetime]
    job_id: Optional[str]           # pipeline job UUID (set when sourcer launches)
    file_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


def _connect() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL env var is not set.")
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _row_to_offer(row: dict) -> Offer:
    status_id = row.get("status_id") or 1
    meta = _STATUS_BY_ID.get(status_id, _STATUS_BY_ID[1])
    return Offer(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        experience_level=row.get("experience_level"),
        location=row.get("location"),
        salary_range=row.get("salary_range"),
        status=row["status"],
        status_id=status_id,
        status_code=meta["code"],
        status_label=meta["label_fr"],
        contract_type_id=row.get("contract_type_id") or 1,
        experience_range_id=row.get("experience_range_id"),
        created_by=row["created_by"],
        assigned_to=row.get("assigned_to"),
        session_id=row.get("session_id"),
        offer_sftp_path=row.get("offer_sftp_path"),
        source_storage_path=row.get("source_storage_path"),
        source_original_filename=row.get("source_original_filename"),
        source_file_size=row.get("source_file_size"),
        source_sha256=row.get("source_sha256"),
        source_created_at=row.get("source_created_at"),
        job_id=row.get("job_id"),
        file_path=row.get("file_path"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row.get("deleted_at"),
    )


def _normalize_skill_name(name: object) -> Optional[str]:
    if not isinstance(name, str):
        return None
    cleaned = name.strip()
    return cleaned if cleaned else None


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


def sync_offer_skills(offer_id: str, skill_names: list) -> None:
    """Link an offer to ref.skills rows via offers.offer_skills bridge table."""
    names: list[str] = []
    seen: set[str] = set()
    for raw in skill_names or []:
        name = _normalize_skill_name(raw)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    if not names:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            for name in names:
                skill_id = _get_or_create_skill_id(cur, name)
                cur.execute(
                    """
                    INSERT INTO offers.offer_skills (offer_id, skill_id, is_required)
                    VALUES (%s, %s, true)
                    ON CONFLICT (offer_id, skill_id) DO NOTHING
                    """,
                    (str(offer_id), skill_id),
                )
            conn.commit()


def fetch_offer_skills(offer_id: str) -> List[dict]:
    """Return structured skills linked to an offer."""
    sql = """
        SELECT s.id, s.name, s.category
        FROM offers.offer_skills os
        JOIN ref.skills s ON s.id = os.skill_id
        WHERE os.offer_id = %s
        ORDER BY s.name
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(offer_id),))
            return [
                {"id": int(r["id"]), "name": r["name"], "category": r.get("category")}
                for r in cur.fetchall()
            ]


def fetch_offer_skills_bulk(offer_ids: List[str]) -> dict:
    """Return {offer_id_str: [skill dicts]} for many offers."""
    if not offer_ids:
        return {}
    sql = """
        SELECT os.offer_id::text AS offer_id, s.id, s.name, s.category
        FROM offers.offer_skills os
        JOIN ref.skills s ON s.id = os.skill_id
        WHERE os.offer_id = ANY(%s::uuid[])
        ORDER BY s.name
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, ([str(i) for i in offer_ids],))
            out: dict = {}
            for row in cur.fetchall():
                oid = row["offer_id"]
                out.setdefault(oid, []).append(
                    {"id": int(row["id"]), "name": row["name"], "category": row.get("category")}
                )
            return out


def display_experience_range(
    min_years: float | int | None,
    max_years: float | int | None,
) -> Optional[str]:
    """Format an experience range for UI display."""
    if min_years is None and max_years is None:
        return None
    if min_years is not None and max_years is not None:
        if float(min_years) == float(max_years):
            return f"{float(min_years):.0f} ans"
        return f"{float(min_years):.0f} ~ {float(max_years):.0f}"
    if min_years is not None:
        return f"{float(min_years):.0f}+"
    if max_years is not None:
        return f"{float(max_years):.0f}-"
    return None


def _float_or_none(value: object) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def contract_type_to_dict(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "code": row["code"],
        "label_fr": row["label_fr"],
    }


def experience_range_to_dict(row: dict) -> dict:
    min_y = _float_or_none(row.get("min_years"))
    max_y = _float_or_none(row.get("max_years"))
    return {
        "id": int(row["id"]),
        "min_years": min_y,
        "max_years": max_y,
        "display": display_experience_range(min_y, max_y),
    }


def list_contract_types(active_only: bool = True) -> List[dict]:
    sql = """
        SELECT id, code, label_fr
        FROM ref.contract_types
    """
    if active_only:
        sql += " WHERE is_active = true"
    sql += " ORDER BY id"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [contract_type_to_dict(dict(r)) for r in cur.fetchall()]


def list_experience_ranges() -> List[dict]:
    sql = """
        SELECT id, min_years, max_years
        FROM ref.experience_ranges
        ORDER BY min_years NULLS LAST, max_years NULLS LAST, id
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [experience_range_to_dict(dict(r)) for r in cur.fetchall()]


def fetch_contract_type(contract_type_id: int) -> Optional[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, code, label_fr FROM ref.contract_types WHERE id = %s LIMIT 1",
                (int(contract_type_id),),
            )
            row = cur.fetchone()
            return contract_type_to_dict(dict(row)) if row else None


def fetch_experience_range(experience_range_id: int) -> Optional[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, min_years, max_years FROM ref.experience_ranges WHERE id = %s LIMIT 1",
                (int(experience_range_id),),
            )
            row = cur.fetchone()
            return experience_range_to_dict(dict(row)) if row else None


def fetch_contract_types_by_ids(ids: List[int]) -> dict[int, dict]:
    if not ids:
        return {}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, code, label_fr
                FROM ref.contract_types
                WHERE id = ANY(%s::smallint[])
                """,
                (list(set(ids)),),
            )
            return {int(r["id"]): contract_type_to_dict(dict(r)) for r in cur.fetchall()}


def fetch_experience_ranges_by_ids(ids: List[int]) -> dict[int, dict]:
    if not ids:
        return {}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, min_years, max_years
                FROM ref.experience_ranges
                WHERE id = ANY(%s::int[])
                """,
                (list(set(ids)),),
            )
            return {int(r["id"]): experience_range_to_dict(dict(r)) for r in cur.fetchall()}


def get_or_create_experience_range(
    min_years: float | None,
    max_years: float | None,
) -> int:
    """Find or create an experience range row; NULL-safe comparison."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM ref.experience_ranges
                WHERE min_years IS NOT DISTINCT FROM %s
                  AND max_years IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (min_years, max_years),
            )
            row = cur.fetchone()
            if row:
                return int(row["id"])
            cur.execute(
                """
                INSERT INTO ref.experience_ranges (min_years, max_years)
                VALUES (%s, %s)
                RETURNING id
                """,
                (min_years, max_years),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id


def get_or_create_contract_type(code: str) -> int:
    """Resolve contract type by code (case-insensitive); create if unknown."""
    normalized = (code or "CDI").strip()
    if not normalized:
        normalized = "CDI"
    lookup = normalized.upper()
    label_map = {
        "CDI": "CDI",
        "CDD": "CDD",
        "FREELANCE": "Freelance / Mission",
        "STAGE": "Stage",
        "ALTERNANCE": "Alternance",
        "REGIE": "Régie",
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM ref.contract_types
                WHERE UPPER(code) = UPPER(%s)
                LIMIT 1
                """,
                (normalized,),
            )
            row = cur.fetchone()
            if row:
                return int(row["id"])
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM ref.contract_types")
            next_id = int(cur.fetchone()["next_id"])
            cur.execute(
                """
                INSERT INTO ref.contract_types (id, code, label_fr, is_active)
                VALUES (%s, %s, %s, true)
                RETURNING id
                """,
                (
                    next_id,
                    lookup if lookup in label_map else normalized,
                    label_map.get(lookup, normalized),
                ),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id


def create_offer(
    title: str,
    description: str,
    created_by: str,
    experience_level: Optional[str] = None,
    location: Optional[str] = None,
    salary_range: Optional[str] = None,
    session_id: Optional[str] = None,
    offer_sftp_path: Optional[str] = None,
    contract_type_id: Optional[int] = 1,
    experience_range_id: Optional[int] = None,
    offer_id: Optional[str] = None,
    source_storage_path: Optional[str] = None,
    source_original_filename: Optional[str] = None,
    source_file_size: Optional[int] = None,
    source_sha256: Optional[str] = None,
) -> Offer:
    sql = """
        INSERT INTO offers.job_offers
          (id, title, description, created_by,
           experience_level, location, salary_range, session_id, offer_sftp_path,
           source_storage_path, source_original_filename, source_file_size, source_sha256,
           contract_type_id, experience_range_id,
           status, status_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', 1)
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            if not offer_id:
                cur.execute("SELECT gen_random_uuid() AS id")
                offer_id = str(cur.fetchone()["id"])
            cur.execute(sql, (
                str(offer_id),
                title,
                description,
                str(created_by),
                experience_level,
                location,
                salary_range,
                session_id,
                offer_sftp_path,
                source_storage_path,
                source_original_filename,
                source_file_size,
                source_sha256,
                contract_type_id or 1,
                experience_range_id,
            ))
            row = cur.fetchone()
            conn.commit()
            return _row_to_offer(dict(row))


def update_offer_source_metadata(
    offer_id: str,
    source_storage_path: str,
    source_original_filename: str,
    source_file_size: int,
    source_sha256: str,
    offer_sftp_path: Optional[str] = None,
) -> None:
    sql = """
        UPDATE offers.job_offers
        SET source_storage_path = %s,
            source_original_filename = %s,
            source_file_size = %s,
            source_sha256 = %s,
            source_created_at = COALESCE(source_created_at, NOW()),
            offer_sftp_path = COALESCE(%s, offer_sftp_path),
            updated_at = NOW()
        WHERE id = %s AND deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source_storage_path,
                    source_original_filename,
                    int(source_file_size),
                    source_sha256,
                    offer_sftp_path,
                    str(offer_id),
                ),
            )
            conn.commit()


def get_offer_by_id(offer_id: str) -> Optional[Offer]:
    sql = "SELECT * FROM offers.job_offers WHERE id = %s AND deleted_at IS NULL LIMIT 1"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(offer_id),))
            row = cur.fetchone()
            return _row_to_offer(dict(row)) if row else None


def get_offers_by_recruiter(user_id: str) -> List[Offer]:
    """All offers created by this recruiter, newest first."""
    sql = """
        SELECT * FROM offers.job_offers
        WHERE created_by = %s AND deleted_at IS NULL
        ORDER BY created_at DESC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id),))
            return [_row_to_offer(dict(r)) for r in cur.fetchall()]


def get_offers_by_sourcer(user_id: str) -> List[Offer]:
    """Offers assigned to this sourcer, newest first.

    Sourcers only ever see status_id <= 4 (open, assigned, in_progress, matched);
    recruiter-only states (final_result, formatted) and archived are hidden.
    """
    sql = """
        SELECT * FROM offers.job_offers
        WHERE assigned_to = %s AND deleted_at IS NULL AND status_id <= 4
        ORDER BY updated_at DESC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id),))
            return [_row_to_offer(dict(r)) for r in cur.fetchall()]


def get_sourcer_dashboard_offers(user_id: str) -> List[Offer]:
    """All non-archived offers assigned to this sourcer — for dashboard KPIs.

    Unlike ``get_offers_by_sourcer``, includes recruiter-only states (final_result,
    formatted) so completed matching work still counts after the offer advances.
    """
    sql = """
        SELECT * FROM offers.job_offers
        WHERE assigned_to = %s AND deleted_at IS NULL AND status_id < 7
        ORDER BY updated_at DESC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id),))
            return [_row_to_offer(dict(r)) for r in cur.fetchall()]


def assign_offer(offer_id: str, sourcer_id: str, assigned_by: str) -> Optional[Offer]:
    """Assign offer to a sourcer and set status_id=2 (assigned). Records assignment history."""
    with _connect() as conn:
        with conn.cursor() as cur:
            # Deactivate previous assignments for this offer
            cur.execute(
                "UPDATE offers.offer_assignments SET is_active = false WHERE offer_id = %s",
                (str(offer_id),),
            )
            # Update the offer (status_id authoritative; legacy text dual-written)
            cur.execute(
                """
                UPDATE offers.job_offers
                SET assigned_to = %s, status_id = 2, status = 'in_progress', updated_at = NOW()
                WHERE id = %s AND deleted_at IS NULL
                RETURNING *
                """,
                (str(sourcer_id), str(offer_id)),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            # Insert assignment record
            cur.execute(
                """
                INSERT INTO offers.offer_assignments (offer_id, assigned_to, assigned_by)
                VALUES (%s, %s, %s)
                """,
                (str(offer_id), str(sourcer_id), str(assigned_by)),
            )
            conn.commit()
            return _row_to_offer(dict(row))


def get_offer_for_recruiter(offer_id: str, recruiter_id: str) -> Optional[Offer]:
    """Return an offer only if it belongs to the given recruiter."""
    sql = """
        SELECT * FROM offers.job_offers
        WHERE id = %s AND created_by = %s AND deleted_at IS NULL
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(offer_id), str(recruiter_id)))
            row = cur.fetchone()
            return _row_to_offer(dict(row)) if row else None


def delete_offer(offer_id: str) -> None:
    """Soft-delete an offer (sets deleted_at = NOW()). Deprecated — use hard_delete_offer."""
    sql = """
        UPDATE offers.job_offers
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE id = %s AND deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(offer_id),))
            conn.commit()


def hard_delete_offer(offer_id: str) -> None:
    """Permanently remove an offer and all linked rows (Action 232).

    Order: wipe prior audit rows for this offer (keeps the final ``offer_deleted``
    entry logged by the caller), then jobs/assignments/offer.
    """
    oid = str(offer_id)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM audit.activity_log "
                "WHERE target_id = %s AND event_type != 'offer_deleted'",
                (oid,),
            )
            cur.execute(
                "DELETE FROM jobs.pipeline_jobs WHERE offer_id = %s",
                (oid,),
            )
            cur.execute(
                "DELETE FROM offers.offer_assignments WHERE offer_id = %s",
                (oid,),
            )
            cur.execute(
                "DELETE FROM offers.job_offers WHERE id = %s",
                (oid,),
            )
            conn.commit()


def get_assignment_events_for_sourcer(user_id: str, limit: int = 10) -> list:
    """Return recent assignment events for a sourcer (for activity feed)."""
    sql = """
        SELECT jo.title, oa.assigned_at
        FROM offers.offer_assignments oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        WHERE oa.assigned_to = %s AND jo.deleted_at IS NULL
        ORDER BY oa.assigned_at DESC
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id), limit))
            return [{"title": row["title"], "assigned_at": row["assigned_at"]} for row in cur.fetchall()]


def get_active_offer_counts() -> dict:
    """Return {sourcer_id_str: active_count} for all sourcers.

    Active = assigned and not archived (status_id between 2 and 6).
    """
    sql = """
        SELECT assigned_to::text AS sid, COUNT(*) AS cnt
        FROM offers.job_offers
        WHERE assigned_to IS NOT NULL
          AND status_id BETWEEN 2 AND 6
          AND deleted_at IS NULL
        GROUP BY assigned_to
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return {row["sid"]: row["cnt"] for row in cur.fetchall()}


def update_offer_status(offer_id: str, new_status: str, recruiter_id: str) -> Optional[Offer]:
    """Update offer status by status CODE (e.g. 'archived'); validates ownership.

    Resolves the code to a status_id via the reference table. Returns None if the
    code is unknown or the offer does not belong to the recruiter.
    """
    meta = _STATUS_BY_CODE.get(new_status)
    if not meta:
        return None
    legacy = _LEGACY_TEXT_BY_ID.get(meta["id"], "open")
    sql = """
        UPDATE offers.job_offers
        SET status_id = %s, status = %s, updated_at = NOW()
        WHERE id = %s AND created_by = %s AND deleted_at IS NULL
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (meta["id"], legacy, str(offer_id), str(recruiter_id)))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            conn.commit()
            return _row_to_offer(dict(row))


def set_offer_status_id(offer_id: str, status_id: int) -> Optional[Offer]:
    """Set an offer's status_id unconditionally (used by pipeline transitions).

    No ownership check — called by the runner / system on pipeline events.
    """
    legacy = _LEGACY_TEXT_BY_ID.get(int(status_id), "open")
    sql = """
        UPDATE offers.job_offers
        SET status_id = %s, status = %s, updated_at = NOW()
        WHERE id = %s AND deleted_at IS NULL
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (int(status_id), legacy, str(offer_id)))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            conn.commit()
            return _row_to_offer(dict(row))


def get_offer_statuses() -> list:
    """Return all ref.offer_statuses rows (ordered) for building UI tabs."""
    sql = """
        SELECT id, code, label_fr, description, sort_order, visible_to
        FROM ref.offer_statuses
        ORDER BY sort_order
    """
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        # Fallback to the static mirror if the ref table is unavailable.
        return [dict(s) for s in OFFER_STATUSES]


def get_dashboard_data(recruiter_id: str) -> dict:
    """
    Return aggregated KPI data for the recruiter dashboard.
    Jobs data (cv_count, completion) must be merged by the caller
    since jobs live in SQLite (job_store), not PostgreSQL.
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            # Offers by authoritative status_id (ref.offer_statuses)
            cur.execute(
                """
                SELECT status_id, COUNT(*) AS cnt
                FROM offers.job_offers
                WHERE created_by = %s AND deleted_at IS NULL
                GROUP BY status_id
                """,
                (str(recruiter_id),),
            )
            by_stage: dict = {}
            for row in cur.fetchall():
                meta = _STATUS_BY_ID.get(int(row["status_id"] or 1), _STATUS_BY_ID[1])
                by_stage[meta["code"]] = row["cnt"]

            # Assigned sourcer counts (for top sourcer)
            cur.execute(
                """
                SELECT oa.assigned_to, u.full_name, COUNT(*) AS cnt
                FROM offers.offer_assignments oa
                JOIN offers.job_offers jo ON jo.id = oa.offer_id
                LEFT JOIN auth.users u ON u.id = oa.assigned_to
                WHERE jo.created_by = %s AND oa.is_active = true AND jo.deleted_at IS NULL
                GROUP BY oa.assigned_to, u.full_name
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (str(recruiter_id),),
            )
            top_sourcer_row = cur.fetchone()
            top_sourcer = (
                {"full_name": top_sourcer_row["full_name"], "assignment_count": top_sourcer_row["cnt"]}
                if top_sourcer_row
                else None
            )

            # Recent activity (offer created + assigned events)
            cur.execute(
                """
                SELECT 'offer_created' AS type, title AS description, created_at AS ts
                FROM offers.job_offers
                WHERE created_by = %s AND deleted_at IS NULL
                UNION ALL
                SELECT 'offer_assigned' AS type,
                       jo.title AS description,
                       oa.assigned_at AS ts
                FROM offers.offer_assignments oa
                JOIN offers.job_offers jo ON jo.id = oa.offer_id
                WHERE jo.created_by = %s AND jo.deleted_at IS NULL
                ORDER BY ts DESC
                LIMIT 10
                """,
                (str(recruiter_id), str(recruiter_id)),
            )
            activity_rows = [dict(r) for r in cur.fetchall()]

    return {
        "offers_by_stage": by_stage,
        "top_sourcer": top_sourcer,
        "activity_rows": activity_rows,  # legacy — audit log used by API instead
    }


# ── Admin space helpers (Workstream 3) ─────────────────────────────────────────

def get_offer_status_counts() -> dict:
    """System-wide offers grouped by legacy status text (non-deleted)."""
    sql = """
        SELECT status, COUNT(*) AS cnt
        FROM offers.job_offers
        WHERE deleted_at IS NULL
        GROUP BY status
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return {row["status"]: row["cnt"] for row in cur.fetchall()}


def get_recent_offer_events(limit: int = 20) -> list:
    """System-wide recent offer events (created + assigned) for the admin activity feed.

    Each row: {type, title, sourcer, user_name, ts}.
    """
    sql = """
        SELECT 'offer_created' AS type, jo.title AS title, NULL AS sourcer,
               cu.full_name AS user_name, jo.created_at AS ts
        FROM offers.job_offers jo
        LEFT JOIN auth.users cu ON cu.id = jo.created_by
        WHERE jo.deleted_at IS NULL
        UNION ALL
        SELECT 'offer_assigned' AS type, jo.title AS title, su.full_name AS sourcer,
               au.full_name AS user_name, oa.assigned_at AS ts
        FROM offers.offer_assignments oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id AND jo.deleted_at IS NULL
        LEFT JOIN auth.users su ON su.id = oa.assigned_to
        LEFT JOIN auth.users au ON au.id = oa.assigned_by
        ORDER BY ts DESC
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return [dict(r) for r in cur.fetchall()]


def set_offer_job_id(offer_id: str, job_id: str) -> None:
    """Link a pipeline job to an offer (called when sourcer launches the pipeline)."""
    sql = """
        UPDATE offers.job_offers
        SET job_id = %s, updated_at = NOW()
        WHERE id = %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(job_id), str(offer_id)))
            conn.commit()


def update_offer_job_id(offer_id: str, job_id: str, status_id: int) -> None:
    """Link a pipeline job to an offer and set its status_id in one statement.

    Used by POST /api/v1/jobs when a sourcer launches an assigned offer. Dual-writes
    the legacy text `status` to keep recruiter/admin views consistent. Best-effort:
    constrained to non-deleted offers.
    """
    legacy = _LEGACY_TEXT_BY_ID.get(int(status_id), "in_progress")
    sql = """
        UPDATE offers.job_offers
        SET job_id = %s, status_id = %s, status = %s, updated_at = NOW()
        WHERE id = %s AND deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(job_id), int(status_id), legacy, str(offer_id)))
            conn.commit()
