"""Best-effort notifications."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ledger.config import settings


class NotificationError(ValueError):
    """Raised when a notification cannot be delivered."""


def send_telegram_alert(message: str) -> bool:
    bot_token = settings.TELEGRAM_BOT_TOKEN.strip()
    chat_id = settings.TELEGRAM_CHAT_ID.strip()

    if not bot_token or not chat_id:
        raise NotificationError("Telegram is not configured.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise NotificationError(f"Telegram HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise NotificationError(f"Telegram network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise NotificationError("Telegram request timed out.") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise NotificationError(f"Telegram request failed: {exc}") from exc

    if not data.get("ok"):
        raise NotificationError(f"Telegram API error: {data}")

    return True
