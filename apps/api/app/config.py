import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import URL


@dataclass(frozen=True)
class Settings:
    database_url: str | URL
    cookie_secret: str
    storage_root: Path
    public_url: str = "https://localhost"
    http_test_mode: bool = False
    cookie_days: int = 365
    rate_limit: int = 10
    rate_window: int = 600
    trusted_proxy_cidrs: str = ""
    telegram_token: str = ""
    telegram_chat: str = ""
    admin_origin: str = ""
    admin_session_hours: int = 12
    admin_login_limit: int = 6

    def __post_init__(self):
        url = urlsplit(self.public_url)
        if len(self.cookie_secret) < 32:
            raise ValueError("COOKIE_SECRET must contain at least 32 characters")
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("PUBLIC_URL must be an HTTP(S) origin")
        if (url.scheme == "http") != self.http_test_mode:
            raise ValueError("HTTP_TEST_MODE must be true only for an explicit HTTP test origin")
        if not 1 <= self.cookie_days <= 730 or self.rate_limit < 1 or self.rate_window < 1:
            raise ValueError("Invalid cookie or rate limit settings")
        admin = urlsplit(self.admin_origin or self.public_url)
        if admin.scheme != url.scheme or not admin.hostname or admin.username or admin.password or admin.query or admin.fragment or admin.path not in {"", "/"}:
            raise ValueError("ADMIN_ORIGIN must be a matching HTTP/HTTPS origin")
        if not 1 <= self.admin_session_hours <= 72 or not 1 <= self.admin_login_limit <= 100:
            raise ValueError("Invalid administrative session or rate settings")

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.environ.get("DATABASE_URL") or URL.create(
                "postgresql+psycopg", username=os.getenv("POSTGRES_USER", "lab"),
                password=os.environ["POSTGRES_PASSWORD"], host=os.getenv("POSTGRES_HOST", "db"),
                port=int(os.getenv("POSTGRES_PORT", "5432")), database=os.getenv("POSTGRES_DB", "lab"),
            ),
            cookie_secret=os.environ["COOKIE_SECRET"],
            storage_root=Path(os.getenv("STORAGE_ROOT", "/data/uploads")),
            public_url=os.getenv("PUBLIC_URL", "https://localhost").rstrip("/"),
            http_test_mode=os.getenv("HTTP_TEST_MODE", "false").lower() == "true",
            cookie_days=int(os.getenv("COOKIE_DAYS", "365")),
            rate_limit=int(os.getenv("RATE_LIMIT", "10")),
            rate_window=int(os.getenv("RATE_WINDOW", "600")),
            trusted_proxy_cidrs=os.getenv("TRUSTED_PROXY_CIDRS", ""),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat=os.getenv("TELEGRAM_CHAT_ID", ""),
            admin_origin=os.getenv("ADMIN_ORIGIN", "").rstrip("/"),
            admin_session_hours=int(os.getenv("ADMIN_SESSION_HOURS", "12")),
            admin_login_limit=int(os.getenv("ADMIN_LOGIN_LIMIT", "6")),
        )
