"""Allowlisted release packaging. Never follows links or relies on Git ignore."""
import tarfile
from pathlib import Path

ROOT_FILES = {"package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", ".dockerignore", "README.md"}
ROOT_DIRS = {"apps", "infra", "scripts", "docs"}
BLOCKED = {"node_modules", "__pycache__", ".venv", "prompt", ".git", ".tools", ".data",
           "tests", "test-results", "playwright-report", "known_hosts", "deploy.local.json"}


def allowed(path: Path) -> bool:
    if any(p.lower() in BLOCKED or (p.startswith(".") and p != ".dockerignore") for p in path.parts):
        return False
    if path.name.lower().endswith((".pem", ".key", ".pfx", ".pyc", ".log", ".local.json")):
        return False
    return (len(path.parts) == 1 and path.name in ROOT_FILES) or (len(path.parts) > 1 and path.parts[0] in ROOT_DIRS)


def package_release(root: Path, output: Path) -> list[str]:
    root = root.resolve()
    entries = []
    # Walk only approved top-level directories. Do not traverse secret/data trees.
    candidates = [root / name for name in ROOT_FILES]
    for name in ROOT_DIRS:
        directory = root / name
        if directory.is_symlink():
            raise ValueError("Release directory cannot be a symlink")
        if directory.exists():
            candidates.extend(directory.rglob("*"))
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for file in sorted(candidates):
            relative = file.relative_to(root)
            if not allowed(relative):
                continue
            if file.is_symlink():
                raise ValueError("Release files cannot be symlinks")
            if not file.is_file():
                continue
            if not file.resolve().is_relative_to(root):
                raise ValueError("Release file escaped project root")
            info = archive.gettarinfo(str(file), arcname=relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            with file.open("rb") as data:
                archive.addfile(info, data)
            entries.append(relative.as_posix())
    if "infra/compose/compose.yaml" not in entries or "package.json" not in entries:
        raise ValueError("Missing release inputs")
    return entries
