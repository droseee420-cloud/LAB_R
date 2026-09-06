"""Runs on Ubuntu as root (directly or via sudo). No production connection on import."""
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def stage(name):
    print("LAB_STAGE " + name, flush=True)


def execute(argv, cwd=None, input_data=None):
    result = subprocess.run(argv, cwd=cwd, input=input_data, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError("Remote command failed")


def dotenv(values):
    lines = []
    for key, value in sorted(values.items()):
        value = str(value)
        if not re.fullmatch(r"[A-Z_]+", key) or any(c in value for c in "\n\r\0"):
            raise ValueError("Invalid environment setting")
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
        lines.append(key + '="' + escaped + '"')
    return "\n".join(lines) + "\n"


def atomic_write(path, content, mode=0o600):
    temp = path.with_name(path.name + ".tmp-" + secrets.token_hex(8))
    with temp.open("x", encoding="utf-8", newline="\n") as file:
        os.chmod(temp, mode)
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)


def install_docker():
    os_release = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            os_release[key] = value.strip('"')
    if os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") not in {"22.04", "24.04"}:
        raise ValueError("Supported targets: Ubuntu 22.04/24.04 LTS")
    if shutil.which("docker"):
        execute(["docker", "info"])
        execute(["docker", "compose", "version"])
        return
    execute(["apt-get", "update"])
    execute(["apt-get", "install", "-y", "ca-certificates", "curl"])
    key_dir = Path("/etc/apt/keyrings")
    key_dir.mkdir(exist_ok=True, mode=0o755)
    with urllib.request.urlopen("https://download.docker.com/linux/ubuntu/gpg", timeout=30) as response:
        atomic_write(key_dir / "docker.asc", response.read().decode(), 0o644)
    architecture = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
    if architecture not in {"amd64", "arm64"}:
        raise ValueError("Unsupported CPU architecture")
    source = Path("/etc/apt/sources.list.d/docker.sources")
    if source.exists():
        raise ValueError("Existing Docker repository configuration requires inspection")
    atomic_write(source, f"Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: {os_release['VERSION_CODENAME']}\nComponents: stable\nArchitectures: {architecture}\nSigned-By: /etc/apt/keyrings/docker.asc\n", 0o644)
    execute(["apt-get", "update"])
    execute(["apt-get", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"])
    execute(["systemctl", "enable", "--now", "docker"])


def extract_release(archive, destination):
    with tarfile.open(archive, "r:gz") as bundle:
        total, seen = 0, set()
        for entry in bundle:
            relative = PurePosixPath(entry.name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in entry.name or not entry.isfile() or entry.name in seen:
                raise ValueError("Unsafe release archive")
            if any(p in {"prompt", ".git", "node_modules", ".venv", ".data"} or p.startswith(".env") or p.endswith(".local.json") for p in relative.parts):
                raise ValueError("Forbidden release entry")
            total += entry.size
            if total > 256 * 1024 * 1024 or len(seen) > 10000:
                raise ValueError("Release exceeds limits")
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Archive escaped release directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(entry) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, 64 * 1024)
            os.chmod(target, 0o644)
            seen.add(entry.name)


def deploy(payload, archive, images=None, initial_admins=None):
    import fcntl  # Ubuntu only; packaging/configuration tests also run on Windows.
    if os.geteuid() != 0:
        raise PermissionError("Root or sudo is required")
    raw = PurePosixPath(payload["app_dir"])
    if not raw.is_absolute() or len(raw.parts) < 3 or ".." in raw.parts:
        raise ValueError("Invalid dedicated application directory")
    base = Path(raw)
    if base.is_symlink() or base.resolve() != base:
        raise ValueError("Application directory must not contain symlinks")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (base / ".deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        shared, releases = base / "shared", base / "releases"
        shared.mkdir(exist_ok=True, mode=0o700)
        releases.mkdir(exist_ok=True, mode=0o700)
        state_path = shared / "settings.json"
        values = json.loads(state_path.read_text()) if state_path.exists() else {}
        incoming = payload["environment"]
        if values and values["COMPOSE_PROJECT_NAME"] != incoming["COMPOSE_PROJECT_NAME"]:
            raise ValueError("Changing project name would select different data volumes")
        values.update(incoming)
        values.setdefault("POSTGRES_PASSWORD", secrets.token_hex(32))
        values.setdefault("COOKIE_SECRET", secrets.token_hex(32))
        values.setdefault("POSTGRES_DB", "lab")
        values.setdefault("POSTGRES_USER", "lab")
        atomic_write(state_path, json.dumps(values, ensure_ascii=False, indent=2))
        atomic_write(shared / "app.env", dotenv(values))
        stage("docker-prerequisites")
        install_docker()
        release_id = payload.get("release_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + secrets.token_hex(4)
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", release_id):
            raise ValueError("Invalid release identifier")
        release = releases / release_id
        release.mkdir(mode=0o700)
        stage("extract-release")
        extract_release(archive, release)
        # Environment snapshot restores both URL/config and code on a manual rollback.
        atomic_write(release / "release.env", dotenv(values | {"RELEASE_ID": release_id}))
        compose = ["docker", "compose", "--project-directory", str(release), "--env-file", str(release / "release.env"), "-p", values["COMPOSE_PROJECT_NAME"], "-f", str(release / "infra/compose/compose.yaml")]
        if values.get("HTTP_TEST_MODE") != "true":
            cert_dir = Path(values.get("TLS_CERT_DIR", ""))
            if not all((cert_dir / name).is_file() for name in ("fullchain.pem", "privkey.pem")):
                raise ValueError("HTTPS certificate files are missing")
            compose += ["-f", str(release / "infra/compose/https.yaml")]
        stage("compose-config")
        execute(compose + ["config", "--quiet"], release)
        if payload.get("build_mode") == "local":
            if images is None:
                raise ValueError("Missing locally built images")
            stage("load-images")
            execute(["docker", "image", "load", "--input", str(images)], release)
        else:
            stage("build")
            execute(compose + ["build", "api", "frontend", "admin"], release)
        stage("database-health")
        execute(compose + ["up", "-d", "--wait", "--wait-timeout", "120", "db"], release)
        stage("migrations")
        execute(compose + ["run", "--rm", "--no-deps", "migrate"], release)
        stage("application-health")
        execute(compose + ["up", "-d", "--no-deps", "--wait", "--wait-timeout", "180", "api", "frontend", "admin", "proxy"], release)
        if initial_admins:
            stage("initial-admins")
            execute(compose + ["exec", "-T", "api", "python", "-m", "app.admin_bootstrap"], release, input_data=json.dumps(initial_admins))
        stage("orphan-cleanup")
        execute(compose + ["exec", "-T", "api", "python", "-m", "app.cleanup"], release)
        current = base / "current"
        if current.is_symlink():
            previous = base / ("previous.tmp-" + secrets.token_hex(4))
            previous.symlink_to(current.resolve())
            os.replace(previous, base / "previous")
        elif current.exists():
            raise ValueError("current exists and is not a managed symlink")
        temporary = base / ("current.tmp-" + secrets.token_hex(4))
        temporary.symlink_to(release)
        os.replace(temporary, current)
        stage("ready")


if __name__ == "__main__":
    os.umask(0o077)
    try:
        accounts = json.loads(sys.stdin.read(16384) or "[]")
        deploy(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None, accounts)
    except Exception:
        stage("failed; previous releases and all data volumes retained")
        raise SystemExit(1)
