"""
service/admin_insights.py

Aggregated CEO dashboard metrics for GET /api/v1/admin/insights.
All sections respect optional date_from / date_to filters.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from service.offer_store import OFFER_STATUSES, _STATUS_BY_ID

psycopg2.extras.register_uuid()

_COMPLETED_JOB_STATUSES = ("succeeded", "completed")
_SCORE_NORM = """
    CASE
      WHEN COALESCE(oa.final_score, oa.matching_score) IS NULL THEN NULL
      WHEN COALESCE(oa.final_score, oa.matching_score) <= 1
        THEN COALESCE(oa.final_score, oa.matching_score) * 100
      ELSE COALESCE(oa.final_score, oa.matching_score)
    END
"""


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


def _period_bounds(
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[Optional[datetime], datetime, dict[str, Any]]:
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to) or date.today()
    ts_from = datetime.combine(d_from, time.min) if d_from else None
    ts_to = datetime.combine(d_to, time.max)
    if d_from:
        label = f"{d_from.isoformat()} — {d_to.isoformat()}"
    else:
        label = "Tout le temps"
    return ts_from, ts_to, {
        "from": d_from.isoformat() if d_from else None,
        "to": d_to.isoformat(),
        "label": label,
    }


def _ts_clause(column: str, ts_from: Optional[datetime], ts_to: datetime) -> tuple[str, list]:
    params: list = []
    parts: list[str] = []
    if ts_from:
        parts.append(f"{column} >= %s")
        params.append(ts_from)
    parts.append(f"{column} <= %s")
    params.append(ts_to)
    return " AND ".join(parts), params


def _empty_stage_counts() -> dict[str, int]:
    return {s["code"]: 0 for s in OFFER_STATUSES}


_SCORE_BUCKETS = ("0-49%", "50-59%", "60-79%", "80-100%")

_SCORE_BUCKET_EXPR = f"""
CASE
  WHEN ({_SCORE_NORM}) IS NULL THEN NULL
  WHEN ({_SCORE_NORM}) < 50 THEN '0-49%%'
  WHEN ({_SCORE_NORM}) < 60 THEN '50-59%%'
  WHEN ({_SCORE_NORM}) < 80 THEN '60-79%%'
  ELSE '80-100%%'
END
"""


def _empty_score_distribution() -> list[dict[str, Any]]:
    return [{"range": r, "count": 0} for r in _SCORE_BUCKETS]


def _rows_to_score_distribution(rows: list[dict]) -> list[dict[str, Any]]:
    counts = {r["range"]: int(r["count"]) for r in rows if r.get("range")}
    return [{"range": r, "count": counts.get(r, 0)} for r in _SCORE_BUCKETS]


def _query_score_distribution(
    cur,
    join_sql: str,
    where_sql: str,
    params: list,
) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT bucket AS range, COUNT(*) AS cnt
        FROM (
          SELECT {_SCORE_BUCKET_EXPR} AS bucket
          FROM candidates.offer_appearances oa
          {join_sql}
          WHERE oa.matching_score IS NOT NULL
            AND {_SCORE_BUCKET_EXPR} IS NOT NULL
            AND {where_sql}
        ) scored
        GROUP BY bucket
        """,
        params,
    )
    return _rows_to_score_distribution(
        [{"range": r["range"], "count": r["cnt"]} for r in cur.fetchall()]
    )


def _compute_recruiting_team_aggregated(
    cur,
    ts_from: Optional[datetime],
    ts_to: datetime,
    offer_ts: str,
    offer_params: list,
) -> dict[str, Any]:
    from service.recruiter_kpis import compute_recruiter_kpis

    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM offers.job_offers jo
        WHERE jo.deleted_at IS NULL AND {offer_ts}
        """,
        offer_params,
    )
    total_created = int(cur.fetchone()["cnt"] or 0)

    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM offers.job_offers jo
        WHERE jo.deleted_at IS NULL
          AND jo.assigned_to IS NOT NULL
          AND {offer_ts}
        """,
        offer_params,
    )
    total_assigned = int(cur.fetchone()["cnt"] or 0)

    cur.execute(
        f"""
        SELECT AVG({_SCORE_NORM}) AS avg_score
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        WHERE jo.deleted_at IS NULL
          AND oa.matching_score IS NOT NULL
          AND {offer_ts}
        """,
        offer_params,
    )
    avg_score_raw = cur.fetchone()["avg_score"]
    avg_matching_score = (
        round(float(avg_score_raw), 1) if avg_score_raw is not None else None
    )

    kpi = compute_recruiter_kpis(cur, None, ts_from, ts_to)
    feedback = dict(kpi["client_feedback"])
    feedback.pop("total_with_feedback", None)

    return {
        "total_offers_created": total_created,
        "total_offers_assigned": total_assigned,
        "avg_matching_to_format_hours": kpi["avg_matching_to_format_hours"],
        "avg_matching_to_format_display": kpi["avg_matching_to_format_display"],
        "avg_format_to_client_hours": kpi["avg_format_to_client_hours"],
        "avg_format_to_client_display": kpi["avg_format_to_client_display"],
        "candidates_validated": kpi["candidates_selected_validated"],
        "client_feedback": feedback,
        "avg_matching_score": avg_matching_score,
    }


