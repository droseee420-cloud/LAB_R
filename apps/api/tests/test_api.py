import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
from pathlib import Path

import httpx
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Lead, LeadFile
from app.security import COOKIE_NAME, new_cookie
from app.service import cleanup_orphans
from app.telegram import notify
from conftest import fields, office, pdf, picture, send

pytestmark = pytest.mark.integration


def count(engine):
    with Session(engine) as db:
        return db.scalar(select(func.count()).select_from(Lead))


@pytest.mark.parametrize("method,contact,normalized", [
    ("email", "Test.Name+lab@Example.org", "test.name+lab@example.org"),
    ("telegram", "@Example_User", "example_user"),
])
def test_complete_brief(client, engine, application, method, contact, normalized):
    assert client.get("/api/brief/session").json() == {"ok": True, "submitted": False}
    assert count(engine) == 0
    token = client.cookies.get(COOKIE_NAME)
    result = send(client, fields(contactMethod=method, contact=contact), [("brief.PNG", picture(), "text/plain")])
    assert result.status_code == 200, result.text
    with Session(engine) as db:
        lead = db.get(Lead, UUID(result.json()["id"]))
        assert lead.message == fields()["message"] and lead.product_link == fields()["productLink"]
        assert lead.no_product and lead.name == "Synthetic client" and lead.language == "en"
        assert lead.contact == contact and lead.contact_normalized == normalized
        assert lead.consent and lead.consent_version == "brief-en-v1" and lead.consent_at.tzinfo
        assert lead.created_at.tzinfo and lead.status == "new"
        assert lead.browser_hash == hashlib.sha256(token.encode()).hexdigest()
        file = db.scalar(select(LeadFile))
        with application.state.storage.read(file.storage_key) as stream:
            assert stream.read() == picture()
        assert file.content_type == "image/png" and file.size_bytes == len(picture())
    assert client.get("/api/brief/session").json() == {"ok": True, "submitted": True}
    assert send(client).json()["code"] == "already_submitted"
    assert len(application.state.notifications) == 1


@pytest.mark.parametrize("change", [
    {"message": ""}, {"message": "x" * 5001}, {"consent": "false"}, {"consentVersion": "invented"},
    {"contact": "invalid"}, {"contactMethod": "phone"}, {"name": "x" * 121}, {"language": "ru"},
    {"contactMethod": "telegram", "contact": "@ab"}, {"contact": "x..y@example.org"},
    {"productLink": "javascript:alert(1)"}, {"productLink": "http://user:pass@example.org"},
    {"noProduct": "maybe"}, {"contact": "x" * 181}, {"productLink": "https://"},
])
def test_direct_validation(client, engine, change):
    assert send(client, fields(**change)).status_code == 400
    assert count(engine) == 0


def test_honeypot(client, engine, application):
    assert send(client, fields(companyWebsite="bot")).json() == {"ok": True}
    assert count(engine) == 0 and not application.state.notifications
    assert not list((application.state.storage.root / "objects").iterdir())


def test_no_cookie_and_deleted_cookie(client, engine):
    assert send(client).status_code == 200
    assert send(client).status_code == 200
    client.get("/api/brief/session")
    assert send(client).status_code == 200
    client.cookies.clear()
    client.get("/api/brief/session")
    assert send(client).status_code == 200
    assert count(engine) == 4


def test_idempotency_and_payload_conflict(client, engine, application):
    client.get("/api/brief/session")
    key = uuid4().hex
    files = [("a.png", picture(), "image/png")]
    first = send(client, uploads=files, key=key)
    repeat = send(client, uploads=files, key=key)
    assert repeat.status_code == 200 and first.json() == repeat.json()
    assert send(client, fields(message="A different request entirely."), uploads=files, key=key).json()["code"] == "idempotency_conflict"
    assert len(list((application.state.storage.root / "objects").glob("*/*"))) == 1
    assert not list((application.state.storage.root / "staging").iterdir())
    assert count(engine) == 1 and len(application.state.notifications) == 1


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_requests(application, engine, same_key):
    token, key = new_cookie("test-secret-" * 4), uuid4().hex
    def post(_):
        with TestClient(application) as client:
            client.cookies.set(COOKIE_NAME, token)
            return send(client, key=key if same_key else uuid4().hex, uploads=[("a.png", picture(), "image/png")])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(post, range(4)))
    assert sorted(r.status_code for r in results) == ([200] * 4 if same_key else [200, 409, 409, 409])
    assert count(engine) == 1 and len(application.state.notifications) == 1
    assert len(list((application.state.storage.root / "objects").glob("*/*"))) == 1


