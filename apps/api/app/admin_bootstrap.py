"""One-time account creation from protected stdin. Existing passwords never change."""
import json
import sys

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from .admin_auth import password_hash, username
from .config import Settings
from .models import Admin


def bootstrap(engine, accounts):
    if not isinstance(accounts, list) or len(accounts) != 3:
        raise ValueError("Provide exactly three initial accounts")
    names = [username(account["username"]) for account in accounts]
    if len(set(names)) != 3 or any(not isinstance(a["password"], str) or not 12 <= len(a["password"]) <= 1024 for a in accounts):
        raise ValueError("Invalid unique usernames or passwords")
    with Session(engine) as db, db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(721930115)"))
        for name, account in zip(names, accounts):
            if db.scalar(select(Admin.id).where(Admin.username == name)) is None:
                db.add(Admin(username=name, password_hash=password_hash(account["password"])))


if __name__ == "__main__":
    engine = create_engine(Settings.from_env().database_url)
    try:
        bootstrap(engine, json.loads(sys.stdin.read(16384)))
        print("Initial accounts ready; existing accounts retained.")
    except Exception:
        print("Initial account creation failed.", file=sys.stderr)
        raise SystemExit(1)
    finally:
        engine.dispose()