def _compute_recruiting_team_charts(
    cur,
    ts_from: Optional[datetime],
    ts_to: datetime,
    offer_ts: str,
    offer_params: list,
) -> dict[str, Any]:
    cur.execute(
        f"""
        SELECT to_char(jo.created_at, 'YYYY-MM') AS month,
               COUNT(*) AS created,
               COUNT(*) FILTER (WHERE jo.assigned_to IS NOT NULL) AS assigned
        FROM offers.job_offers jo
        WHERE jo.deleted_at IS NULL AND {offer_ts}
        GROUP BY 1
        ORDER BY 1
        """,
        offer_params,
    )
    offers_by_month = [
        {
            "month": r["month"],
            "created": int(r["created"]),
            "assigned": int(r["assigned"]),
        }
        for r in cur.fetchall()
    ]

    scope_parts = ["jo.deleted_at IS NULL"]
    trend_params: list = []
    if ts_from:
        scope_parts.append("jf.format_completed_at >= %s")
        trend_params.append(ts_from)
    scope_parts.append("jf.format_completed_at <= %s")
    trend_params.append(ts_to)
    scope_sql = " AND ".join(scope_parts)

    cur.execute(
        f"""
        SELECT to_char(jf.format_completed_at, 'YYYY-MM') AS month,
               AVG(
                 EXTRACT(EPOCH FROM (jf.format_completed_at - jm.matching_ts)) / 3600.0
               ) AS matching_to_format_hours
        FROM offers.job_offers jo
        JOIN jobs.pipeline_jobs jf ON jf.id = jo.job_id
        JOIN LATERAL (
          SELECT MIN(COALESCE(j.matching_completed_at, j.completed_at)) AS matching_ts
          FROM jobs.pipeline_jobs j
          WHERE j.offer_id = jo.id
            AND COALESCE(j.matching_completed_at, j.completed_at) IS NOT NULL
        ) jm ON jm.matching_ts IS NOT NULL
        WHERE {scope_sql}
          AND jf.format_completed_at IS NOT NULL
          AND jf.format_completed_at > jm.matching_ts
        GROUP BY 1
        ORDER BY 1
        """,
        trend_params,
    )
    mf_by_month = {
        r["month"]: round(float(r["matching_to_format_hours"]), 2)
        if r["matching_to_format_hours"] is not None else None
        for r in cur.fetchall()
    }

    # Format → client delay from status history (status_id = 2 = envoyé client),
    # preserved even after the candidate moves to a later status.
    cur.execute(
        f"""
        SELECT to_char(jf.format_completed_at, 'YYYY-MM') AS month,
               AVG(
                 EXTRACT(EPOCH FROM (sent.first_at - jf.format_completed_at)) / 3600.0
               ) AS format_to_client_hours
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
        WHERE {scope_sql}
          AND jf.format_completed_at IS NOT NULL
          AND sent.first_at >= jf.format_completed_at
        GROUP BY 1
        ORDER BY 1
        """,
        trend_params,
    )
    fc_by_month = {
        r["month"]: round(float(r["format_to_client_hours"]), 2)
        if r["format_to_client_hours"] is not None else None
        for r in cur.fetchall()
    }
    all_months = sorted(set(mf_by_month) | set(fc_by_month))
    pipeline_to_client_trend = [
        {
            "month": m,
            "matching_to_format_hours": mf_by_month.get(m),
            "format_to_client_hours": fc_by_month.get(m),
        }
        for m in all_months
    ]

    score_distribution = _query_score_distribution(
        cur,
        "JOIN offers.job_offers jo ON jo.id = oa.offer_id",
        f"jo.deleted_at IS NULL AND {offer_ts}",
        offer_params,
    )

    return {
        "offers_by_month": offers_by_month,
        "pipeline_to_client_trend": pipeline_to_client_trend,
        "score_distribution": score_distribution,
    }


