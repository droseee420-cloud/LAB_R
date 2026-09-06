import logging

import httpx

logger = logging.getLogger("lab")


def notify(settings, lead_id: str, data: dict, file_count: int, transport=None):
    if not settings.telegram_token or not settings.telegram_chat:
        return
    message = "\n".join([
        "New Refraction LAB brief", f"ID: {lead_id}",
        f"{data['contact_method']}: {data['contact']}",
        f"Name: {data['name'] or '—'}", f"Language: {data['language']}",
        f"Files: {file_count}", "", data["message"][:2500],
    ])
    try:
        # No redirects, retries, parse_mode or document uploads. Never log the URL.
        with httpx.Client(timeout=httpx.Timeout(5, connect=2), transport=transport, trust_env=False) as client:
            response = client.post(f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                                   json={"chat_id": settings.telegram_chat, "text": message, "link_preview_options": {"is_disabled": True}})
            response.raise_for_status()
            if response.json().get("ok") is not True:
                raise ValueError("Telegram rejected notification")
    except Exception:
        logger.warning("telegram_failed lead=%s", lead_id)
