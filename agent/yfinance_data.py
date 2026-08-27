from __future__ import annotations

from typing import Any

import yfinance as yf


YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{ticker}/"


def _read_value(container: Any, key: str):
    if container is None:
        return None

    try:
        value = getattr(container, key)
        if value is not None:
            return value
    except Exception:
        pass

    try:
        return container[key]
    except Exception:
        return None


def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number <= 0:
        return None

    return number


def _history_date(history) -> str:
    try:
        if history is None or history.empty:
            return ""

        value = history.index[-1]
        if hasattr(value, "date"):
            return value.date().isoformat()

        text = str(value)
        return text[:10] if len(text) >= 10 else ""
    except Exception:
        return ""


def _history_close(history):
    try:
        if history is None or history.empty or "Close" not in history.columns:
            return None
        return _positive_float(history["Close"].iloc[-1])
    except Exception:
        return None


def normalize_yfinance_snapshot(*, ticker: str, fast_info: Any, history: Any) -> dict:
    symbol = ticker.strip().upper()

    price = _positive_float(_read_value(fast_info, "last_price"))
    if price is None:
        price = _history_close(history)

    market_cap_raw = _positive_float(_read_value(fast_info, "market_cap"))
    shares = _positive_float(_read_value(fast_info, "shares"))

    market_cap_usd_b = (
        market_cap_raw / 1_000_000_000
        if market_cap_raw is not None
        else None
    )

    market_cap_method = "provider_reported"
    if market_cap_usd_b is None and price is not None and shares is not None:
        market_cap_usd_b = price * shares / 1_000_000_000
        market_cap_method = "derived: Yahoo price * Yahoo shares"

    currency = str(_read_value(fast_info, "currency") or "").upper()
    exchange = str(_read_value(fast_info, "exchange") or "")
    timezone_name = str(_read_value(fast_info, "timezone") or "")
    as_of_date = _history_date(history)

    usd_compatible = currency in {"", "USD"}
    complete = bool(
        usd_compatible
        and price is not None
        and market_cap_usd_b is not None
        and as_of_date
    )

    return {
        "ok": complete,
        "ticker": symbol,
        "price_usd": price if usd_compatible else None,
        "market_cap_usd_b": market_cap_usd_b if usd_compatible else None,
        "shares_outstanding": shares,
        "currency": currency,
        "exchange": exchange,
        "as_of_date": as_of_date,
        "as_of_time": None,
        "timezone": timezone_name or None,
        "provider": "Yahoo Finance via yfinance",
        "source_url": YAHOO_QUOTE_URL.format(ticker=symbol),
        "source_quality": "secondary_non_official",
        "status": "verified" if complete else "unavailable",
        "market_cap_method": market_cap_method,
        "notes": "Yahoo Finance market data accessed via yfinance.",
    }


def fetch_yfinance_market_snapshot(ticker: str) -> dict:
    symbol = ticker.strip().upper()

    if not symbol:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "Empty ticker.",
        }

    try:
        security = yf.Ticker(symbol)
        fast_info = security.fast_info
        history = security.history(
            period="5d",
            interval="1d",
            auto_adjust=False,
            actions=False,
        )

        return normalize_yfinance_snapshot(
            ticker=symbol,
            fast_info=fast_info,
            history=history,
        )

    except Exception as exc:
        return {
            "ok": False,
            "ticker": symbol,
            "status": "unavailable",
            "provider": "Yahoo Finance via yfinance",
            "source_url": YAHOO_QUOTE_URL.format(ticker=symbol),
            "source_quality": "secondary_non_official",
            "error": f"{exc.__class__.__name__}: {exc}",
            "notes": "Yahoo market lookup failed; caller may use independent web fallback.",
        }