def _compute_recruiting_team_members(
    cur,
    ts_from: Optional[datetime],
    ts_to: datetime,
    offer_ts: str,
    offer_params: list,
    hire_ts: str,
    hire_params: list,
) -> list[dict[str, Any]]:
    from service.recruiter_kpis import compute_recruiter_kpis

    cur.execute(
        f"""
        SELECT u.id::text AS id,
               u.full_name,
               (
                 SELECT COUNT(*)
                 FROM offers.job_offers jo
                 WHERE jo.created_by = u.id
                   AND jo.deleted_at IS NULL
                   AND {offer_ts}
               ) AS offers_created,
               (
                 SELECT COUNT(*)
                 FROM offers.job_offers jo
                 WHERE jo.created_by = u.id
                   AND jo.deleted_at IS NULL
                   AND jo.assigned_to IS NOT NULL
                   AND {offer_ts}
               ) AS offers_assigned,
               (
                 SELECT AVG({_SCORE_NORM})
                 FROM candidates.offer_appearances oa
                 JOIN offers.job_offers jo2 ON jo2.id = oa.offer_id
                 WHERE jo2.created_by = u.id
                   AND jo2.deleted_at IS NULL
                   AND oa.matching_score IS NOT NULL
               ) AS avg_matching_score,
               (
                 SELECT COUNT(*)
                 FROM candidates.offer_appearances oa
                 JOIN offers.job_offers jo2 ON jo2.id = oa.offer_id
                 WHERE jo2.created_by = u.id
                   AND jo2.deleted_at IS NULL
                   AND oa.format_status_id = 6
                   AND {offer_ts.replace('jo.created_at', 'jo2.created_at')}
               ) AS hired_candidates,
               GREATEST(
                 (SELECT MAX(jo.updated_at)
                  FROM offers.job_offers jo
                  WHERE jo.created_by = u.id),
                 u.last_login_at
               ) AS last_active
        FROM auth.users u
        WHERE u.role = 'recruiter' AND u.deleted_at IS NULL
        ORDER BY offers_created DESC, u.full_name
        """,
        [*offer_params, *offer_params, *offer_params],
    )
    members = []
    for r in cur.fetchall():
        la = r["last_active"]
        kpi = compute_recruiter_kpis(cur, r["id"], ts_from, ts_to)
        feedback = dict(kpi["client_feedback"])
        feedback.pop("total_with_feedback", None)
        members.append({
            "id": r["id"],
            "full_name": r["full_name"],
            "offers_created": int(r["offers_created"] or 0),
            "offers_assigned": int(r["offers_assigned"] or 0),
            "avg_matching_score": (
                round(float(r["avg_matching_score"]), 1)
                if r["avg_matching_score"] is not None else None
            ),
            "matching_to_format_display": kpi["avg_matching_to_format_display"],
            "matching_to_format_hours": kpi["avg_matching_to_format_hours"],
            "format_to_client_display": kpi["avg_format_to_client_display"],
            "format_to_client_hours": kpi["avg_format_to_client_hours"],
            "candidates_validated": kpi["candidates_selected_validated"],
            "client_feedback": feedback,
            "client_feedback_compact": kpi["client_feedback_compact"],
            "hired_candidates": int(r["hired_candidates"] or 0),
            "last_active": la.date().isoformat() if la else None,
        })
    return members


