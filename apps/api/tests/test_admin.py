import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app import admin_auth as auth
from app.admin_bootstrap import bootstrap
from app.admin_service import download as service_download
from app.admin_service import recover
from app.admin_service import remove as service_remove
from app.config import Settings
from app.main import create_app
from app.models import Admin, AdminSession, Lead, LeadFile
from conftest import fields, picture, send

pytestmark = pytest.mark.integration
PASSWORD = "synthetic-admin-password-for-tests"
ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def logged(client, application, engine):
    for name in ("synthetic_one", "synthetic_two", "synthetic_three"):
        auth.manage(engine, "create", name, PASSWORD)
    response = client.post("/api/admin/login", json={"username": "synthetic_one", "password": PASSWORD}, headers=ORIGIN)
    assert response.status_code == 200
    token = client.get("/api/admin/session").json()["csrf_token"]
    return client, ORIGIN | {"X-CSRF-Token": token}


def lead(client, files=True, **updates):
    return send(client, fields(**updates), uploads=[("Тест.png", picture(), "image/png")] if files else []).json()["id"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/leads"),
        ("GET", "/leads/{}"),
        ("PATCH", "/leads/{}/notes"),
        ("GET", "/files/{}/download"),
        ("DELETE", "/files/{}"),
        ("DELETE", "/leads/{}"),
    ],
)
def test_anonymous_cannot_access(client, method, path):
    response = client.request(method, "/api/admin" + path.format(uuid4()), json={"notes": "x", "notes_version": 0})
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_sessions_password_reset_disable_and_three_accounts(logged, engine):
    client, headers = logged
    raw = client.cookies.get(auth.COOKIE)
    with Session(engine) as db:
        session = db.get(AdminSession, auth.digest(raw))
        assert session and raw not in session.token_hash
        assert len(list(db.scalars(select(Admin)))) == 3
        assert all(
            a.password_hash.startswith("$argon2id$") and PASSWORD not in a.password_hash
            for a in db.scalars(select(Admin))
        )
    auth.manage(engine, "reset-password", "synthetic_one", PASSWORD + "new")
    assert client.get("/api/admin/session").status_code == 401
    auth.manage(engine, "disable", "synthetic_two")
    disabled = client.post("/api/admin/login", json={"username": "synthetic_two", "password": PASSWORD}, headers=ORIGIN)
    unknown = client.post("/api/admin/login", json={"username": "missing", "password": PASSWORD}, headers=ORIGIN)
    assert disabled.status_code == unknown.status_code == 401 and disabled.json() == unknown.json()
    auth.manage(engine, "enable", "synthetic_two")
    assert (
        client.post(
            "/api/admin/login", json={"username": "synthetic_two", "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 200
    )
    with Session(engine) as db, db.begin():
        db.execute(update(AdminSession).values(expires_at=auth.now() - timedelta(seconds=1)))
    assert client.get("/api/admin/session").status_code == 401
    client.cookies.set(auth.COOKIE, "forged")
    assert client.get("/api/admin/session").status_code == 401


def test_bootstrap_is_exactly_three_and_never_resets_existing_password(engine):
    accounts = [{"username": f"bootstrap_{index}", "password": PASSWORD + str(index)} for index in range(3)]
    bootstrap(engine, accounts)
    bootstrap(engine, [{**account, "password": "replacement-password-ignored"} for account in accounts])
    assert auth.login(
        engine, type("S", (), {"admin_session_hours": 12}), accounts[0]["username"], accounts[0]["password"]
    )
    assert not auth.login(
        engine, type("S", (), {"admin_session_hours": 12}), accounts[0]["username"], "replacement-password-ignored"
    )
    with pytest.raises(ValueError):
        bootstrap(engine, accounts[:2])


def test_concurrent_failed_login_and_session_cleanup(logged, engine):
    def attempt(_):
        return auth.login(engine, type("S", (), {"admin_session_hours": 12}), "missing-user", "incorrect-password")

    with ThreadPoolExecutor(6) as pool:
        assert list(pool.map(attempt, range(6))) == [None] * 6
    with Session(engine) as db, db.begin():
        db.execute(update(AdminSession).values(expires_at=auth.now() - timedelta(seconds=1)))
    assert auth.manage(engine, "cleanup-sessions") >= 1
    with Session(engine) as db:
        assert not list(db.scalars(select(AdminSession)))


def test_logout_csrf_origin_and_public_cookie_separation(logged):
    client, headers = logged
    client.get("/api/brief/session")
    assert client.post("/api/admin/logout", headers=ORIGIN).status_code == 403
    assert client.post("/api/admin/logout", headers=headers | {"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/admin/logout", headers={"X-CSRF-Token": headers["X-CSRF-Token"]}).status_code == 403
    assert client.post("/api/admin/logout", headers=headers).status_code == 204
    assert client.get("/api/admin/session").status_code == 401


def test_login_limits_and_secure_cookie(application, engine):
    auth.manage(engine, "create", "synthetic_one", PASSWORD)
    settings = Settings(
        database_url=engine.url,
        cookie_secret="s" * 64,
        storage_root=application.state.storage.root,
        public_url="https://testserver",
        admin_login_limit=2,
    )
    with TestClient(create_app(settings, engine), base_url="https://testserver") as client:
        result = client.post(
            "/api/admin/login",
            json={"username": "synthetic_one", "password": PASSWORD},
            headers={"Origin": "https://testserver"},
        )
        cookie = result.headers["set-cookie"]
        assert all(
            flag in cookie for flag in ["Secure", "HttpOnly", "SameSite=strict", "Path=/api/admin", "Max-Age=43200"]
        )
        client.post(
            "/api/admin/login",
            json={"username": "missing", "password": "wrong"},
            headers={"Origin": "https://testserver"},
        )
        result = client.post(
            "/api/admin/login",
            json={"username": "missing", "password": "wrong"},
            headers={"Origin": "https://testserver", "X-Real-IP": "1.2.3.4"},
        )
        assert result.status_code == 429 and int(result.headers["retry-after"]) > 0


def test_filters_pagination_details_related_and_whitelist(logged):
    client, _ = logged
    first = lead(client, name="<script>alert(1)</script>")
    second = lead(client, False, name="Another", language="es")
    third = lead(client, False, contactMethod="telegram", contact="@different_user", name="Another", language="ca")
    for query, total in [
        ("", 3),
        ("q=" + first, 1),
        ("q=another", 2),
        ("q=test.name%2Blab", 2),
        ("q=careful", 3),
        ("q=absent", 0),
        ("contact_method=telegram", 1),
        ("language=es", 1),
        ("has_files=true", 1),
        ("has_files=false", 2),
        ("date_from=2000-01-01&date_to=2099-01-01", 3),
        ("date_to=2000-01-01", 0),
        ("language=es&has_files=false&contact_method=email", 1),
        ("page=2", 3),
    ]:
        result = client.get("/api/admin/leads?" + query)
        assert result.status_code == 200, result.text
        assert result.json()["total"] == total
        if query == "page=2":
            assert not result.json()["items"]
    for bad in [
        "page_size=1000",
        "sort=injected",
        "page=0",
        "date_from=wrong",
        "date_from=2026-01-01&date_to=2025-01-01",
    ]:
        assert client.get("/api/admin/leads?" + bad).status_code == 422
    assert [x["id"] for x in client.get("/api/admin/leads?sort=asc").json()["items"]] == [first, second, third]
    result = client.get("/api/admin/leads/" + first).json()
    assert [x["id"] for x in result["related"]] == [second]
    assert result["name"] == "<script>alert(1)</script>"
    for forbidden in ["status", "storage_key", "browser_hash", "idempotency_hash", "payload_hash", "password_hash"]:
        assert forbidden not in str(result)


def test_notes_concurrency_limits_and_clear(logged):
    client, headers = logged
    identifier = lead(client)
    path = f"/api/admin/leads/{identifier}/notes"
    assert client.patch(path, json={"notes": "x", "notes_version": 0}).status_code == 403

    def save(value):
        return client.patch(path, json={"notes": value, "notes_version": 0}, headers=headers)

    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(save, ["<b>first</b>", "second"]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert client.patch(path, json={"notes": "x" * 10001, "notes_version": 1}, headers=headers).status_code == 422
    assert client.patch(path, json={"notes": "", "notes_version": 1}, headers=headers).json() == {
        "notes": None,
        "notes_version": 2,
    }


def test_download_and_idempotent_file_delete(logged, engine):
    client, headers = logged
    identifier = lead(client)
    detail = client.get("/api/admin/leads/" + identifier).json()
    file = detail["files"][0]
    download = client.get(f"/api/admin/files/{file['id']}/download")
    assert download.content == picture() and hashlib.sha256(download.content).hexdigest() == file["sha256"]
    assert "filename*=UTF-8''" in download.headers["content-disposition"]
    assert download.headers["x-content-type-options"] == "nosniff"
    for _ in range(2):
        assert client.delete("/api/admin/files/" + file["id"], headers=headers).status_code == 204
    assert client.get(f"/api/admin/files/{file['id']}/download").status_code == 404
    assert client.get("/api/admin/leads/" + identifier).json()["file_count"] == 0
    with Session(engine) as db:
        assert db.get(Lead, UUID(identifier))


def test_download_holds_storage_lock_until_stream_finishes(logged, application, engine):
    client, _ = logged
    identifier = lead(client)
    with Session(engine) as db:
        file_id = db.scalar(select(LeadFile.id).where(LeadFile.lead_id == UUID(identifier)))
    info, chunks = service_download(engine, application.state.storage, file_id)
    assert info["size_bytes"] == len(picture())
    with ThreadPoolExecutor(1) as pool:
        deletion = pool.submit(service_remove, engine, application.state.storage, file_id)
        assert next(chunks)
        assert not deletion.done()
        chunks.close()
        deletion.result(timeout=5)


def test_delete_lead_unblocks_browser_and_keeps_others(logged, application):
    client, headers = logged
    other = lead(client, False)
    client.get("/api/brief/session")
    identifier = lead(client)
    assert send(client).status_code == 409
    file = client.get("/api/admin/leads/" + identifier).json()["files"][0]
    assert client.delete("/api/admin/files/" + file["id"], headers=headers).status_code == 204
    assert send(client).status_code == 409
    for _ in range(2):
        assert client.delete("/api/admin/leads/" + identifier, headers=headers).status_code == 204
    assert send(client).status_code == 200
    assert client.get("/api/admin/leads/" + other).status_code == 200
    assert not list((application.state.storage.root / "trash").rglob("*.png"))


@pytest.mark.parametrize("failure", ["file", "commit", "ambiguous"])
def test_delete_failure_and_recovery(logged, application, engine, monkeypatch, failure):
    client, headers = logged
    identifier = lead(client)
    storage = application.state.storage
    with Session(engine) as db:
        file = db.scalar(select(LeadFile).where(LeadFile.lead_id == UUID(identifier)))
        key = file.storage_key

    def broken(*args):
        raise OSError("synthetic disk failure")

    def commit(*args):
        raise OperationalError("synthetic", {}, Exception("failure"))

    if failure == "file":
        monkeypatch.setattr(storage, "quarantine", broken)
    else:
        event.listen(Session, "after_commit" if failure == "ambiguous" else "before_commit", commit)
    try:
        assert client.delete("/api/admin/leads/" + identifier, headers=headers).status_code == 503
    finally:
        if failure != "file":
            event.remove(Session, "after_commit" if failure == "ambiguous" else "before_commit", commit)
    monkeypatch.undo()
    recover(engine, storage)
    if failure != "ambiguous":
        assert storage.read(key).read() == picture()
        assert client.get("/api/admin/leads/" + identifier).status_code == 200
    assert client.delete("/api/admin/leads/" + identifier, headers=headers).status_code == 204
    assert not storage._object(key).exists() and not storage._trash(key).exists()


def test_crash_recovery_restores_live_files_and_missing_bytes(logged, application, engine):
    client, headers = logged
    identifier = lead(client)
    storage = application.state.storage
    with Session(engine) as db:
        file = db.scalar(select(LeadFile).where(LeadFile.lead_id == UUID(identifier)))
        key, file_id = file.storage_key, file.id
    storage.quarantine(key)
    recover(engine, storage)
    assert client.get(f"/api/admin/files/{file_id}/download").content == picture()
    storage.delete(key)
    response = client.get(f"/api/admin/files/{file_id}/download")
    assert response.status_code == 503 and str(storage.root) not in response.text
    assert client.delete("/api/admin/leads/" + identifier, headers=headers).status_code == 503
    assert client.get("/api/admin/leads/" + identifier).status_code == 200
