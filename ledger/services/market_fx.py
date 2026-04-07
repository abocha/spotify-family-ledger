"""FX fetchers using CurrencyBeacon."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal
from typing import Any

from ledger.config import settings

_HISTORICAL_CACHE: dict[str, Decimal] = {}
_LATEST_CACHE: dict[str, float | None] = {"rate": None, "timestamp": 0.0}
_LATEST_CACHE_TTL = 3600.0


class FxLookupError(ValueError):
    """Raised when the FX provider returns a usable error message."""


def _get_api_key() -> str:
    """Return CurrencyBeacon API key.

    Prefers CURRENCYBEACON_API_KEY, but falls back to EXCHANGERATE_API_KEY so the
    app can keep working during migration if you reuse the old env var name.
    """
    return (
        getattr(settings, "CURRENCYBEACON_API_KEY", None)
        or getattr(settings, "EXCHANGERATE_API_KEY", None)
        or ""
    ).strip()


def _request_json(path: str, params: dict[str, str], timeout: float) -> dict[str, Any]:
    """Perform a GET request to CurrencyBeacon and return parsed JSON."""
    api_key = _get_api_key()
    if not api_key:
        raise FxLookupError(
            "CurrencyBeacon API key is missing. Set CURRENCYBEACON_API_KEY "
            "(or temporarily reuse EXCHANGERATE_API_KEY)."
        )

    query = urllib.parse.urlencode({**params, "api_key": api_key})
    url = f"https://api.currencybeacon.com/v1/{path}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "spotify-family-ledger/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise FxLookupError(f"CurrencyBeacon HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise FxLookupError(f"CurrencyBeacon network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FxLookupError("CurrencyBeacon request timed out.") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise FxLookupError(f"CurrencyBeacon request failed: {exc}") from exc

    meta = payload.get("meta") or {}
    response_code = meta.get("code")
    if response_code and int(response_code) >= 400:
        error_message = payload.get("error") or payload.get("message") or "Unknown API error."
        raise FxLookupError(f"CurrencyBeacon error {response_code}: {error_message}")

    if "response" not in payload:
        raise FxLookupError("CurrencyBeacon returned an unexpected payload.")

    return payload


def fetch_historical_fx_rate(rate_date: date) -> Decimal | None:
    """Fetch USD->RUB for an exact historical date via CurrencyBeacon.

    Returns Decimal when available, otherwise raises FxLookupError for actionable
    provider/network/config problems and returns None only when the payload is valid
    but RUB is missing.
    """
    cache_key = rate_date.isoformat()
    cached = _HISTORICAL_CACHE.get(cache_key)
    if cached is not None:
        return cached

    payload = _request_json(
        "historical",
        {
            # CurrencyBeacon docs state latest/historical default base to USD.
            # We omit `base=USD` to stay compatible with plans where base switching
            # is restricted, while still getting the USD->RUB rate we need.
            "date": cache_key,
            "symbols": "RUB",
        },
        timeout=5.0,
    )

    rate = ((payload.get("response") or {}).get("rates") or {}).get("RUB")
    if rate is None:
        return None

    decimal_rate = Decimal(str(rate))
    _HISTORICAL_CACHE[cache_key] = decimal_rate
    return decimal_rate


def fetch_market_rate() -> float | None:
    """Fetch latest USD->RUB rate using CurrencyBeacon latest endpoint.

    Caches the result for 1 hour to stay well within free-tier limits. Returns the
    last known cached rate on transient lookup failures.
    """
    now = time.time()
    cached_rate = _LATEST_CACHE["rate"]
    cached_ts = float(_LATEST_CACHE["timestamp"] or 0.0)
    if now - cached_ts < _LATEST_CACHE_TTL and cached_rate is not None:
        return cached_rate

    try:
        payload = _request_json(
            "latest",
            {
                # See note in fetch_historical_fx_rate(): we rely on the documented
                # default USD base and only request RUB explicitly.
                "symbols": "RUB",
            },
            timeout=3.0,
        )
        rate = ((payload.get("response") or {}).get("rates") or {}).get("RUB")
        if rate is None:
            return cached_rate

        float_rate = float(rate)
        _LATEST_CACHE["rate"] = float_rate
        _LATEST_CACHE["timestamp"] = now
        return float_rate
    except FxLookupError:
        return cached_rate
