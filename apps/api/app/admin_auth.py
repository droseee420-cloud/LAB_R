import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from threading import BoundedSemaphore

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import Admin, AdminSession

COOKIE = "lab_admin"
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
password_slots = BoundedSemaphore(2)


def now():
    return datetime.now(timezone.utc)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def username(value):
    if not isinstance(value, str):
        raise ValueError("Username is required")
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,79}", value):
        raise ValueError("Username must contain 3–80 ASCII letters, numbers, dot, underscore or hyphen")
    return value


def password_hash(password):
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12–1024 characters")
    with password_slots:
        return hasher.hash(password)


def login(engine, settings, name, password):
    with Session(engine) as db, db.begin():
        # Lock the identity against concurrent password reset/disable.
        admin = db.scalar(select(Admin).where(Admin.username == name.strip().lower()).with_for_update())
        with password_slots:
            try:
                valid = hasher.verify(admin.password_hash if admin else dummy_hash, password)
            except (VerificationError, InvalidHashError):
                valid = False
        if not valid or not admin or not admin.active:
            return None
        if hasher.check_needs_rehash(admin.password_hash):
            # Verification has released the bounded Argon2 slot before rehashing.
            admin.password_hash = password_hash(password)
        token = secrets.token_urlsafe(48)
        db.add(AdminSession(token_hash=digest(token), admin_id=admin.id,
                            expires_at=now() + timedelta(hours=settings.admin_session_hours)))
        return token


def identity(engine, token):
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{64}", token):
        return None
    with Session(engine) as db:
        admin = db.scalar(select(Admin).join(AdminSession).where(AdminSession.token_hash == digest(token),
                           AdminSession.expires_at > now(), AdminSession.revoked_at.is_(None), Admin.active.is_(True)))
        return {"id": str(admin.id), "username": admin.username} if admin else None


def csrf(token, secret):
    return hmac.new(secret.encode(), ("admin-csrf:" + token).encode(), hashlib.sha256).hexdigest()


def logout(engine, token):
    with Session(engine) as db, db.begin():
        db.execute(update(AdminSession).where(AdminSession.token_hash == digest(token)).values(revoked_at=now()))


def manage(engine, action, name=None, password=None):
    with Session(engine) as db, db.begin():
        if action == "list":
            return [{"username": a.username, "active": a.active} for a in db.scalars(select(Admin).order_by(Admin.username))]
        if action == "cleanup-sessions":
            return db.execute(delete(AdminSession).where((AdminSession.expires_at <= now()) | AdminSession.revoked_at.is_not(None))).rowcount
        name = username(name)
        admin = db.scalar(select(Admin).where(Admin.username == name).with_for_update())
        if action == "create":
            if admin:
                raise ValueError("Account already exists; use explicit reset-password")
            db.add(Admin(username=name, password_hash=password_hash(password)))
            return
        if not admin:
            raise ValueError("Account does not exist")
        if action == "reset-password":
            admin.password_hash = password_hash(password)
            admin.password_changed_at = now()
        elif action in {"enable", "disable"}:
            admin.active = action == "enable"
        else:
            raise ValueError("Unknown account operation")
        if action != "enable":
            db.execute(update(AdminSession).where(AdminSession.admin_id == admin.id).values(revoked_at=now()))
