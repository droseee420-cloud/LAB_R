import hmac
import logging
import re
from datetime import date, datetime
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.responses import StreamingResponse

from . import admin_auth as auth
from . import admin_service as service
from .security import RateLimiter, client_ip


logger = logging.getLogger(__name__)


def login_label(value):
    cleaned = re.sub(r"[^a-z0-9_.-]", "?", value.strip().lower())
    return (cleaned[:24] or "-")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class Note(StrictModel):
    notes: str | None = Field(max_length=10000)
    notes_version: int = Field(ge=0)


class Filters(StrictModel):
    q: str = Field(default="", max_length=200)
    page: int = Field(default=1, ge=1, le=100000)
    page_size: Literal[25, 50, 100] = 25
    contact_method: Literal["email", "telegram"] | None = None
    language: Literal["en", "es", "ca"] | None = None
    has_files: bool | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Start date must precede end date")
        if self.date_to and self.date_to.year >= 9999:
            raise ValueError("End date out of range")
        return self


class FileView(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class Summary(BaseModel):
    id: UUID
    created_at: datetime
    name: str | None
    contact_method: str
    contact: str
    language: str
    message_preview: str
    file_count: int | None


class Listing(BaseModel):
    items: list[Summary]
    total: int
    page: int
    page_size: int


class Detail(Summary):
    message: str
    product_link: str | None
    no_product: bool
    contact_normalized: str
    consent: bool
    consent_at: datetime
    consent_version: str
    notes: str | None
    notes_version: int
    files: list[FileView]
    related: list[Summary]


def router(engine, storage, settings):
    router = APIRouter(prefix="/api/admin")
    limiter = RateLimiter(settings.admin_login_limit, 600, settings.cookie_secret)

    def origin(request):
        if request.headers.get("origin") != (settings.admin_origin or settings.public_url):
            raise service.AdminError("origin", "This origin is not allowed.", 403)

    def authenticated(request: Request):
        if request.headers.get("origin"):
            origin(request)
        token = request.cookies.get(auth.COOKIE)
        identity = auth.identity(engine, token)
        if not identity:
            raise service.AdminError("unauthorized", "Sign in to continue.", 401)
        if request.method not in {"GET", "HEAD"}:
            origin(request)
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), auth.csrf(token, settings.cookie_secret)):
                raise service.AdminError("csrf", "Reload the page and try again.", 403)
        return identity

    @router.post("/login")
    def login(data: Login, request: Request, response: Response):
        origin(request)
        address = client_ip(request.client.host if request.client else "unknown", request.headers.get("x-real-ip"), settings.trusted_proxy_cidrs)
        retry = limiter.check(address)
        if retry:
            logger.info("admin_login outcome=rate_limited username=%s", login_label(data.username))
            response.status_code = 429
            response.headers["Retry-After"] = str(retry)
            return {"ok": False, "code": "rate_limited", "error": "Too many sign-in attempts. Try again later."}
        token = auth.login(engine, settings, data.username, data.password)
        if not token:
            logger.info("admin_login outcome=denied username=%s", login_label(data.username))
            raise service.AdminError("invalid_credentials", "Incorrect username or password.", 401)
        logger.info("admin_login outcome=success username=%s", login_label(data.username))
        response.set_cookie(auth.COOKIE, token, path="/api/admin", httponly=True, secure=not settings.http_test_mode,
                            samesite="strict", max_age=settings.admin_session_hours * 3600)
        return {"ok": True}

    @router.get("/session")
    def session(request: Request, user=Depends(authenticated)):
        return {"user": user, "csrf_token": auth.csrf(request.cookies[auth.COOKIE], settings.cookie_secret)}

    @router.post("/logout", status_code=204)
    def logout(request: Request, response: Response, user=Depends(authenticated)):
        auth.logout(engine, request.cookies[auth.COOKIE])
        response.delete_cookie(auth.COOKIE, path="/api/admin", httponly=True, secure=not settings.http_test_mode, samesite="strict")

    @router.get("/leads", response_model=Listing)
    def listing(q: str = Query("", max_length=200), page: int = Query(1, ge=1, le=100000),
                page_size: int = Query(25, ge=1, le=100),
                contact_method: Literal["email", "telegram"] | None = None,
                language: Literal["en", "es", "ca"] | None = None, has_files: bool | None = None,
                date_from: date | None = None, date_to: date | None = None,
                sort: Literal["asc", "desc"] = "desc", user=Depends(authenticated)):
        if page_size not in {25, 50, 100}:
            raise service.AdminError("validation", "Invalid request fields or filters.", 422)
        if (date_from and date_to and date_from > date_to) or (date_to and date_to.year >= 9999):
            raise service.AdminError("validation", "Invalid request fields or filters.", 422)
        filters = Filters(q=q, page=page, page_size=page_size, contact_method=contact_method, language=language,
                          has_files=has_files, date_from=date_from, date_to=date_to, sort=sort)
        return service.list_leads(engine, filters)

    @router.get("/leads/{lead_id}", response_model=Detail)
    def detail(lead_id: UUID, user=Depends(authenticated)):
        return service.detail(engine, lead_id)

    @router.patch("/leads/{lead_id}/notes", response_model=Note)
    def notes(lead_id: UUID, data: Note, user=Depends(authenticated)):
        return service.notes(engine, lead_id, data.notes, data.notes_version)

    @router.get("/files/{file_id}/download")
    def download(file_id: UUID, user=Depends(authenticated)):
        info, chunks = service.download(engine, storage, file_id)
        return StreamingResponse(chunks, media_type=info["content_type"], headers={
            "Content-Length": str(info["size_bytes"]), "Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename=download; filename*=UTF-8''" + quote(info["filename"], safe="")})

    @router.delete("/files/{file_id}", status_code=204)
    def delete_file(file_id: UUID, user=Depends(authenticated)):
        service.remove(engine, storage, file_id)

    @router.delete("/leads/{lead_id}", status_code=204)
    def delete_lead(lead_id: UUID, user=Depends(authenticated)):
        service.remove(engine, storage, lead_id, entire_lead=True)

    return router
