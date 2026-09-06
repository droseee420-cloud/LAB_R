"""Failure injection checks stage ordering and retained release state on Linux."""
import json
import os
from pathlib import Path

import pytest

from scripts.deploy import remote as remote


@pytest.mark.skipif(os.name != "posix", reason="Server release symlinks/flock require Linux")
@pytest.mark.parametrize("failure", ["build", "migrations", "application-health"])
def test_failed_stage_retains_previous_release_and_secrets(tmp_path, monkeypatch, failure):
    base = tmp_path / "Lab with spaces Кириллица"
    previous = base / "releases" / "old"
    previous.mkdir(parents=True)
    (base / "current").symlink_to(previous)
    shared = base / "shared"
    shared.mkdir()
    original = {"COMPOSE_PROJECT_NAME": "synthetic", "POSTGRES_PASSWORD": "keep-this-password",
                "COOKIE_SECRET": "keep-this-cookie-secret", "HTTP_TEST_MODE": "true"}
    (shared / "settings.json").write_text(json.dumps(original))
    stages, commands = [], []
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(remote, "install_docker", lambda: None)
    monkeypatch.setattr(remote, "extract_release", lambda archive, target: (target / "compose.yaml").write_text("services: {}"))
    monkeypatch.setattr(remote, "stage", stages.append)

    def execute(argv, cwd=None):
        commands.append(argv)
        if stages[-1] == failure:
            raise RuntimeError("Synthetic command failure")

    monkeypatch.setattr(remote, "execute", execute)
    with pytest.raises(RuntimeError, match="Synthetic command failure"):
        remote.deploy({"app_dir": str(base), "environment": {"COMPOSE_PROJECT_NAME": "synthetic"}}, Path("unused.tar.gz"))
    assert stages[-1] == failure
    assert "ready" not in stages and "orphan-cleanup" not in stages
    assert (base / "current").resolve() == previous
    assert not (base / "previous").exists()
    values = json.loads((shared / "settings.json").read_text())
    assert all(values[key] == value for key, value in original.items())
    assert all("down" not in command and "prune" not in command for command in commands)
