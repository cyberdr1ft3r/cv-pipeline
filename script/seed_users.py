"""
script/seed_users.py

Creates default demo users in auth.users if they don't already exist.
Idempotent — safe to run multiple times.

Usage:
    python script/seed_users.py

Requires:
    DATABASE_URL env var pointing to the cv_pipeline PostgreSQL database.
    Run service/migrations/001_auth_offers_schema.sql first.

    Set SECRET_KEY in config/.env to any non-placeholder value before running
    the full API. The seed script itself doesn't need JWT, but it loads service.config
    which reads the .env file so DATABASE_URL is available.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap env loading (reads config/.env → sets DATABASE_URL etc.)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service.config  # noqa: F401 — side-effect: loads .env

from service.security import hash_password
from service.user_store import create_user, user_exists

_SEED_USERS = [
    {
        "email": "recruiter@itroad.ma",
        "full_name": "Responsable Recrutement",
        "password": "Recruiter2026!",
        "role": "recruiter",
    },
    {
        "email": "sourcer@itroad.ma",
        "full_name": "Chargé de Sourcing",
        "password": "Sourcer2026!",
        "role": "sourcer",
    },
    {
        "email": "admin@itroad.com",
        "full_name": "Administrateur",
        "password": "Admin2026!",
        "role": "admin",
    },
]


def seed() -> None:
    print("Seeding users into auth.users …\n")
    created = 0
    skipped = 0
    for u in _SEED_USERS:
        if user_exists(u["email"]):
            print(f"⏭️  Already exists: {u['email']} ({u['role']})")
            skipped += 1
        else:
            try:
                create_user(
                    email=u["email"],
                    full_name=u["full_name"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                )
                print(f"✅ Created: {u['email']} ({u['role']})")
                created += 1
            except Exception as exc:
                print(f"❌ Failed to create {u['email']}: {exc}", file=sys.stderr)

    print(f"\nDone — {created} created, {skipped} already existed.")


if __name__ == "__main__":
    seed()