def test_cookie_tampering_privacy(client, application):
    client.get("/api/brief/session")
    assert send(client).status_code == 200
    token = client.cookies.get(COOKIE_NAME)
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, token[:-1] + ("1" if token[-1] != "1" else "0"))
    response = client.get("/api/brief/session")
    assert response.json() == {"ok": True, "submitted": False}
    assert "HttpOnly" in response.headers["set-cookie"] and "Secure" not in response.headers["set-cookie"]
    for path in ["/api/brief/123", "/api/leads", "/api/admin", "/uploads/a", "/objects/a", "/api/files/a", "/docs"]:
        assert client.get(path).status_code == 404
    with pytest.raises(ValueError):
        application.state.storage.read("../../secret")


def test_rate_limit_ignores_untrusted_headers(engine, tmp_path):
    settings = Settings(engine.url, "test-secret-" * 4, tmp_path, "http://testserver", True, rate_limit=2)
    with TestClient(create_app(settings, engine)) as client:
        assert send(client).status_code == 200
        assert send(client, headers={"X-Real-IP": "1.2.3.4"}).status_code == 200
        response = send(client, headers={"X-Real-IP": "5.6.7.8", "X-Forwarded-For": "9.9.9.9"})
        assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


@pytest.mark.parametrize("failure_point", ["stage", "promote", "commit"])
def test_failure_is_retryable(client, engine, application, monkeypatch, failure_point):
    client.get("/api/brief/session")
    key = uuid4().hex
    storage = application.state.storage
    def fail(*args, **kwargs):
        raise OSError("synthetic disk full")
    def commit_fail(*args):
        raise OperationalError("synthetic", {}, Exception("connection lost"))
    with monkeypatch.context() as m:
        if failure_point == "commit":
            event.listen(engine, "commit", commit_fail)
        else:
            m.setattr(storage, failure_point, fail)
        try:
            response = send(client, key=key, uploads=[("a.png", picture(), "image/png")])
        finally:
            if failure_point == "commit":
                event.remove(engine, "commit", commit_fail)
    assert response.status_code == 503 and count(engine) == 0
    assert client.get("/api/brief/session").json()["submitted"] is False
    assert send(client, key=key, uploads=[("a.png", picture(), "image/png")]).status_code == 200
    cleanup_orphans(engine, storage, grace_seconds=0)
    assert len(list((storage.root / "objects").glob("*/*"))) == 1
    assert not list((storage.root / "staging").iterdir())


def test_mid_write_failure(client, engine, application, monkeypatch):
    import app.storage as module
    original = module.validate_file
    calls = 0
    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return original(*args)
    monkeypatch.setattr(module, "validate_file", fail_second)
    response = send(client, uploads=[("a.png", picture(), "image/png"), ("b.png", picture(), "image/png")])
    assert response.status_code == 503 and count(engine) == 0
    assert not list((application.state.storage.root / "staging").iterdir())


def test_ambiguous_commit_keeps_accepted_files(client, engine, application):
    client.get("/api/brief/session")
    key = uuid4().hex
    def after_commit(session):
        raise OperationalError("synthetic", {}, Exception("response lost after commit"))
    event.listen(Session, "after_commit", after_commit)
    try:
        assert send(client, key=key, uploads=[("a.png", picture(), "image/png")]).status_code == 503
    finally:
        event.remove(Session, "after_commit", after_commit)
    assert count(engine) == 1
    assert cleanup_orphans(engine, application.state.storage, 0) == 0
    assert send(client, key=key, uploads=[("a.png", picture(), "image/png")]).status_code == 200
    assert len(list((application.state.storage.root / "objects").glob("*/*"))) == 1


def test_secure_cookie_in_https_mode(engine, tmp_path):
    settings = Settings(engine.url, "test-secret-" * 4, tmp_path, "https://testserver")
    with TestClient(create_app(settings, engine), base_url="https://testserver") as client:
        response = client.get("/api/brief/session")
        cookie = response.headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Path=/api/brief" in cookie and "Domain=" not in cookie
        assert send(client).status_code == 200
        assert client.get("/api/brief/session").json()["submitted"] is True


def test_db_down_and_no_origin_access(client, engine):
    def fail(*args):
        raise OperationalError("synthetic", {}, Exception("db down"))
    event.listen(engine, "before_cursor_execute", fail)
    try:
        assert send(client).status_code == 503
        assert client.get("/api/health").status_code == 503
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert send(client, headers={"Origin": "https://elsewhere.invalid"}).status_code == 403
    assert send(client).status_code == 200


