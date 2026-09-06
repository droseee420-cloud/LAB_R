import re
from urllib.parse import urlsplit

from starlette.datastructures import FormData, UploadFile

CONSENT_VERSION = "brief-en-v1"
CONSENT_TEXT = "I agree that Refraction LAB may use the submitted information to review and reply to this request."
MAX_FILES = 6
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 30 * 1024 * 1024
MAX_BODY_SIZE = 31 * 1024 * 1024


class BriefError(Exception):
    def __init__(self, message: str, code: str = "validation", status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


def field(form: FormData, name: str, limit: int, default: str = "") -> str:
    items = form.getlist(name)
    if len(items) > 1 or (items and not isinstance(items[0], str)):
        raise BriefError(f"Invalid {name}.")
    value = items[0] if items else default
    if len(value) > limit:
        raise BriefError(f"{name} is too long (maximum {limit} characters).")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise BriefError(f"Invalid {name}.")
    return value.strip()


def validate_form(form: FormData) -> dict:
    message = field(form, "message", 5000)
    if len(message) < 12:
        raise BriefError("Tell us a little more about the situation (at least 12 characters).")
    method = field(form, "contactMethod", 8)
    contact = field(form, "contact", 180)
    if method == "telegram":
        normalized = contact.removeprefix("@").lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{4,31}", normalized):
            raise BriefError("Add a valid Telegram username (5–32 letters, digits or underscores).")
    elif method == "email":
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", contact):
            raise BriefError("Add a valid email address.")
        local, domain = contact.rsplit("@", 1)
        if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local or any(len(p) > 63 for p in domain.split(".")):
            raise BriefError("Add a valid email address.")
        normalized = contact.lower()
    else:
        raise BriefError("Choose Telegram or email.")
    if field(form, "consent", 5) != "true":
        raise BriefError("Consent is required so we can review and reply.")
    if field(form, "consentVersion", 40) != CONSENT_VERSION:
        raise BriefError("Please reload the form to review the current consent text.")
    language = field(form, "language", 2, "en")
    if language not in {"en", "es", "ca"}:
        raise BriefError("Invalid form language.")
    link = field(form, "productLink", 1000)
    if link:
        try:
            url = urlsplit(link)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or any(c.isspace() for c in link):
                raise ValueError()
            _ = url.port
        except ValueError:
            raise BriefError("Use a valid http:// or https:// product link.") from None
    no_product = field(form, "noProduct", 5, "false")
    if no_product not in {"true", "false"}:
        raise BriefError("Invalid noProduct.")
    for key, value in form.multi_items():
        if isinstance(value, UploadFile) and key != "files":
            raise BriefError("Unexpected attachment field.")
    return dict(message=message, contact_method=method, contact=contact,
                contact_normalized=normalized, name=field(form, "name", 120) or None,
                product_link=link or None, no_product=no_product == "true", language=language,
                consent=True, consent_version=CONSENT_VERSION)
