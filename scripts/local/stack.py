from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def command(https=False):
    result = ["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "infra/compose/compose.yaml")]
    if https:
        result += ["-f", str(ROOT / "infra/compose/https.yaml")]
    return result