@pytest.mark.parametrize("filename,content", [
    ("a.jpg", picture("JPEG")), ("a.jpeg", picture("JPEG")), ("a.png", picture()),
    ("a.webp", picture("WEBP")), ("a.gif", picture("GIF")), ("a.pdf", pdf()),
    ("a.docx", office()), ("a.xlsx", office("xlsx")),
])
def test_allowed_types(client, filename, content):
    response = send(client, uploads=[(filename, content, "application/octet-stream")])
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("name", ["document.doc", "sheet.xls"])
def test_real_legacy_office(client, name):
    fixture = next(
        candidate
        for parent in Path(__file__).resolve().parents
        if (candidate := parent / "tests" / "fixtures" / name).is_file()
    )
    data = fixture.read_bytes()
    assert send(client, uploads=[(name, data, "application/octet-stream")]).status_code == 200
    wrong_name = "wrong.xls" if name.endswith(".doc") else "wrong.doc"
    assert send(client, uploads=[(wrong_name, data, "application/octet-stream")]).status_code == 400


@pytest.mark.parametrize("filename,content", [
    ("a.svg", b"<svg/>"), ("a.xml", b"<xml/>"), ("a.heic", b"bad"), ("a.exe", b"MZ"),
    ("a.png", pdf()), ("a.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
    ("a.xls", office("xlsx")), ("a.docx", office("xlsx")), ("a.docx", office(macro=True)),
    ("a.docm", office()), ("../a.png", picture()), ("a" * 241 + ".png", picture()),
    ("empty.png", b""), ("a.pdf", b"%PDF-1.7\nfake\n%%EOF"),
])
def test_rejected_types(client, engine, filename, content):
    assert send(client, uploads=[(filename, content, "image/png")]).status_code == 400
    assert count(engine) == 0


@pytest.mark.parametrize("sizes,expected", [
    ([10 * 1024 * 1024], 200), ([10 * 1024 * 1024 + 1], 413),
    ([10 * 1024 * 1024] * 3, 200), ([10 * 1024 * 1024] * 3 + [1], 413),
    ([100] * 6, 200), ([100] * 7, 400),
])
def test_limits(client, sizes, expected):
    # Valid PNG plus harmless padding keeps real format checks in the boundary test.
    files = [(f"a{i}.png", picture().ljust(max(n, len(picture())), b"\0"), "image/png") for i, n in enumerate(sizes)]
    assert send(client, uploads=files).status_code == expected


def test_duplicate_fields_and_raw_body(client):
    response = client.post("/api/brief", files=[("message", (None, "a" * 12)), ("message", (None, "b" * 12))], headers={"Idempotency-Key": uuid4().hex})
    assert response.status_code == 400
    response = client.post("/api/brief", content=b"x", headers={"Content-Length": str(32 * 1024 * 1024)})
    assert response.status_code == 413


def test_restart_and_cleanup_preserve_accepted(client, engine, application, tmp_path):
    result = send(client, uploads=[("a.png", picture(), "image/png")])
    with engine.connect() as conn:
        key = conn.execute(text("SELECT storage_key FROM lead_files")).scalar_one()
    orphan = application.state.storage.root / "objects" / str(uuid4())
    orphan.mkdir()
    (orphan / str(uuid4())).write_bytes(b"orphan")
    assert cleanup_orphans(engine, application.state.storage, 0) == 1
    settings = Settings(engine.url, "test-secret-" * 4, tmp_path, "http://testserver", True)
    with TestClient(create_app(settings, engine)) as restarted:
        assert restarted.get("/api/health").status_code == 200
    assert result.status_code == 200 and (tmp_path / key).read_bytes() == picture()


@pytest.mark.parametrize("mode", ["disabled", "timeout", "http", "negative", "success"])
def test_telegram_never_breaks_acceptance(engine, tmp_path, mode, monkeypatch, caplog):
    settings = Settings(engine.url, "test-secret-" * 4, tmp_path, "http://testserver", True,
                        telegram_token="synthetic-secret-token" if mode != "disabled" else "", telegram_chat="123")
    def handler(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("synthetic")
        return httpx.Response(502 if mode == "http" else 200, json={"ok": mode == "success"})
    monkeypatch.setattr("app.main.notify", lambda *args: notify(*args, transport=httpx.MockTransport(handler)))
    with TestClient(create_app(settings, engine)) as client, caplog.at_level(logging.INFO):
        assert send(client).status_code == 200
    assert "synthetic-secret-token" not in caplog.text and fields()["contact"] not in caplog.text
