import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    name: Mapped[str | None] = mapped_column(String(120))
    contact_method: Mapped[str] = mapped_column(String(8))
    contact: Mapped[str] = mapped_column(String(180))
    contact_normalized: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    product_link: Mapped[str | None] = mapped_column(String(1000))
    no_product: Mapped[bool] = mapped_column(Boolean)
    language: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(16), server_default="new")
    browser_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    idempotency_hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    consent: Mapped[bool] = mapped_column(Boolean)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    consent_version: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    notes_version: Mapped[int] = mapped_column(Integer, server_default="0")
    __table_args__ = (
        CheckConstraint("contact_method IN ('email', 'telegram')", name="contact_method_valid"),
        CheckConstraint("language IN ('en', 'es', 'ca')", name="language_valid"),
        CheckConstraint("status = 'new'", name="status_valid"),
        CheckConstraint("consent", name="consent_required"),
        CheckConstraint("char_length(message) BETWEEN 12 AND 5000", name="message_length"),
        Index("ix_leads_created", "created_at"),
        Index("ix_leads_status_created", "status", "created_at"),
        Index("ix_leads_contact", "contact_method", "contact_normalized"),
    )


class LeadFile(Base):
    __tablename__ = "lead_files"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"), index=True)
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="file_size_valid"),)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admins.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
