import json
import urllib.request
from typing import Optional
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_market_rate() -> Optional[float]:
    """
    Fetch the latest USD to RUB exchange rate from ExchangeRate-API.
    This uses the free, keyless v4 endpoint.
    Returns the rate as a float, or None if there was an error.
    """
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        # 3 second timeout so the UI never hangs for too long
        with urllib.request.urlopen(url, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("rates", {}).get("RUB")
    except Exception:
        # Silently catch network errors, UI handles fallback
        pass
    
    return None
