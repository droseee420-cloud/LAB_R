import logging
import re
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

from .config import Settings
from .admin_routes import router as admin_router
from .admin_service import AdminError
from .security import COOKIE_NAME, RateLimiter, client_ip, cookie_hash, new_cookie
from .service import accept_brief, submitted
from .storage import LocalStorage
from .telegram import notify
from .validation import MAX_BODY_SIZE, BriefError, field, validate_form

logger = logging.getLogger("lab")
# These libraries may include user file data or the bot token URL in diagnostics.
for name in ("httpx", "httpcore", "pypdf", "olefile", "python_multipart"):
    logging.getLogger(name).disabled = True


def failure(message, code, status, **kwargs):
    return JSONResponse({"ok": False, "error": message, "code": code}, status_code=status, **kwargs)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0
        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > (65536 if scope.get("path", "").startswith("/api/admin") else MAX_BODY_SIZE):
                # Starlette closes every spooled upload on MultiPartException.
                scope["lab_body_too_large"] = True
                raise MultiPartException("Request too large")
            return message
        await self.app(scope, limited_receive, send)


def create_app(settings: Settings | None = None, engine=None, storage=None) -> FastAPI:
    settings = settings or Settings.from_env()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True,
                                    connect_args={"connect_timeout": 5}, pool_size=4, max_overflow=2)
    storage = storage or LocalStorage(settings.storage_root)
    limiter = RateLimiter(settings.rate_limit, settings.rate_window, settings.cookie_secret)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if own_engine:
            engine.dispose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(BodyLimit)
    app.state.engine, app.state.storage, app.state.limiter = engine, storage, limiter
    app.include_router(admin_router(engine, storage, settings))

    @app.exception_handler(AdminError)
    async def admin_error(request, error):
        return failure(error.message, error.code, error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return failure("Invalid request fields or filters.", "validation", 422)

    def browser(request):
        return cookie_hash(request.cookies.get(COOKIE_NAME), settings.cookie_secret, settings.cookie_days * 86400)

    def set_cookie(response):
        response.set_cookie(COOKIE_NAME, new_cookie(settings.cookie_secret), httponly=True,
                            secure=not settings.http_test_mode, samesite="lax", path="/api/brief",
                            max_age=settings.cookie_days * 86400)

    @app.middleware("http")
    async def guard(request, call_next):
        request_id = str(uuid4())
        try:
            if request.url.path.startswith("/api/brief"):
                origin = request.headers.get("origin")
                if origin and origin != settings.public_url:
                    return failure("This origin is not allowed.", "origin", 403)
                if request.method == "POST":
                    address = client_ip(request.client.host if request.client else "unknown",
                                        request.headers.get("x-real-ip"), settings.trusted_proxy_cidrs)
                    retry = limiter.check(address)
                    if retry:
                        return failure("Too many attempts. Please try again later.", "rate_limited", 429,
                                       headers={"Retry-After": str(retry)})
                    try:
                        size = int(request.headers.get("content-length", "0"))
                    except ValueError:
                        return failure("Invalid request size.", "validation", 400)
                    if size > MAX_BODY_SIZE:
                        return failure("Request exceeds 31 MiB.", "file_size", 413)
            response = await call_next(request)
        except Exception:
            logger.error("request_failed request=%s", request_id)
            response = failure("The request could not be saved. Please retry.", "unavailable", 503)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/admin"):
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/api/health")
    async def health():
        def check():
            with engine.connect() as conn:
                conn.execute(text("SELECT id FROM leads LIMIT 0"))
            test = storage.root / (".health-" + str(uuid4()))
            try:
                test.write_bytes(b"ok")
            finally:
                test.unlink(missing_ok=True)
        try:
            await run_in_threadpool(check)
            return {"ok": True}
        except (OSError, SQLAlchemyError):
            return failure("Service unavailable.", "unavailable", 503)

    @app.get("/api/brief/session")
    async def session_status(request: Request):
        marker = browser(request)
        response = JSONResponse({"ok": True, "submitted": await run_in_threadpool(submitted, engine, marker)})
        if marker is None:
            set_cookie(response)
        return response

    @app.post("/api/brief")
    async def brief(request: Request):
        try:
            if not request.headers.get("content-type", "").lower().startswith("multipart/form-data;"):
                raise BriefError("Use a multipart form.")
            async with request.form(max_files=6, max_fields=12, max_part_size=16 * 1024) as form:
                if field(form, "companyWebsite", 200):
                    return {"ok": True}
                key = request.headers.get("idempotency-key", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
                    raise BriefError("A valid Idempotency-Key is required.")
                data = validate_form(form)
                uploads = form.getlist("files")
                if any(not isinstance(f, UploadFile) for f in uploads):
                    raise BriefError("Invalid attachment.")
                lead_id, created = await run_in_threadpool(accept_brief, engine, storage, data, uploads, browser(request), key)
                if created:
                    await run_in_threadpool(notify, settings, lead_id, data, len(uploads))
                response = JSONResponse({"ok": True, "id": lead_id})
                if request.cookies.get(COOKIE_NAME) and browser(request) is None:
                    set_cookie(response)
                return response
        except BriefError as exc:
            return failure(str(exc), exc.code, exc.status)
        except (HTTPException, MultiPartException):
            oversized = request.scope.get("lab_body_too_large", False)
            return failure("Request exceeds 31 MiB." if oversized else "Invalid multipart form or too many attachments.",
                           "file_size" if oversized else "validation", 413 if oversized else 400)
        except (OSError, SQLAlchemyError):
            technical_id = str(uuid4())
            logger.error("save_failed request=%s", technical_id)
            return failure("The request could not be saved. Please retry.", "unavailable", 503)

    return app
