"""
Recruiter performance KPIs (Action 283).

Metrics: matching→format delay, format→client delay,
selected/validated candidates, client feedback breakdown.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any, Optional

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()

_FEEDBACK_CODES = ("envoye_client", "recrute", "non_integre", "rejete", "valide_client", "non_valide_client")


def _connect() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL env var is not set.")
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def format_duration_display(hours: Optional[float]) -> Optional[str]:
    """French duration: '2j 4h' if >=24h, else '5h 30min'. None if no data."""
    if hours is None:
        return None
    if hours <= 0:
        return None
    total_minutes = int(round(hours * 60))
    if total_minutes <= 0:
        return None
    if hours >= 24:
        days = int(hours // 24)
        rem_h = int(hours % 24)
        if rem_h == 0:
            return f"{days}j"
        return f"{days}j {rem_h}h"
    h = int(hours)
    m = int(round((hours - h) * 60))
    if h == 0:
        return f"{m} min"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}min"


def format_client_feedback_display(feedback: dict[str, int]) -> str:
    pending = int(feedback.get("envoye_attente") or 0)
    r = int(feedback.get("recrute") or 0)
    ni = int(feedback.get("non_integre") or 0)
    rej = int(feedback.get("rejete") or 0)
    responded = r + ni + rej + int(feedback.get("valide_client") or 0) + int(feedback.get("non_valide_client") or 0)
    if pending == 0 and responded == 0:
        return "—"
    parts: list[str] = []
    if pending > 0:
        parts.append(f"{pending} en attente")
    if r + ni + rej > 0:
        parts.append(f"{r}✓ {ni}✗ {rej}⊘")
    return " · ".join(parts)


def format_client_feedback_compact(feedback: dict[str, int]) -> str:
    pending = int(feedback.get("envoye_attente") or 0)
    r = int(feedback.get("recrute") or 0)
    ni = int(feedback.get("non_integre") or 0)
    rej = int(feedback.get("rejete") or 0)
    if pending == 0 and r + ni + rej == 0:
        return "—"
    if pending > 0 and r + ni + rej == 0:
        return f"{pending} att."
    if pending > 0:
        return f"{pending}/{r}/{ni}/{rej}"
    return f"{r}/{ni}/{rej}"


def _period_bounds(
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[Optional[datetime], datetime]:
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to) or date.today()
    ts_from = datetime.combine(d_from, time.min) if d_from else None
    ts_to = datetime.combine(d_to, time.max)
    return ts_from, ts_to


def _offer_scope_sql(
    recruiter_id: Optional[str],
    ts_from: Optional[datetime],
    ts_to: datetime,
    alias: str = "jo",
) -> tuple[str, list]:
    parts = [f"{alias}.deleted_at IS NULL"]
    params: list = []
    if recruiter_id:
        parts.append(f"{alias}.created_by = %s::uuid")
        params.append(recruiter_id)
    if ts_from:
        parts.append(f"{alias}.created_at >= %s")
        params.append(ts_from)
    parts.append(f"{alias}.created_at <= %s")
    params.append(ts_to)
    return " AND ".join(parts), params


def _positive_kpi_hours(raw: Optional[float]) -> Optional[float]:
    """Keep sub-hour precision so ~2 min is not rounded to 0.0 before display."""
    if raw is None:
        return None
    hours = float(raw)
    if hours <= 0:
        return None
    return hours


def _export_kpi_hours(hours: Optional[float]) -> Optional[float]:
    if hours is None:
        return None
    return round(hours, 2) if hours < 1 else round(hours, 1)


def _empty_feedback() -> dict[str, int]:
    fb = {code: 0 for code in _FEEDBACK_CODES}
    fb["envoye_attente"] = 0
    fb["total_with_feedback"] = 0
    return fb


def compute_recruiter_kpis(
    cur,
    recruiter_id: Optional[str],
    ts_from: Optional[datetime],
    ts_to: datetime,
) -> dict[str, Any]:
    scope, scope_params = _offer_scope_sql(recruiter_id, ts_from, ts_to)

    cur.execute(
        f"""
        SELECT AVG(
          EXTRACT(EPOCH FROM (jf.format_completed_at - jm.matching_ts)) / 3600.0
        ) AS avg_hours
        FROM offers.job_offers jo
        JOIN jobs.pipeline_jobs jf ON jf.id = jo.job_id
          AND jf.format_completed_at IS NOT NULL
        JOIN LATERAL (
          SELECT MIN(COALESCE(j.matching_completed_at, j.completed_at)) AS matching_ts
          FROM jobs.pipeline_jobs j
          WHERE j.offer_id = jo.id
            AND COALESCE(j.matching_completed_at, j.completed_at) IS NOT NULL
            AND (
              j.matching_completed_at IS NOT NULL
              OR j.stage IN (
                'matching_complete', 'running_final', 'final_complete',
                'running_format', 'format_complete'
              )
            )
        ) jm ON jm.matching_ts IS NOT NULL
        WHERE {scope}
          AND jf.format_completed_at > jm.matching_ts
        """,
        scope_params,
    )
    avg_mf_raw = cur.fetchone()["avg_hours"]
    avg_matching_to_format_hours = _positive_kpi_hours(avg_mf_raw)

    # Format → client delay reads the FIRST "envoyé au client" timestamp from
    # the status history (status_id = 2), so the value is preserved even after
    # the candidate moves on to a later status (recruté, validé client, …).
    # The current-status fallback only applies when the appearance is still at
    # envoye_client and (defensively) has no history row.
    cur.execute(
        f"""
        SELECT AVG(
          EXTRACT(EPOCH FROM (sent.first_at - jf.format_completed_at)) / 3600.0
        ) AS avg_hours
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        JOIN jobs.pipeline_jobs jf ON jf.id = jo.job_id
        JOIN LATERAL (
          SELECT COALESCE(
            (
              SELECT MIN(h.changed_at)
              FROM candidates.appearance_status_history h
              WHERE h.appearance_id = oa.id
                AND h.phase = 'format'
                AND h.status_id = 2
            ),
            CASE WHEN oa.format_status_id = 2 THEN oa.format_status_changed_at END
          ) AS first_at
        ) sent ON sent.first_at IS NOT NULL
        WHERE {scope}
          AND jf.format_completed_at IS NOT NULL
          AND sent.first_at >= jf.format_completed_at
        """,
        scope_params,
    )
    avg_fc_raw = cur.fetchone()["avg_hours"]
    avg_format_to_client_hours = _positive_kpi_hours(avg_fc_raw)

    cur.execute(
        f"""
        SELECT COUNT(DISTINCT oa.id) AS cnt
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        LEFT JOIN ref.final_statuses fs ON fs.id = oa.final_status_id
        LEFT JOIN ref.format_statuses fts ON fts.id = oa.format_status_id
        WHERE {scope}
          AND (
            fs.code = 'valide'
            OR fts.code IN ('offre_faite', 'recrute', 'valide_client')
          )
        """,
        scope_params,
    )
    candidates_selected_validated = int(cur.fetchone()["cnt"] or 0)

    cur.execute(
        f"""
        SELECT fts.code, COUNT(*) AS cnt
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        JOIN ref.format_statuses fts ON fts.id = oa.format_status_id
        WHERE {scope}
          AND fts.code = ANY(%s)
        GROUP BY fts.code
        """,
        [*scope_params, list(_FEEDBACK_CODES)],
    )
    client_feedback = _empty_feedback()
    for row in cur.fetchall():
        code = row["code"]
        cnt = int(row["cnt"] or 0)
        if code == "envoye_client":
            client_feedback["envoye_attente"] = cnt
        else:
            client_feedback[code] = cnt
        client_feedback["total_with_feedback"] += cnt

    return {
        "avg_matching_to_format_hours": _export_kpi_hours(avg_matching_to_format_hours),
        "avg_matching_to_format_display": format_duration_display(avg_matching_to_format_hours),
        "avg_format_to_client_hours": _export_kpi_hours(avg_format_to_client_hours),
        "avg_format_to_client_display": format_duration_display(avg_format_to_client_hours),
        "candidates_selected_validated": candidates_selected_validated,
        "client_feedback": client_feedback,
        "client_feedback_display": format_client_feedback_display(client_feedback),
        "client_feedback_compact": format_client_feedback_compact(client_feedback),
    }


def get_recruiter_kpis(
    recruiter_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict[str, Any]:
    ts_from, ts_to = _period_bounds(date_from, date_to)
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return compute_recruiter_kpis(cur, recruiter_id, ts_from, ts_to)
