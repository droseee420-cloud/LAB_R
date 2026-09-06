import hashlib
import json
import logging
import time
from dataclasses import asdict
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import Lead, LeadFile
from .security import digest
from .validation import BriefError

logger = logging.getLogger("lab")
STORAGE_LOCK = 721930114


def lock_key(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big", signed=True)


def accept_brief(engine, storage, data: dict, uploads: list, browser_hash: str | None, key: str):
    batch = str(uuid4())
    try:
        with Session(engine) as session, session.begin():
            # Cleanup takes the exclusive form of this lock. It cannot race active writes.
            session.execute(text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": STORAGE_LOCK})
            staged = storage.stage(batch, uploads)
            file_data = [{k: v for k, v in asdict(f).items() if k != "id"} for f in staged]
            payload_hash = digest(json.dumps({"fields": data, "files": file_data, "browser": browser_hash}, sort_keys=True, ensure_ascii=False))
            key_hash = digest(key)
            locks = [lock_key("idempotency:" + key_hash)]
            if browser_hash:
                locks.append(lock_key("browser:" + browser_hash))
            for lock in sorted(set(locks)):
                session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
            existing = session.scalar(select(Lead).where(Lead.idempotency_hash == key_hash))
            if existing:
                if existing.payload_hash != payload_hash:
                    raise BriefError("This request key was already used with different content. Please start a new submission.", "idempotency_conflict", 409)
                return str(existing.id), False
            if browser_hash and session.scalar(select(Lead.id).where(Lead.browser_hash == browser_hash)):
                raise BriefError("Your message is already with the lab. This browser has submitted a request.", "already_submitted", 409)
            lead = Lead(**data, browser_hash=browser_hash, idempotency_hash=key_hash, payload_hash=payload_hash)
            session.add(lead)
            session.flush()
            lead_id = str(lead.id)
            for file in staged:
                session.add(LeadFile(id=UUID(file.id), lead_id=lead.id,
                                     storage_key=f"objects/{lead_id}/{file.id}", filename=file.filename,
                                     content_type=file.content_type, size_bytes=file.size_bytes, sha256=file.sha256))
            session.flush()
            storage.promote(batch, lead_id)
            # Commit is last. On an ambiguous commit error, KEEP promoted files:
            # PostgreSQL might have committed. Cleanup checks committed references.
        return lead_id, True
    finally:
        try:
            storage.discard(batch)
        except OSError:
            logger.error("staging_cleanup_failed batch=%s", batch)


def submitted(engine, browser_hash: str | None) -> bool:
    if not browser_hash:
        return False
    with Session(engine) as session:
        return session.scalar(select(Lead.id).where(Lead.browser_hash == browser_hash)) is not None


def cleanup_orphans(engine, storage, grace_seconds: int = 3600) -> int:
    from .admin_service import recover_locked
    removed = 0
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": STORAGE_LOCK})
        recover_locked(session, storage)
        for kind in ("staging", "objects"):
            for path in (storage.root / kind).iterdir():
                if path.is_symlink() or not path.is_dir() or time.time() - path.stat().st_mtime < grace_seconds:
                    continue
                try:
                    lead_id = UUID(path.name)
                except ValueError:
                    continue
                if kind == "objects" and session.get(Lead, lead_id) is not None:
                    continue
                storage.remove_orphan(kind, path.name)
                removed += 1
    return removed
