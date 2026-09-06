from datetime import datetime, time, timedelta, timezone

from sqlalchemy import String, cast, delete, exists, func, or_, select, text, update
from sqlalchemy.orm import Session

from .models import Lead, LeadFile
from .service import STORAGE_LOCK


class AdminError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def lock(db, shared=False):
    db.execute(text("SELECT pg_advisory_xact_lock" + ("_shared" if shared else "") + "(:key)"), {"key": STORAGE_LOCK})


def recover_locked(db, storage):
    for key in storage.trash_keys():
        live = db.scalar(select(LeadFile.id).where(LeadFile.storage_key == key)) is not None
        storage.recover_object(key, live)


def recover(engine, storage):
    with Session(engine) as db, db.begin():
        lock(db)
        recover_locked(db, storage)


def summary(lead, count):
    return {"id": str(lead.id), "created_at": lead.created_at, "name": lead.name,
            "contact_method": lead.contact_method, "contact": lead.contact, "language": lead.language,
            "message_preview": lead.message[:180], "file_count": count}


def file_view(file):
    return {key: getattr(file, key) for key in ("id", "filename", "content_type", "size_bytes", "sha256", "created_at")}


def list_leads(engine, query):
    filters = []
    if query.q:
        pattern = "%" + query.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        filters.append(or_(*(column.ilike(pattern, escape="\\") for column in
                            (cast(Lead.id, String), Lead.name, Lead.contact, Lead.contact_normalized, Lead.message))))
    for name in ("contact_method", "language"):
        if getattr(query, name):
            filters.append(getattr(Lead, name) == getattr(query, name))
    files = exists().where(LeadFile.lead_id == Lead.id)
    if query.has_files is not None:
        filters.append(files if query.has_files else ~files)
    if query.date_from:
        filters.append(Lead.created_at >= datetime.combine(query.date_from, time.min, timezone.utc))
    if query.date_to:
        filters.append(Lead.created_at < datetime.combine(query.date_to + timedelta(days=1), time.min, timezone.utc))
    count = select(func.count(LeadFile.id)).where(LeadFile.lead_id == Lead.id).correlate(Lead).scalar_subquery()
    ordering = [getattr(column, query.sort)() for column in (Lead.created_at, Lead.id)]
    with Session(engine) as db:
        total = db.scalar(select(func.count()).select_from(Lead).where(*filters))
        rows = db.execute(select(Lead, count).where(*filters).order_by(*ordering).offset((query.page - 1) * query.page_size).limit(query.page_size))
        return {"items": [summary(lead, count) for lead, count in rows], "total": total, "page": query.page, "page_size": query.page_size}


def detail(engine, lead_id):
    with Session(engine) as db:
        lead = db.get(Lead, lead_id)
        if not lead:
            raise AdminError("not_found", "Request not found.", 404)
        files = list(db.scalars(select(LeadFile).where(LeadFile.lead_id == lead_id).order_by(LeadFile.created_at, LeadFile.id)))
        related = db.scalars(select(Lead).where(Lead.id != lead_id, Lead.contact_method == lead.contact_method,
                              Lead.contact_normalized == lead.contact_normalized).order_by(Lead.created_at.desc(), Lead.id.desc()).limit(100))
        return summary(lead, len(files)) | {key: getattr(lead, key) for key in
                 ("message", "product_link", "no_product", "contact_normalized", "consent", "consent_at", "consent_version", "notes", "notes_version")} | {
                 "files": [file_view(file) for file in files], "related": [summary(other, None) for other in related]}


def notes(engine, lead_id, value, version):
    with Session(engine) as db, db.begin():
        row = db.execute(update(Lead).where(Lead.id == lead_id, Lead.notes_version == version).values(
            notes=value or None, notes_version=Lead.notes_version + 1).returning(Lead.notes, Lead.notes_version)).first()
        if not row:
            if not db.get(Lead, lead_id):
                raise AdminError("not_found", "Request not found.", 404)
            raise AdminError("notes_conflict", "Another administrator changed this note. Reload before saving.", 409)
        return {"notes": row.notes, "notes_version": row.notes_version}


def remove(engine, storage, identifier, entire_lead=False):
    # Trash keys are deterministic. Committed metadata is the recovery journal.
    # Recovery is always under the same exclusive lock as uploads/cleanup/downloads.
    try:
        with Session(engine) as db, db.begin():
            lock(db)
            recover_locked(db, storage)
            condition = LeadFile.lead_id == identifier if entire_lead else LeadFile.id == identifier
            files = list(db.scalars(select(LeadFile).where(condition)))
            for file in files:
                storage.quarantine(file.storage_key)
            db.execute(delete(LeadFile).where(condition))
            if entire_lead:
                db.execute(delete(Lead).where(Lead.id == identifier))
    except Exception:
        # May have committed: a fresh DB view decides restore versus purge.
        # If DB/storage is unavailable, leave recoverable trash and return an error.
        try:
            recover(engine, storage)
        except Exception:
            pass
        raise
    recover(engine, storage)  # No success response until bytes have actually been purged.


def download(engine, storage, file_id):
    recover(engine, storage)
    db = Session(engine)
    stream = None
    try:
        lock(db, shared=True)
        file = db.get(LeadFile, file_id)
        if not file:
            raise AdminError("not_found", "File not found.", 404)
        stream = storage.read(file.storage_key)
        info = file_view(file)
    except Exception:
        if stream:
            stream.close()
        db.close()
        raise

    def chunks():
        try:
            while chunk := stream.read(64 * 1024):
                yield chunk
        finally:
            stream.close()
            db.close()  # Shared storage lock spans the complete stream.
    return info, chunks()
