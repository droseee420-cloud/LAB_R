from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def test_existing_schema_upgrade_keeps_briefs(engine):
    schema = "migration_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    migrated = create_engine(url)
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.attributes["database_url"] = url
    try:
        command.upgrade(cfg, "0001")
        with migrated.begin() as conn:
            conn.execute(text("""INSERT INTO leads
                (id,contact_method,contact,contact_normalized,message,no_product,language,idempotency_hash,payload_hash,consent,consent_version)
                VALUES (:id,'email','synthetic@example.org','synthetic@example.org','Existing synthetic brief.',false,'en',:hash,:hash,true,'brief-en-v1')"""),
                         {"id": uuid4(), "hash": "a" * 64})
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        with migrated.connect() as conn:
            assert conn.execute(text("SELECT message, notes, notes_version FROM leads")).one() == ("Existing synthetic brief.", None, 0)
            assert conn.execute(text("SELECT to_regclass('admins'), to_regclass('admin_sessions')")).one() == ("admins", "admin_sessions")
        command.check(cfg)
    finally:
        migrated.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
