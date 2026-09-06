"""Integration check for an existing LOCAL synthetic Compose stack; never targets SSH."""
from scripts.local.stack import command as stack_command
import json
import os
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit

base = os.getenv("E2E_BASE_URL", "http://localhost:8080")
if urlsplit(base).hostname not in {"localhost", "127.0.0.1"}:
    raise SystemExit("This restart/rate-limit test is restricted to a local synthetic stack.")


def compose(*args, capture=False):
    return subprocess.run([*stack_command(), *args], check=True, text=True, encoding="utf-8",
                          stdout=subprocess.PIPE if capture else None).stdout


def snapshot():
    code = """import hashlib,json
from pathlib import Path
from sqlalchemy import create_engine,text
from app.config import Settings
s=Settings.from_env()
with create_engine(s.database_url).connect() as c:
    leads=c.execute(text('SELECT count(*) FROM leads')).scalar_one()
    files=[(str(i),hashlib.sha256((s.storage_root/k).read_bytes()).hexdigest()) for i,k in c.execute(text('SELECT id,storage_key FROM lead_files ORDER BY id'))]
print(json.dumps([leads,files]))
"""
    return json.loads(compose("exec", "-T", "api", "python", "-c", code, capture=True))


def request(path, *, headers=None, data=None):
    req = urllib.request.Request(base + path, data=data, headers=headers or {})
    try:
        return urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        return error


config = json.loads(compose("config", "--format", "json", capture=True))
for service in ("db", "api", "frontend", "admin"):
    assert not config["services"][service].get("ports"), f"{service} must not publish ports"
for service, check in {
    "api": "test ! -e /app/tests -a ! -e /app/prompt -a ! -e /app/.env -a ! -e /app/scripts",
    "frontend": "test ! -e /app/apps/admin -a ! -e /app/tests -a ! -e /app/prompt -a ! -e /app/.env",
    "admin": "test ! -e /app/apps/web -a ! -e /app/tests -a ! -e /app/prompt -a ! -e /app/.env",
}.items():
    compose("exec", "-T", service, "sh", "-c", check)
before = snapshot()
assert before[0] > 0 and before[1], "Run synthetic browser submissions before this test"
compose("up", "-d", "--no-deps", "--force-recreate", "--wait", "--wait-timeout", "120", "db")
compose("up", "-d", "--no-deps", "--force-recreate", "--wait", "--wait-timeout", "180", "api", "frontend", "admin", "proxy")
assert snapshot() == before, "Recreating containers changed accepted data or file bytes"
assert request("/api/health").status == 200
for path in ("/uploads/a", "/objects/a", "/api/leads", "/api/files/a", "/api/admin"):
    assert request(path).status == 404
assert request("/api/brief", data=b"", headers={"Content-Length": str(32 * 1024 * 1024)}).status == 413
limited = False
for index in range(600):
    response = request("/api/brief", data=b"x", headers={"X-Real-IP": f"10.0.{index // 255}.{index % 255}", "X-Forwarded-For": f"10.1.{index // 255}.{index % 255}"})
    if response.status == 429:
        assert int(response.headers["Retry-After"]) > 0
        assert json.load(response)["code"] == "rate_limited"
        limited = True
        break
assert limited, "Forged forwarding headers bypassed the configured rate limit"
assert snapshot() == before
print(f"Compose verified: {before[0]} briefs and {len(before[1])} files retained; runtime images clean; ports private; proxy size/rate limits work.")
