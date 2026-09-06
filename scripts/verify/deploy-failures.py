"""Real failed Docker build/migration/health commands on a local synthetic stack."""
from scripts.local.stack import command as stack_command
import json
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from scripts.deploy.remote import execute


def fails(command):
    try:
        execute(command)
    except RuntimeError:
        return
    raise AssertionError("Expected deployment command to fail")


config = json.loads(subprocess.check_output([*stack_command(), "config", "--format", "json"], text=True, encoding="utf-8"))
assert urlsplit(config["services"]["api"]["environment"]["PUBLIC_URL"]).hostname in {"localhost", "127.0.0.1"}, "Local synthetic stack only"
with tempfile.TemporaryDirectory(prefix="lab-failure-") as directory:
    root = Path(directory)
    (root / "Dockerfile").write_text("FROM scratch\nCOPY deliberately-missing-file /missing\n", encoding="utf-8")
    fails(["docker", "build", "--network", "none", str(root)])
    # Unknown revision fails before applying any migration to the synthetic local database.
    fails([*stack_command(), "run", "--rm", "--no-deps", "migrate", "python", "-m", "alembic", "upgrade", "synthetic_missing_revision"])
    project = "lab-failure-" + uuid4().hex[:8]
    compose_file = root / "compose.yaml"
    compose_file.write_text("services:\n  unhealthy:\n    image: alpine:3.22\n    command: [sleep, '120']\n    healthcheck:\n      test: [CMD, 'false']\n      interval: 1s\n      timeout: 1s\n      retries: 1\n", encoding="utf-8")
    compose = ["docker", "compose", "-p", project, "-f", str(compose_file)]
    try:
        fails(compose + ["up", "-d", "--wait", "--wait-timeout", "15"])
    finally:
        execute(compose + ["down"])
print("Actual failed Docker build, Alembic migration and container healthcheck all propagated as failures.")
