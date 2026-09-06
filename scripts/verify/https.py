"""Exercise TLS and Secure cookies on the existing local synthetic Compose stack."""
from scripts.local.stack import command as stack_command
import os
import json
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def compose(env, https=False):
    args = stack_command(https)
    subprocess.run(args + ["up", "-d", "--no-deps", "--force-recreate", "--wait", "--wait-timeout", "180", "api", "proxy"], env=env, check=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


original = os.environ.copy()
# This script always connects to loopback and keeps both published ports on loopback.
test_env = original | {"BIND_ADDRESS": "127.0.0.1", "HTTP_PORT": "8080", "HTTP_TEST_MODE": "false",
                       "PUBLIC_URL": "https://localhost", "ADMIN_ORIGIN": "https://localhost"}
with tempfile.TemporaryDirectory(prefix="lab-tls-") as directory:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
            .sign(key, hashes.SHA256()))
    cert_dir = Path(directory)
    os.chmod(cert_dir, 0o755)
    (cert_dir / "fullchain.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (cert_dir / "privkey.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    # Disposable synthetic certificate only; container UID 101 must read this fixture.
    os.chmod(cert_dir / "privkey.pem", 0o644)
    test_env["TLS_CERT_DIR"] = cert_dir.as_posix()
    try:
        compose(test_env, https=True)
        context = ssl.create_default_context(cafile=str(cert_dir / "fullchain.pem"))
        with urllib.request.urlopen("https://localhost/api/brief/session", context=context, timeout=10) as response:
            cookie = response.headers["Set-Cookie"]
            assert response.status == 200 and "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
            assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
        password = test_env.get("E2E_ADMIN_PASSWORD")
        assert password, "E2E_ADMIN_PASSWORD is required for the synthetic admin TLS check"
        login = urllib.request.Request(
            "https://localhost/api/admin/login",
            data=json.dumps({"username": "synthetic_admin_one", "password": password}).encode(),
            headers={"Content-Type": "application/json", "Origin": "https://localhost"},
        )
        with urllib.request.urlopen(login, context=context, timeout=30) as response:
            cookie = response.headers["Set-Cookie"].lower()
            assert response.status == 200
            assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
            assert "path=/api/admin" in cookie
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Frame-Options"] == "DENY"
        try:
            urllib.request.build_opener(NoRedirect).open("http://localhost:8080/", timeout=10)
        except urllib.error.HTTPError as response:
            assert response.code == 301 and response.headers["Location"] == "https://localhost/"
        else:
            raise AssertionError("HTTP did not redirect to HTTPS")
        print("HTTPS verified: trusted certificate, public/admin Secure cookies, admin no-store headers, HSTS and redirect.")
    finally:
        compose(original)
