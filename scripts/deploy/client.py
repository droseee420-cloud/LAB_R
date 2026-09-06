"""Windows entry point: verified SSH, protected config, allowlisted upload."""
import argparse
import base64
import hashlib
import gzip
import ipaddress
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

import paramiko

from scripts.deploy.release import package_release


class DeployError(Exception):
    pass


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


class PinnedHostKey(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected):
        self.expected = expected

    def missing_host_key(self, client, hostname, key):
        if not self.expected or fingerprint(key) != self.expected:
            raise DeployError("SSH host key is not trusted. Verify its SHA256 fingerprint through the server provider.")


def load_config(path: Path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    required = {"host", "username", "app_dir", "project_name", "public_url", "http_test_mode"}
    if not isinstance(config, dict) or required - config.keys():
        raise DeployError("Missing required configuration fields")
    for value in config.values():
        if isinstance(value, str) and any(c in value for c in "\r\n\0"):
            raise DeployError("Configuration values must not contain line breaks or NUL")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", config["project_name"]):
        raise DeployError("Invalid Compose project name")
    directory = PurePosixPath(config["app_dir"])
    if not directory.is_absolute() or len(directory.parts) < 3 or ".." in directory.parts:
        raise DeployError("app_dir must be a dedicated absolute directory, for example /opt/refraction-lab")
    url = urlsplit(config["public_url"])
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
        raise DeployError("public_url must be an HTTP(S) origin")
    if not isinstance(config["http_test_mode"], bool) or (url.scheme == "http") != config["http_test_mode"]:
        raise DeployError("HTTP requires http_test_mode=true; HTTPS requires false")
    if url.scheme == "https" and not config.get("tls_cert_dir"):
        raise DeployError("HTTPS requires an existing certificate directory on the server")
    if not 1 <= int(config.get("port", 22)) <= 65535 or not 1 <= int(config.get("http_port", 80)) <= 65535:
        raise DeployError("Invalid port")
    if not re.fullmatch(r"[1-9][0-9]{0,4}r/[sm]", config.get("proxy_rate", "6r/m")):
        raise DeployError("Invalid proxy_rate")
    if not 1 <= int(config.get("proxy_burst", 6)) <= 100:
        raise DeployError("Invalid proxy_burst")
    ipaddress.ip_network(config.get("app_subnet", "172.30.80.0/24"))
    ipaddress.ip_address(config.get("bind_address", "0.0.0.0"))
    if config.get("build_mode", "remote") not in {"remote", "local"}:
        raise DeployError("build_mode must be remote or local")
    if config.get("admin_base_path", "/admin") not in {"", "/admin"}:
        raise DeployError("admin_base_path must be /admin or empty for a dedicated hostname")
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", config.get("admin_host", "admin.invalid")):
        raise DeployError("Invalid admin_host")
    if config.get("admin_origin"):
        admin = urlsplit(config["admin_origin"])
        if admin.scheme != url.scheme or not admin.hostname or admin.username or admin.password or admin.path not in {"", "/"} or admin.query or admin.fragment:
            raise DeployError("Invalid admin_origin")
    for field in ("known_hosts", "key_filename"):
        if config.get(field):
            config[field] = str((path.parent / config[field]).resolve())
    if not config.get("password") and not config.get("key_filename"):
        raise DeployError("Configure an SSH password or key_filename")
    accounts = config.get("initial_admins", [])
    if accounts:
        if not isinstance(accounts, list) or len(accounts) != 3:
            raise DeployError("initial_admins must contain exactly three accounts")
        names = []
        for account in accounts:
            name, password = account.get("username", "").strip().lower(), account.get("password", "")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,79}", name) or not isinstance(password, str) or not 12 <= len(password) <= 1024 or any(c in password for c in "\r\n\0"):
                raise DeployError("Invalid initial administrator credentials")
            names.append(name)
        if len(set(names)) != 3:
            raise DeployError("Initial usernames must be distinct")
    return config


def server_settings(config):
    # Explicit mapping: SSH password, key path, passphrase and sudo password NEVER travel in this payload.
    mapping = {
        "project_name": "COMPOSE_PROJECT_NAME", "public_url": "PUBLIC_URL", "http_test_mode": "HTTP_TEST_MODE",
        "http_port": "HTTP_PORT", "bind_address": "BIND_ADDRESS", "tls_cert_dir": "TLS_CERT_DIR",
        "app_subnet": "APP_SUBNET", "cookie_days": "COOKIE_DAYS", "rate_limit": "RATE_LIMIT", "rate_window": "RATE_WINDOW",
        "proxy_rate": "PROXY_RATE", "proxy_burst": "PROXY_BURST", "telegram_bot_token": "TELEGRAM_BOT_TOKEN", "telegram_chat_id": "TELEGRAM_CHAT_ID",
        "admin_origin": "ADMIN_ORIGIN", "admin_host": "ADMIN_HOST", "admin_base_path": "ADMIN_BASE_PATH", "admin_session_hours": "ADMIN_SESSION_HOURS",
    }
    values = {dest: str(config[src]).lower() if isinstance(config[src], bool) else str(config[src]) for src, dest in mapping.items() if src in config}
    return {"app_dir": config["app_dir"], "environment": values}


def connect(config):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if config.get("known_hosts") and Path(config["known_hosts"]).exists():
        client.load_host_keys(config["known_hosts"])
    client.set_missing_host_key_policy(PinnedHostKey(config.get("host_fingerprint")))
    try:
        private_key = paramiko.PKey.from_path(config["key_filename"], passphrase=config.get("key_passphrase") or None) if config.get("key_filename") else None
        client.connect(hostname=config["host"], port=int(config.get("port", 22)), username=config["username"],
                       password=config.get("password") or None, pkey=private_key,
                       look_for_keys=False, allow_agent=False, timeout=15, auth_timeout=15, banner_timeout=15)
    except Exception:
        client.close()
        raise
    return client


