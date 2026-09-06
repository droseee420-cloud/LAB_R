"""Account maintenance: passwords only from terminal/stdin, never argv or logs."""
import argparse
import getpass
import json
import sys

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from .admin_auth import manage
from .config import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "list", "disable", "enable", "reset-password", "cleanup-sessions"])
    parser.add_argument("username", nargs="?")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    password = None
    if args.action in {"create", "reset-password"}:
        password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Password: ")
    engine = create_engine(Settings.from_env().database_url)
    try:
        result = manage(engine, args.action, args.username, password)
        print(json.dumps(result) if result is not None else "Account updated.")
    except (ValueError, SQLAlchemyError):
        print("Account operation failed. Check action, unique username and password length (12–1024).", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