def _compute_sourcing_team_aggregated(
    cur,
    offer_ts: str,
    offer_params: list,
    job_ts: str,
    job_params: list,
) -> dict[str, Any]:
    # Pipeline / CV-count aggregates. No offer_appearances join here: it would
    # multiply each offer row by its number of candidates and inflate
    # SUM(cv_count). avg_score is computed separately below.
    cur.execute(
        f"""
        SELECT
          COUNT(DISTINCT jo.id) AS offers_assigned,
          COUNT(DISTINCT j.id) AS pipelines_launched,
          COUNT(DISTINCT j.id) FILTER (WHERE j.status = ANY(%s)) AS pipelines_succeeded,
          COUNT(DISTINCT j.id) FILTER (WHERE j.status = 'failed') AS pipelines_failed,
          COALESCE(SUM(j.cv_count) FILTER (WHERE j.status = ANY(%s)), 0) AS candidates_scored,
          COUNT(DISTINCT jo.id) FILTER (
            WHERE jo.status_id = 2 AND (jo.job_id IS NULL OR j.id IS NULL)
          ) AS offers_pending_launch
        FROM offers.job_offers jo
        JOIN auth.users u ON u.id = jo.assigned_to AND u.role = 'sourcer'
        LEFT JOIN jobs.pipeline_jobs j ON j.id = jo.job_id AND {job_ts}
        WHERE jo.deleted_at IS NULL AND {offer_ts}
        """,
        [
            list(_COMPLETED_JOB_STATUSES),
            list(_COMPLETED_JOB_STATUSES),
            *job_params,
            *offer_params,
        ],
    )
    row = dict(cur.fetchone())
    launched = int(row["pipelines_launched"] or 0)
    succeeded = int(row["pipelines_succeeded"] or 0)
    failed = int(row["pipelines_failed"] or 0)
    finished = succeeded + failed
    success_rate = round(succeeded / finished * 100, 1) if finished else None
    candidates_scored = int(row["candidates_scored"] or 0)
    avg_per_pipeline = (
        round(candidates_scored / succeeded, 1) if succeeded else None
    )

    cur.execute(
        f"""
        SELECT AVG({_SCORE_NORM}) AS avg_score
        FROM candidates.offer_appearances oa
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        JOIN auth.users u ON u.id = jo.assigned_to AND u.role = 'sourcer'
        WHERE jo.deleted_at IS NULL AND {offer_ts}
        """,
        offer_params,
    )
    avg_score_raw = cur.fetchone()["avg_score"]

    return {
        "total_offers_assigned": int(row["offers_assigned"] or 0),
        "total_pipelines_launched": launched,
        "pipelines_success_rate_percent": success_rate,
        "total_candidates_scored": candidates_scored,
        "avg_candidates_per_pipeline": avg_per_pipeline,
        "avg_matching_score": (
            round(float(avg_score_raw), 1) if avg_score_raw is not None else None
        ),
        "offers_pending_launch": int(row["offers_pending_launch"] or 0),
    }


