import hashlib
import hmac
import ipaddress
import re
import secrets
import threading
import time
from collections import OrderedDict

COOKIE_NAME = "lab_browser"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_cookie(secret: str, now: int | None = None) -> str:
    body = f"{int(time.time()) if now is None else now}.{secrets.token_hex(32)}"
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def cookie_hash(token: str | None, secret: str, ttl: int, now: int | None = None) -> str | None:
    if not token or not re.fullmatch(r"[0-9]{1,12}\.[a-f0-9]{64}\.[a-f0-9]{64}", token):
        return None
    stamp, nonce, signature = token.split(".")
    body = f"{stamp}.{nonce}"
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    age = (int(time.time()) if now is None else now) - int(stamp)
    if not hmac.compare_digest(signature, expected) or not 0 <= age < ttl:
        return None
    return digest(token)


def client_ip(peer: str, forwarded: str | None, cidrs: str) -> str:
    try:
        address = ipaddress.ip_address(peer)
        if forwarded and any(address in ipaddress.ip_network(c.strip()) for c in cidrs.split(",") if c.strip()):
            return str(ipaddress.ip_address(forwarded))
        return str(address)
    except ValueError:
        return peer


class RateLimiter:
    """Bounded, transient counters for ONE API worker; Nginx also limits globally."""

    def __init__(self, limit: int, window: int, secret: str):
        self.limit, self.window, self.secret = limit, window, secret
        self.buckets: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self.lock = threading.Lock()

    def check(self, address: str, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        key = hmac.new(self.secret.encode(), address.encode(), hashlib.sha256).hexdigest()
        with self.lock:
            while self.buckets and next(iter(self.buckets.values()))[0] <= now:
                self.buckets.popitem(last=False)
            expiry, count = self.buckets.get(key, (now + self.window, 0))
            if expiry <= now:
                expiry, count = now + self.window, 0
            if count >= self.limit:
                return max(1, int(expiry - now) + 1)
            if key not in self.buckets and len(self.buckets) >= 10000:
                return self.window
            self.buckets[key] = (expiry, count + 1)
            return 0
