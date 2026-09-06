import io
import os
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import URL, create_engine, text
from starlette.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.storage import LocalStorage


@pytest.fixture(scope="session")
def engine():
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url and os.getenv("TEST_POSTGRES_PASSWORD"):
        url = URL.create("postgresql+psycopg", username=os.getenv("TEST_POSTGRES_USER", "lab"),
                         password=os.environ["TEST_POSTGRES_PASSWORD"], host=os.getenv("TEST_POSTGRES_HOST", "db"),
                         database=os.getenv("TEST_POSTGRES_DB", "lab_test"))
    database = url.database if isinstance(url, URL) else url.rsplit("/", 1)[-1]
    if not url or "test" not in database:
        pytest.fail("TEST_DATABASE_URL must name a disposable PostgreSQL database containing 'test'")
    db = create_engine(url, pool_size=8)
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")
    yield db
    db.dispose()


@pytest.fixture
def application(engine, tmp_path, monkeypatch):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE admin_sessions, admins, lead_files, leads"))
    settings = Settings(database_url=engine.url, cookie_secret="test-secret-" * 4, storage_root=tmp_path,
                        public_url="http://testserver", http_test_mode=True, rate_limit=1000)
    app = create_app(settings, engine, LocalStorage(tmp_path))
    calls = []
    monkeypatch.setattr("app.main.notify", lambda *args: calls.append(args))
    app.state.notifications = calls
    return app


@pytest.fixture
def client(application):
    with TestClient(application) as value:
        yield value


def fields(**updates):
    return dict(message="Our product needs a careful review.", productLink="https://example.org/product?q=1",
                noProduct="true", contactMethod="email", contact="Test.Name+lab@Example.org",
                name="Synthetic client", consent="true", consentVersion="brief-en-v1", language="en",
                companyWebsite="", **{}) | updates


def send(client, data=None, uploads=(), key=None, **kwargs):
    parts = [(k, (None, v)) for k, v in (fields() if data is None else data).items()]
    parts.extend(("files", upload) for upload in uploads)
    headers = {"Idempotency-Key": key or uuid4().hex} | kwargs.pop("headers", {})
    return client.post("/api/brief", files=parts, headers=headers, **kwargs)


def picture(fmt="PNG"):
    out = io.BytesIO()
    Image.new("RGB", (3, 2), "blue").save(out, format=fmt)
    return out.getvalue()


def pdf():
    out = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(out)
    return out.getvalue()


def office(ext="docx", macro=False):
    part = "word/document.xml" if ext == "docx" else "xl/workbook.xml"
    ns = "wordprocessingml" if ext == "docx" else "spreadsheetml"
    kind, root = ("document", "document") if ext == "docx" else ("sheet", "workbook")
    out = io.BytesIO()
    with ZipFile(out, "w") as z:
        z.writestr("[Content_Types].xml", f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/{part}" ContentType="application/vnd.openxmlformats-officedocument.{ns}.{kind}.main+xml"/></Types>')
        z.writestr("_rels/.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{part}"/></Relationships>')
        z.writestr(part, f'<{root} xmlns="http://schemas.openxmlformats.org/{ns}/2006/main"/>')
        if macro:
            z.writestr("word/vbaProject.bin", b"synthetic macro")
    return out.getvalue()
