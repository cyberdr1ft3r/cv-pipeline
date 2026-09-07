"""
service/audit_store.py

PostgreSQL-backed append-only audit trail (audit.activity_log).
Schema lives in service/migrations/004_audit_schema.sql.

Connection is read from DATABASE_URL (same as the other stores).

Design rule: log_event() must NEVER raise. An audit failure must not break
the business operation that triggered it — failures are swallowed and logged
as a warning only.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional, Sequence, Union

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()

try:  # app_logger is optional; fall back to a module logger if unavailable
    from service.logging_config import app_logger as _logger
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger("audit_store")


def _connect() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL env var is not set.")
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


class AuditStore:
    """Thin wrapper around audit.activity_log."""

    def log_event(
        self,
        event_type: str,
        description: str,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Insert one audit row. Never raises — swallows + logs any failure."""
        sql = """
            INSERT INTO audit.activity_log
              (event_type, description, actor_id, actor_name,
               target_id, target_type, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """
        try:
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (
                            event_type,
                            description,
                            str(actor_id) if actor_id else None,
                            actor_name,
                            str(target_id) if target_id else None,
                            target_type,
                            json.dumps(metadata or {}),
                        ),
                    )
                    conn.commit()
        except Exception as exc:  # noqa: BLE001 — audit must never break callers
            try:
                _logger.warning(f"Audit log_event failed ({event_type}): {exc}")
            except Exception:
                pass

    def get_recent_activity(
        self,
        limit: int = 20,
        event_type: Optional[Union[str, Sequence[str]]] = None,
        actor_id: Optional[str] = None,
    ) -> List[dict]:
        """Return recent audit rows (newest first).

        Optional filters: event_type (single value or list) and actor_id.
        Returns [] on any failure (audit reads are non-critical).
        """
        clauses: list = []
        params: list = []
        if event_type:
            if isinstance(event_type, (list, tuple, set)):
                clauses.append("event_type = ANY(%s)")
                params.append(list(event_type))
            else:
                clauses.append("event_type = %s")
                params.append(event_type)
        if actor_id:
            clauses.append("actor_id = %s")
            params.append(str(actor_id))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT id, event_type, description, actor_id, actor_name, "
            "target_id, target_type, metadata, created_at "
            f"FROM audit.activity_log{where} "
            "ORDER BY created_at DESC LIMIT %s"
        )
        params.append(limit)
        try:
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(params))
                    rows = cur.fetchall()
            return [
                {
                    "id": str(r["id"]),
                    "event_type": r["event_type"],
                    "description": r["description"],
                    "actor_id": str(r["actor_id"]) if r["actor_id"] else None,
                    "actor_name": r["actor_name"],
                    "target_id": r["target_id"],
                    "target_type": r["target_type"],
                    "metadata": r["metadata"] or {},
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        except Exception as exc:  # noqa: BLE001
            try:
                _logger.warning(f"Audit get_recent_activity failed: {exc}")
            except Exception:
                pass
            return []


# Module-level singleton used across the API.
audit_store = AuditStore()