def run(client, argv, config=None, capture=False, input_data=None):
    command = shlex.join(argv)
    if config and config.get("sudo"):
        command = "sudo -S -p '' -- " + command
    stdin, stdout, stderr = client.exec_command(command, timeout=1800)
    if config and config.get("sudo"):
        stdin.write((config.get("sudo_password") or config.get("password") or "") + "\n")
        stdin.flush()
    if input_data is not None:
        stdin.write(input_data)
        stdin.flush()
    stdin.channel.shutdown_write()
    # Remote helpers output only short stage labels. Drain both streams to prevent deadlock.
    channel, chunks = stdout.channel, []
    import time
    deadline = time.monotonic() + 1800
    while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
        if time.monotonic() > deadline:
            channel.close()
            raise DeployError("Remote command timed out")
        if channel.recv_ready():
            part = channel.recv(65536)
            if capture:
                chunks.append(part)
            else:
                # Only print known helper status lines, never arbitrary Docker/SSH output.
                for line in part.decode("utf-8", "replace").splitlines():
                    if line.startswith("LAB_STAGE "):
                        print(line, flush=True)
        if channel.recv_stderr_ready():
            channel.recv_stderr(65536)
        time.sleep(0.05)
    if channel.recv_exit_status() != 0:
        raise DeployError("Remote step failed; deployment stopped. Existing data volumes and previous release are retained.")
    return b"".join(chunks).decode().strip() if capture else None


def deploy(config, root: Path):
    with tempfile.TemporaryDirectory(prefix="lab-release-") as local:
        archive = Path(local) / "release.tar.gz"
        package_release(root, archive)
        payload = Path(local) / "settings.json"
        release_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
        settings = server_settings(config) | {"release_id": release_id, "build_mode": config.get("build_mode", "remote")}
        payload.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
        images = None
        if settings["build_mode"] == "local":
            print("LAB_STAGE local-build", flush=True)
            tags = [f"{config['project_name']}-{name}:{release_id}" for name in ("api", "frontend", "admin")]
            for name, tag in zip(("api", "frontend", "admin"), tags):
                args = ["docker", "build", "--platform", "linux/amd64", "-t", tag, "-f", "apps/api/Dockerfile" if name == "api" else "infra/docker/frontend.Dockerfile"]
                if name != "api":
                    args += ["--build-arg", "PUBLIC_URL=" + config["public_url"], "--build-arg", "APP_NAME=" + ("web" if name == "frontend" else "admin"), "--build-arg", "ADMIN_BASE_PATH=" + config.get("admin_base_path", "/admin")]
                subprocess.run(args + ["."], cwd=root, check=True)
            images = Path(local) / "images.tar.gz"
            with gzip.open(images, "wb", compresslevel=1) as output:
                process = subprocess.Popen(["docker", "image", "save", *tags], stdout=subprocess.PIPE)
                try:
                    shutil.copyfileobj(process.stdout, output, 1024 * 1024)
                finally:
                    process.stdout.close()
                if process.wait() != 0:
                    raise DeployError("Could not export local images")
        client = connect(config)
        try:
            remote = run(client, ["mktemp", "-d", "/tmp/refraction-upload-XXXXXXXX"], capture=True)
            if not re.fullmatch(r"/tmp/refraction-upload-[A-Za-z0-9]{8}", remote):
                raise DeployError("Unexpected remote staging path")
            uploads = [(archive, "release.tar.gz"), (payload, "settings.json"), (root / "scripts/deploy/remote.py", "remote_deploy.py")]
            if images:
                uploads.append((images, "images.tar.gz"))
            print("LAB_STAGE upload", flush=True)
            with client.open_sftp() as sftp:
                for source, name in uploads:
                    target = remote + "/" + name
                    sftp.put(str(source), target)
                    sftp.chmod(target, 0o600)
            try:
                run(client, ["python3", remote + "/remote_deploy.py", remote + "/settings.json", remote + "/release.tar.gz"] + ([remote + "/images.tar.gz"] if images else []), config, input_data=json.dumps(config.get("initial_admins", [])))
            finally:
                # Exact files inside a freshly created, validated directory; no recursive remote deletion.
                with client.open_sftp() as sftp:
                    for _, name in uploads:
                        sftp.remove(remote + "/" + name)
                    sftp.rmdir(remote)
        finally:
            client.close()
    print("Deployment ready: " + config["public_url"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("scripts/deploy/config.local.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(args.config.resolve())
        root = Path(__file__).resolve().parents[2]
        if args.dry_run:
            with tempfile.TemporaryDirectory(prefix="lab-release-") as directory:
                entries = package_release(root, Path(directory) / "release.tar.gz")
            print(f"Configuration and archive validated ({len(entries)} source files). No SSH connection or remote changes.")
            return 0
        deploy(config, root)
        return 0
    except paramiko.BadHostKeyException:
        print("Deployment stopped: the known SSH host key has changed.", file=sys.stderr)
        return 1
    except paramiko.AuthenticationException:
        print("Deployment stopped: SSH authentication failed. Check the configured username and password/key.", file=sys.stderr)
        return 1
    except DeployError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (paramiko.SSHException, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        # Exceptions from SSH/JSON/subprocess may contain passwords or filesystem data.
        print("Deployment failed. Check configuration, verified host key, authentication and the last LAB_STAGE. Secrets are not printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
