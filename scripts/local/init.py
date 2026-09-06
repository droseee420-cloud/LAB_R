"""Generate only a new local Compose config. Never replaces an existing one."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[2]
target = root / ".env"
if target.exists():
    print(".env already exists; retained unchanged.")
else:
    template = (root / ".env.example").read_text(encoding="utf-8")
    template = template.replace("REPLACE_WITH_RANDOM_SECRET", secrets.token_hex(32))
    template = template.replace("REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS", secrets.token_hex(32))
    with target.open("x", encoding="utf-8", newline="\n") as output:
        output.write(template)
    print("Created local .env. Run docker compose up --build --wait.")