def _compute_sourcing_team_charts(
    cur,
    offer_ts: str,
    offer_params: list,
    job_ts: str,
    job_params: list,
) -> dict[str, Any]:
    cur.execute(
        f"""
        SELECT to_char(j.created_at, 'YYYY-MM') AS month,
               COUNT(*) AS launched,
               COUNT(*) FILTER (WHERE j.status = ANY(%s)) AS succeeded,
               COUNT(*) FILTER (WHERE j.status = 'failed') AS failed
        FROM jobs.pipeline_jobs j
        JOIN offers.job_offers jo ON jo.id = j.offer_id
        JOIN auth.users u ON u.id = jo.assigned_to AND u.role = 'sourcer'
        WHERE jo.deleted_at IS NULL AND {job_ts}
        GROUP BY 1
        ORDER BY 1
        """,
        [list(_COMPLETED_JOB_STATUSES), *job_params],
    )
    pipelines_by_month = [
        {
            "month": r["month"],
            "launched": int(r["launched"]),
            "succeeded": int(r["succeeded"]),
            "failed": int(r["failed"]),
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        f"""
        SELECT to_char(j.created_at, 'YYYY-MM') AS month,
               COALESCE(SUM(j.cv_count) FILTER (WHERE j.status = ANY(%s)), 0) AS count
        FROM jobs.pipeline_jobs j
        JOIN offers.job_offers jo ON jo.id = j.offer_id
        JOIN auth.users u ON u.id = jo.assigned_to AND u.role = 'sourcer'
        WHERE jo.deleted_at IS NULL AND {job_ts}
        GROUP BY 1
        ORDER BY 1
        """,
        [list(_COMPLETED_JOB_STATUSES), *job_params],
    )
    candidates_scored_by_month = [
        {"month": r["month"], "count": int(r["count"] or 0)}
        for r in cur.fetchall()
    ]

    score_distribution = _query_score_distribution(
        cur,
        """
        JOIN offers.job_offers jo ON jo.id = oa.offer_id
        JOIN auth.users u ON u.id = jo.assigned_to AND u.role = 'sourcer'
        """,
        f"jo.deleted_at IS NULL AND {offer_ts}",
        offer_params,
    )

    return {
        "pipelines_by_month": pipelines_by_month,
        "candidates_scored_by_month": candidates_scored_by_month,
        "score_distribution": score_distribution,
    }


def _compute_sourcing_team_members(
    cur,
    offer_ts: str,
    offer_params: list,
    job_ts: str,
    job_params: list,
) -> list[dict[str, Any]]:
    # No offer_appearances join in the main query: it would multiply each offer
    # row by its candidate count and inflate SUM(cv_count). avg_score comes from
    # a correlated subquery over the sourcer's appearances.
    cur.execute(
        f"""
        SELECT u.id::text AS id,
               u.full_name,
               COUNT(DISTINCT jo.id) AS offers_assigned,
               COUNT(DISTINCT j.id) AS pipelines_launched,
               COALESCE(SUM(j.cv_count) FILTER (WHERE j.status = ANY(%s)), 0) AS candidates_scored,
               (
                 SELECT AVG({_SCORE_NORM.replace('oa.', 'oa2.')})
                 FROM candidates.offer_appearances oa2
                 JOIN offers.job_offers jo2 ON jo2.id = oa2.offer_id
                 WHERE jo2.assigned_to = u.id
                   AND jo2.deleted_at IS NULL
                   AND {offer_ts.replace('jo.created_at', 'jo2.created_at')}
               ) AS avg_score,
               COUNT(DISTINCT jo.id) FILTER (WHERE jo.status_id >= 4) AS offers_matched,
               GREATEST(MAX(jo.updated_at), MAX(u.last_login_at)) AS last_active
        FROM auth.users u
        LEFT JOIN offers.job_offers jo
          ON jo.assigned_to = u.id
         AND jo.deleted_at IS NULL
         AND {offer_ts}
        LEFT JOIN jobs.pipeline_jobs j
          ON j.id = jo.job_id
         AND {job_ts}
        WHERE u.role = 'sourcer' AND u.deleted_at IS NULL
        GROUP BY u.id, u.full_name
        ORDER BY pipelines_launched DESC, offers_assigned DESC, u.full_name
        """,
        [list(_COMPLETED_JOB_STATUSES), *offer_params, *offer_params, *job_params],
    )
    members = []
    for r in cur.fetchall():
        la = r["last_active"]
        assigned = int(r["offers_assigned"] or 0)
        matched = int(r["offers_matched"] or 0)
        scored = int(r["candidates_scored"] or 0)
        pipelines = int(r["pipelines_launched"] or 0)
        members.append({
            "id": r["id"],
            "full_name": r["full_name"],
            "offers_assigned": assigned,
            "pipelines_launched": pipelines,
            "candidates_scored": scored,
            "avg_candidates_matched": (
                round(scored / pipelines, 1) if pipelines else None
            ),
            "avg_score": (
                round(float(r["avg_score"]), 1)
                if r["avg_score"] is not None else None
            ),
            "offers_completed_percent": (
                round(matched / assigned * 100, 1) if assigned else None
            ),
            "last_active": la.date().isoformat() if la else None,
        })
    return members


def _build_team_activity(
    cur,
    ts_from: Optional[datetime],
    ts_to: datetime,
    offer_ts: str,
    offer_params: list,
    job_ts: str,
    job_params: list,
    hire_ts: str,
    hire_params: list,
) -> dict[str, Any]:
    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE role = 'recruiter') AS recruiters,
               COUNT(*) FILTER (WHERE role = 'sourcer') AS sourcers
        FROM auth.users
        WHERE deleted_at IS NULL AND is_active
        """
    )
    team_counts = dict(cur.fetchone())

    recruiting_agg = _compute_recruiting_team_aggregated(
        cur, ts_from, ts_to, offer_ts, offer_params,
    )
    recruiting_charts = _compute_recruiting_team_charts(
        cur, ts_from, ts_to, offer_ts, offer_params,
    )
    recruiting_members = _compute_recruiting_team_members(
        cur, ts_from, ts_to, offer_ts, offer_params, hire_ts, hire_params,
    )
    sourcing_agg = _compute_sourcing_team_aggregated(
        cur, offer_ts, offer_params, job_ts, job_params,
    )
    sourcing_charts = _compute_sourcing_team_charts(
        cur, offer_ts, offer_params, job_ts, job_params,
    )
    sourcing_members = _compute_sourcing_team_members(
        cur, offer_ts, offer_params, job_ts, job_params,
    )

    return {
        "total_recruiters": int(team_counts.get("recruiters") or 0),
        "total_sourcers": int(team_counts.get("sourcers") or 0),
        "recruiting_team": {
            "aggregated": recruiting_agg,
            "charts": recruiting_charts,
            "members": recruiting_members,
        },
        "sourcing_team": {
            "aggregated": sourcing_agg,
            "charts": sourcing_charts,
            "members": sourcing_members,
        },
    }


def get_admin_insights(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict[str, Any]:
    ts_from, ts_to, period = _period_bounds(date_from, date_to)
    offer_ts, offer_params = _ts_clause("jo.created_at", ts_from, ts_to)
    job_ts, job_params = _ts_clause("j.created_at", ts_from, ts_to)
    cand_ts, cand_params = _ts_clause("p.created_at", ts_from, ts_to)
    hire_ts, hire_params = _ts_clause("oa.decision_at", ts_from, ts_to)

    with _connect() as conn:
        with conn.cursor() as cur:
            # ── Business KPIs ─────────────────────────────────────────────
            cur.execute(
                f"""
                SELECT status_id, COUNT(*) AS cnt
                FROM offers.job_offers jo
                WHERE jo.deleted_at IS NULL AND {offer_ts}
                GROUP BY status_id
                """,
                offer_params,
            )
            by_stage = _empty_stage_counts()
            total_offers = 0
            for row in cur.fetchall():
                meta = _STATUS_BY_ID.get(int(row["status_id"] or 1), _STATUS_BY_ID[1])
                by_stage[meta["code"]] = int(row["cnt"])
                total_offers += int(row["cnt"])

            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM offers.job_offers jo
                WHERE jo.deleted_at IS NULL
                  AND jo.status_id = 3
                  AND {offer_ts.replace('jo.created_at', 'jo.updated_at')}
                """,
                offer_params,
            )
            missions_in_progress = int(cur.fetchone()["cnt"])

            # "Recrutés" = candidats au statut format « recruté » (id 6), cohérent
            # avec l'espace recruteur et le retour client. Le champ oa.decision
            # n'est pas alimenté par le workflow recruteur (statut /status).
            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM candidates.offer_appearances oa
                JOIN offers.job_offers jo ON jo.id = oa.offer_id
                WHERE jo.deleted_at IS NULL
                  AND oa.format_status_id = 6
                  AND {offer_ts}
                """,
                offer_params,
            )
            hired_candidates = int(cur.fetchone()["cnt"])

            cur.execute(
                f"""
                SELECT AVG(
                  EXTRACT(EPOCH FROM (j.completed_at - j.created_at)) / 3600.0
                ) AS avg_hours
                FROM jobs.pipeline_jobs j
                WHERE j.status = ANY(%s)
                  AND j.completed_at IS NOT NULL
                  AND j.created_at IS NOT NULL
                  AND {job_ts.replace('j.created_at', 'j.completed_at')}
                """,
                [list(_COMPLETED_JOB_STATUSES), *job_params],
            )
            avg_match_hours_raw = cur.fetchone()["avg_hours"]
            avg_time_to_match_hours = (
                round(float(avg_match_hours_raw), 1) if avg_match_hours_raw is not None else None
            )

            # ── Pipeline performance ──────────────────────────────────────
            cur.execute(
                f"""
                SELECT
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE j.status = ANY(%s)) AS completed,
                  COUNT(*) FILTER (WHERE j.status = 'failed') AS failed,
                  AVG(
                    CASE WHEN j.status = ANY(%s) AND j.completed_at IS NOT NULL
                         AND j.started_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (j.completed_at - j.started_at)) / 60.0
                    END
                  ) AS avg_proc_min,
                  AVG(j.cv_count) FILTER (WHERE j.status = ANY(%s)) AS avg_cv
                FROM jobs.pipeline_jobs j
                WHERE {job_ts}
                """,
                [list(_COMPLETED_JOB_STATUSES), list(_COMPLETED_JOB_STATUSES), list(_COMPLETED_JOB_STATUSES), *job_params],
            )
            pipe_row = dict(cur.fetchone())
            total_pipelines = int(pipe_row["total"] or 0)
            completed_pipelines = int(pipe_row["completed"] or 0)
            failed_pipelines = int(pipe_row["failed"] or 0)
            finished = completed_pipelines + failed_pipelines
            success_rate = (
                round(completed_pipelines / finished * 100, 1) if finished else None
            )
            avg_proc = pipe_row["avg_proc_min"]
            avg_cv = pipe_row["avg_cv"]

            cur.execute(
                f"""
                SELECT AVG({_SCORE_NORM}) AS avg_score
                FROM candidates.offer_appearances oa
                WHERE oa.matching_score IS NOT NULL
                  AND {hire_ts.replace('oa.decision_at', 'oa.created_at')}
                """,
                cand_params,
            )
            avg_score_raw = cur.fetchone()["avg_score"]
            avg_matching_score = (
                round(float(avg_score_raw), 1) if avg_score_raw is not None else None
            )

            month_job_ts, month_job_params = _ts_clause(
                "COALESCE(j.completed_at, j.created_at)", ts_from, ts_to
            )
            cur.execute(
                f"""
                SELECT to_char(COALESCE(j.completed_at, j.created_at), 'YYYY-MM') AS month,
                       COUNT(*) AS count,
                       COUNT(*) FILTER (WHERE j.status = ANY(%s)) AS success
                FROM jobs.pipeline_jobs j
                WHERE {month_job_ts}
                GROUP BY 1
                ORDER BY 1
                """,
                [list(_COMPLETED_JOB_STATUSES), *month_job_params],
            )
            pipelines_by_month = [
                {
                    "month": r["month"],
                    "count": int(r["count"]),
                    "success": int(r["success"]),
                }
                for r in cur.fetchall()
            ]

            # ── Team activity ─────────────────────────────────────────────
            team_activity = _build_team_activity(
                cur, ts_from, ts_to,
                offer_ts, offer_params,
                job_ts, job_params,
                hire_ts, hire_params,
            )

            # ── Candidate pipeline ────────────────────────────────────────
            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM candidates.profiles p
                WHERE p.deleted_at IS NULL AND {cand_ts}
                """,
                cand_params,
            )
            total_candidates = int(cur.fetchone()["cnt"])

            cur.execute(
                f"""
                SELECT COALESCE(rp.code, p.profile, 'Autre') AS profile,
                       COALESCE(rp.label_fr, p.profile, 'Autre') AS label_fr,
                       COUNT(*) AS cnt
                FROM candidates.profiles p
                LEFT JOIN ref.profiles rp ON rp.id = p.profile_id
                WHERE p.deleted_at IS NULL AND {cand_ts}
                GROUP BY 1, 2
                ORDER BY cnt DESC
                LIMIT 12
                """,
                cand_params,
            )
            candidates_by_profile = [
                {"profile": r["profile"], "label_fr": r["label_fr"], "count": int(r["cnt"])}
                for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                SELECT COALESCE(rs.code, LOWER(p.seniority), 'non_renseigne') AS seniority,
                       COALESCE(rs.label_fr, p.seniority, 'Non renseigné') AS label_fr,
                       COUNT(*) AS cnt
                FROM candidates.profiles p
                LEFT JOIN ref.seniorities rs ON rs.id = p.seniority_id
                WHERE p.deleted_at IS NULL AND {cand_ts}
                GROUP BY 1, 2
                ORDER BY cnt DESC
                """,
                cand_params,
            )
            candidates_by_seniority = [
                {"seniority": r["seniority"], "label_fr": r["label_fr"], "count": int(r["cnt"])}
                for r in cur.fetchall()
            ]

            offer_skill_ts, offer_skill_params = _ts_clause("jo.created_at", ts_from, ts_to)
            cur.execute(
                f"""
                SELECT s.name AS skill,
                       s.category,
                       COUNT(DISTINCT os.offer_id) AS offer_count,
                       COUNT(DISTINCT cs.candidate_id) AS candidate_count
                FROM ref.skills s
                JOIN offers.offer_skills os ON os.skill_id = s.id
                JOIN offers.job_offers jo ON jo.id = os.offer_id
                  AND jo.deleted_at IS NULL AND {offer_skill_ts}
                LEFT JOIN candidates.candidate_skills cs ON cs.skill_id = s.id
                LEFT JOIN candidates.profiles p ON p.id = cs.candidate_id
                  AND p.deleted_at IS NULL
                GROUP BY s.id, s.name, s.category
                ORDER BY offer_count DESC, candidate_count DESC
                LIMIT 10
                """,
                offer_skill_params,
            )
            top_skills = [
                {
                    "skill": r["skill"],
                    "category": r["category"],
                    "offer_count": int(r["offer_count"]),
                    "candidate_count": int(r["candidate_count"] or 0),
                }
                for r in cur.fetchall()
            ]

            skills_gap = sorted(
                [
                    {
                        "skill": s["skill"],
                        "offer_demand": s["offer_count"],
                        "candidate_supply": s["candidate_count"],
                        "gap": s["offer_count"] - s["candidate_count"],
                    }
                    for s in top_skills
                    if s["offer_count"] > s["candidate_count"]
                ],
                key=lambda x: x["gap"],
                reverse=True,
            )[:5]

            cur.execute(
                f"""
                SELECT to_char(p.created_at, 'YYYY-MM') AS month,
                       COUNT(*) AS count
                FROM candidates.profiles p
                WHERE p.deleted_at IS NULL AND {cand_ts}
                GROUP BY 1
                ORDER BY 1
                """,
                cand_params,
            )
            new_candidates_by_month = [
                {"month": r["month"], "count": int(r["count"])}
                for r in cur.fetchall()
            ]

            # ── Recruitment efficiency (CEO-facing) ─────────────────────
            cur.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE jo.assigned_to IS NOT NULL) AS assigned,
                  COUNT(*) FILTER (WHERE jo.status_id >= 4) AS matched
                FROM offers.job_offers jo
                WHERE jo.deleted_at IS NULL AND {offer_ts}
                """,
                offer_params,
            )
            funnel_row = dict(cur.fetchone())
            offers_assigned = int(funnel_row["assigned"] or 0)
            offers_matched = int(funnel_row["matched"] or 0)

            appear_ts, appear_params = _ts_clause("oa.created_at", ts_from, ts_to)
            cur.execute(
                f"""
                SELECT
                  COUNT(DISTINCT oa.candidate_id) AS evaluated,
                  COUNT(*) FILTER (WHERE oa.decision = 'shortlisted') AS shortlisted
                FROM candidates.offer_appearances oa
                JOIN offers.job_offers jo ON jo.id = oa.offer_id
                WHERE jo.deleted_at IS NULL AND {appear_ts}
                """,
                appear_params,
            )
            appear_row = dict(cur.fetchone())
            candidates_evaluated = int(appear_row["evaluated"] or 0)
            candidates_shortlisted = int(appear_row["shortlisted"] or 0)

            offer_to_match = (
                round(offers_matched / total_offers * 100, 1)
                if total_offers else None
            )
            match_to_hire = (
                round(hired_candidates / offers_matched * 100, 1)
                if offers_matched else None
            )
            avg_candidates_per_offer = (
                round(candidates_evaluated / offers_matched, 1)
                if offers_matched else None
            )

            cur.execute(
                f"""
                SELECT to_char(jo.created_at, 'YYYY-MM') AS month,
                       COUNT(DISTINCT jo.id) FILTER (WHERE jo.status_id >= 4) AS offers_matched,
                       COUNT(DISTINCT oa.candidate_id) AS candidates_evaluated,
                       COUNT(DISTINCT oa.id) FILTER (
                         WHERE oa.format_status_id = 6
                       ) AS hired
                FROM offers.job_offers jo
                LEFT JOIN candidates.offer_appearances oa ON oa.offer_id = jo.id
                WHERE jo.deleted_at IS NULL AND {offer_ts}
                GROUP BY 1
                ORDER BY 1
                """,
                offer_params,
            )
            outcomes_by_month = [
                {
                    "month": r["month"],
                    "offers_matched": int(r["offers_matched"] or 0),
                    "candidates_evaluated": int(r["candidates_evaluated"] or 0),
                    "hired": int(r["hired"] or 0),
                }
                for r in cur.fetchall()
            ]

    return {
        "period": period,
        "business_kpis": {
            "total_offers": total_offers,
            "offers_by_status": by_stage,
            "avg_time_to_match_hours": avg_time_to_match_hours,
            "hired_candidates": hired_candidates,
            "total_missions_in_progress": missions_in_progress,
        },
        "pipeline_performance": {
            "total_pipelines_run": total_pipelines,
            "success_rate_percent": success_rate,
            "failed_pipelines": failed_pipelines,
            "avg_matching_score": avg_matching_score,
            "avg_cv_count_per_offer": (
                round(float(avg_cv), 1) if avg_cv is not None else None
            ),
            "avg_processing_time_minutes": (
                round(float(avg_proc), 1) if avg_proc is not None else None
            ),
            "pipelines_by_month": pipelines_by_month,
        },
        "recruitment_efficiency": {
            "funnel": {
                "offers_created": total_offers,
                "offers_assigned": offers_assigned,
                "offers_matched": offers_matched,
                "candidates_evaluated": candidates_evaluated,
                "candidates_shortlisted": candidates_shortlisted,
                "hired": hired_candidates,
            },
            "conversion_offer_to_match_percent": offer_to_match,
            "conversion_match_to_hire_percent": match_to_hire,
            "avg_candidates_per_matched_offer": avg_candidates_per_offer,
            "avg_matching_score": avg_matching_score,
            "avg_time_to_match_hours": avg_time_to_match_hours,
            "outcomes_by_month": outcomes_by_month,
        },
        "team_activity": team_activity,
        "candidate_pipeline": {
            "total_candidates": total_candidates,
            "candidates_by_profile": candidates_by_profile,
            "candidates_by_seniority": candidates_by_seniority,
            "top_skills_in_demand": top_skills,
            "skills_gap": skills_gap,
            "new_candidates_by_month": new_candidates_by_month,
        },
    }
