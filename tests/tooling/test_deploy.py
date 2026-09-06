import io
import json
import tarfile
from pathlib import Path

import paramiko
import pytest

from scripts.deploy.client import DeployError, PinnedHostKey, fingerprint, load_config, server_settings
from scripts.deploy.release import package_release
from scripts.deploy.remote import atomic_write, dotenv, extract_release


def test_release_excludes_secrets_and_contains_working_changes(tmp_path):
    root = tmp_path / "source with spaces Кириллица"
    root.mkdir()
    for name in ["package.json", "infra/compose/compose.yaml", "apps/web/app/page.tsx", "apps/api/app/main.py",
                 "prompt/implementation-prompt.md", ".git/config", "node_modules/secret",
                 "scripts/deploy/config.local.json", ".env", "apps/api/.env.production", "apps/web/app/key.pem"]:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("working source" if name in {"apps/web/app/page.tsx", "apps/api/app/main.py", "package.json", "infra/compose/compose.yaml"} else "SECRET_MARKER")
    archive = tmp_path / "release.tar.gz"
    entries = package_release(root, archive)
    assert set(entries) == {"package.json", "infra/compose/compose.yaml", "apps/web/app/page.tsx", "apps/api/app/main.py"}
    with tarfile.open(archive) as tar:
        assert all(b"SECRET_MARKER" not in tar.extractfile(member).read() for member in tar)
    target = tmp_path / "extract"
    target.mkdir()
    extract_release(archive, target)
    assert (target / "apps/web/app/page.tsx").read_text() == "working source"


@pytest.mark.parametrize("name", ["../outside", "/outside", "a/../../outside", "prompt/private.md", "scripts/deploy/config.local.json"])
def test_archive_traversal_and_secrets_rejected(tmp_path, name):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        entry = tarfile.TarInfo(name)
        entry.size = 1
        tar.addfile(entry, io.BytesIO(b"x"))
    target = tmp_path / "destination"
    target.mkdir()
    with pytest.raises(ValueError):
        extract_release(archive, target)


def test_password_special_characters_are_data(tmp_path):
    config = json.loads(Path("scripts/deploy/config.example.json").read_text())
    config["password"] = "local SSH ' \" $() ` ; Кириллица\\password"
    config["sudo_password"] = "sudo-secret"
    config["app_dir"] = "/opt/Lab with spaces Кириллица"
    config["telegram_bot_token"] = "remote'quoted$value\\path"
    path = tmp_path / "deploy.local.json"
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    loaded = load_config(path)
    payload = server_settings(loaded)
    assert "local SSH" not in json.dumps(payload) and "sudo-secret" not in json.dumps(payload)
    assert payload["app_dir"] == config["app_dir"]
    assert payload["environment"]["TELEGRAM_BOT_TOKEN"] == config["telegram_bot_token"]
    rendered = dotenv(payload["environment"])
    assert 'TELEGRAM_BOT_TOKEN="remote\'quoted$$value\\\\path"' in rendered
    target = tmp_path / "settings.json"
    atomic_write(target, json.dumps(payload))
    assert json.loads(target.read_text()) == payload


def test_host_key_verification():
    key = paramiko.RSAKey.generate(2048)
    PinnedHostKey(fingerprint(key)).missing_host_key(None, "synthetic", key)
    with pytest.raises(DeployError):
        PinnedHostKey("SHA256:wrong").missing_host_key(None, "synthetic", key)
    with pytest.raises(DeployError):
        PinnedHostKey(None).missing_host_key(None, "synthetic", key)


@pytest.mark.parametrize("update", [
    {"app_dir": "/"}, {"app_dir": "/opt/../etc"}, {"project_name": "x;echo secret"},
    {"public_url": "http://example.org", "http_test_mode": False},
    {"public_url": "https://example.org", "http_test_mode": True},
    {"proxy_rate": "1r/s; echo secret"}, {"password": "bad\npassword"},
])
def test_invalid_configuration_fails_locally(tmp_path, update):
    config = json.loads(Path("scripts/deploy/config.example.json").read_text()) | update
    path = tmp_path / "deploy.local.json"
    path.write_text(json.dumps(config))
    with pytest.raises((DeployError, ValueError)):
        load_config(path)
