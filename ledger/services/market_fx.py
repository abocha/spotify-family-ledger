import json
import time
import urllib.request
from typing import Optional

_CACHE: dict[str, float | None] = {"rate": None, "timestamp": 0.0}
_CACHE_TTL = 3600.0


def fetch_market_rate() -> Optional[float]:
    """Fetch the latest USD->RUB mid-market reference rate."""
    now = time.time()
    if now - float(_CACHE["timestamp"] or 0.0) < _CACHE_TTL and _CACHE["rate"] is not None:
        return _CACHE["rate"]

    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        # 3 second timeout so the UI never hangs for too long
        with urllib.request.urlopen(url, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                rate = data.get("rates", {}).get("RUB")
                _CACHE["rate"] = rate
                _CACHE["timestamp"] = now
                return rate
    except Exception:
        # Silently catch network errors, UI handles fallback
        pass

    return _CACHE["rate"]
