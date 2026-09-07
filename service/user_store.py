"""
service/user_store.py

PostgreSQL-backed user store for the auth.users table.
Schema lives in service/migrations/001_auth_offers_schema.sql.

Connection is read from DATABASE_URL environment variable.
Pattern mirrors service/job_store.py but targets PostgreSQL, not SQLite.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()  # lets psycopg2 map UUID ↔ Python uuid.UUID


@dataclass
class User:
    id: UUID
    email: str
    full_name: str
    role: str          # sourcer | recruiter | admin
    hashed_password: str
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


def _connect() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL env var is not set. "
            "Add it to config/.env (e.g. postgresql://postgres:password@localhost:5432/cv_pipeline)"
        )
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _row_to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        hashed_password=row["hashed_password"],
        is_active=row["is_active"],
        last_login_at=row.get("last_login_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row.get("deleted_at"),
    )


def create_user(
    email: str,
    full_name: str,
    hashed_password: str,
    role: str = "sourcer",
) -> User:
    """Insert a new user. Raises psycopg2.errors.UniqueViolation if email exists."""
    sql = """
        INSERT INTO auth.users (email, full_name, hashed_password, role)
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email, full_name, hashed_password, role))
            row = cur.fetchone()
            conn.commit()
            return _row_to_user(dict(row))


def get_user_by_email(email: str) -> Optional[User]:
    """Return the active user with this email, or None."""
    sql = """
        SELECT * FROM auth.users
        WHERE email = %s AND deleted_at IS NULL
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            return _row_to_user(dict(row)) if row else None


def get_user_by_email_any(email: str) -> Optional[User]:
    """Return the user with this email regardless of is_active / deleted_at.

    Used by the login flow to distinguish 'not found' vs 'deactivated' vs
    'deleted' for precise French error messages.
    """
    sql = "SELECT * FROM auth.users WHERE email = %s LIMIT 1"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            return _row_to_user(dict(row)) if row else None


def get_user_by_id(user_id: str) -> Optional[User]:
    """Return the active user with this UUID, or None."""
    sql = """
        SELECT * FROM auth.users
        WHERE id = %s AND deleted_at IS NULL
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id),))
            row = cur.fetchone()
            return _row_to_user(dict(row)) if row else None


def update_last_login(user_id: str) -> None:
    """Stamp last_login_at = NOW() for the given user."""
    sql = """
        UPDATE auth.users
        SET last_login_at = NOW(), updated_at = NOW()
        WHERE id = %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id),))
            conn.commit()


def user_exists(email: str) -> bool:
    """Return True if a (non-deleted) user with this email already exists."""
    sql = "SELECT 1 FROM auth.users WHERE email = %s AND deleted_at IS NULL LIMIT 1"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            return cur.fetchone() is not None


def update_full_name(user_id: str, full_name: str) -> None:
    """Update a user's display name."""
    sql = "UPDATE auth.users SET full_name = %s, updated_at = NOW() WHERE id = %s"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (full_name.strip(), str(user_id)))
            conn.commit()


def update_password(user_id: str, hashed_password: str) -> None:
    """Replace a user's hashed password."""
    sql = "UPDATE auth.users SET hashed_password = %s, updated_at = NOW() WHERE id = %s"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (hashed_password, str(user_id)))
            conn.commit()


def get_sourcers() -> List[User]:
    """Return all active sourcer users (for recruiter assign dropdown)."""
    sql = """
        SELECT * FROM auth.users
        WHERE role = 'sourcer' AND is_active = true AND deleted_at IS NULL
        ORDER BY full_name ASC
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [_row_to_user(dict(r)) for r in cur.fetchall()]


# ── Admin space helpers (Workstream 3) ─────────────────────────────────────────

def list_users(role: Optional[str] = None, active: Optional[bool] = None) -> List[User]:
    """Return all non-deleted users, optionally filtered by role and/or active flag."""
    clauses = ["deleted_at IS NULL"]
    params: list = []
    if role:
        clauses.append("role = %s")
        params.append(role)
    if active is not None:
        clauses.append("is_active = %s")
        params.append(active)
    sql = (
        "SELECT * FROM auth.users WHERE "
        + " AND ".join(clauses)
        + " ORDER BY created_at DESC"
    )
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [_row_to_user(dict(r)) for r in cur.fetchall()]


def update_user(
    user_id: str,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    email: Optional[str] = None,
) -> Optional[User]:
    """Update the provided fields of a (non-deleted) user. Returns the updated row."""
    sets = []
    params: list = []
    if email is not None:
        sets.append("email = %s")
        params.append(email.strip().lower())
    if full_name is not None:
        sets.append("full_name = %s")
        params.append(full_name.strip())
    if role is not None:
        sets.append("role = %s")
        params.append(role)
    if is_active is not None:
        sets.append("is_active = %s")
        params.append(is_active)
    if not sets:
        return get_user_by_id(user_id)
    sets.append("updated_at = NOW()")
    sql = (
        "UPDATE auth.users SET "
        + ", ".join(sets)
        + " WHERE id = %s AND deleted_at IS NULL RETURNING *"
    )
    params.append(str(user_id))
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            conn.commit()
            return _row_to_user(dict(row))


def soft_delete_user(user_id: str) -> bool:
    """Soft-delete a user (sets deleted_at = NOW()). Returns True if a row was affected."""
    sql = """
        UPDATE auth.users
        SET deleted_at = NOW(), is_active = false, updated_at = NOW()
        WHERE id = %s AND deleted_at IS NULL
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id),))
            affected = cur.rowcount
            conn.commit()
            return affected > 0


def get_user_stats() -> dict:
    """Return {total, by_role: {...}, active} for all non-deleted users."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role,
                       COUNT(*) AS cnt,
                       COUNT(*) FILTER (WHERE is_active) AS active_cnt
                FROM auth.users
                WHERE deleted_at IS NULL
                GROUP BY role
                """
            )
            by_role: dict = {}
            total = 0
            active = 0
            for row in cur.fetchall():
                by_role[row["role"]] = row["cnt"]
                total += row["cnt"]
                active += row["active_cnt"]
    return {"total": total, "by_role": by_role, "active": active}


def get_recent_user_creations(limit: int = 20) -> list:
    """Return recent user creations for the admin activity feed."""
    sql = """
        SELECT full_name, email, role, created_at
        FROM auth.users
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return [dict(r) for r in cur.fetchall()]
