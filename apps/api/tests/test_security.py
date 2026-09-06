import pytest

from app.config import Settings
from app.security import RateLimiter, client_ip, cookie_hash, new_cookie


def test_cookie_signature_and_expiry():
    secret = "s" * 32
    token = new_cookie(secret, now=100)
    assert cookie_hash(token, secret, 100, now=199)
    assert cookie_hash(token, secret, 100, now=200) is None
    assert cookie_hash(token, secret, 100, now=99) is None
    assert cookie_hash(token, "x" * 32, 100, now=110) is None
    assert cookie_hash("not-a-token", secret, 100) is None


def test_proxy_boundary_and_rate_reset():
    assert client_ip("1.2.3.4", "8.8.8.8", "172.30.80.0/24") == "1.2.3.4"
    assert client_ip("172.30.80.2", "8.8.8.8", "172.30.80.0/24") == "8.8.8.8"
    assert client_ip("172.30.80.2", "8.8.8.8,1.2.3.4", "172.30.80.0/24") == "172.30.80.2"
    limiter = RateLimiter(2, 10, "secret")
    assert limiter.check("one", 0) == limiter.check("one", 1) == 0
    assert limiter.check("one", 2) > 0
    assert limiter.check("two", 2) == 0
    assert limiter.check("one", 10) == 0


def test_http_requires_explicit_mode(tmp_path):
    with pytest.raises(ValueError):
        Settings("postgresql://unused", "s" * 32, tmp_path, "http://example.org")
    with pytest.raises(ValueError):
        Settings("postgresql://unused", "s" * 32, tmp_path, "https://example.org", True)
