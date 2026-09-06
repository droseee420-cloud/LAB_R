from sqlalchemy import create_engine

from .config import Settings
from .service import cleanup_orphans
from .storage import LocalStorage


def main():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    try:
        removed = cleanup_orphans(engine, LocalStorage(settings.storage_root))
        print(f"Removed {removed} orphan directories; accepted materials retained.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
