"""Read-only verification of a synthetic E2E brief, never a public endpoint."""
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import UUID

if "__file__" in globals():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/api"))
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from app.config import Settings  # noqa: E402
from app.models import Lead, LeadFile  # noqa: E402


expected = json.load(sys.stdin)
engine = create_engine(os.getenv("TEST_DATABASE_URL") or Settings.from_env().database_url)
with Session(engine) as db:
    lead = db.get(Lead, UUID(sys.argv[1]))
    assert lead is not None
    for key, value in expected["fields"].items():
        assert getattr(lead, key) == value, f"Field mismatch: {key}"
    files = list(db.scalars(select(LeadFile).where(LeadFile.lead_id == lead.id)))
    assert len(files) == len(expected.get("files", []))
    for item in expected.get("files", []):
        file = next(f for f in files if f.filename == item["filename"])
        assert file.sha256 == item["sha256"] and file.size_bytes == item["size"]
        root = Path(os.environ["STORAGE_ROOT"])
        assert hashlib.sha256((root / file.storage_key).read_bytes()).hexdigest() == item["sha256"]
    if expected.get("unique_message"):
        assert len(list(db.scalars(select(Lead).where(Lead.message == lead.message)))) == 1
engine.dispose()
print("Stored fields and file bytes verified.")
