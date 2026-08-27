from __future__ import annotations

from agent.nodes import (
    market_data_node as legacy_web_market_data_node,
    merge_sources,
)
from agent.schemas import ResearchState
from agent.yfinance_data import fetch_yfinance_market_snapshot


def _has_market_retry(state: ResearchState) -> bool:
    attempts = state.get("issue_attempts", {})
    return int(attempts.get("market_data", 0) or 0) > 0


def market_data_node(state: ResearchState):
    """
    Market-data ownership policy:

    1. Yahoo Finance via yfinance first for quote / market cap / shares.
    2. Existing web-search + LLM extraction only if Yahoo is incomplete or fails.
    3. On a targeted market-data retry, use the independent web path instead
       of repeating the same Yahoo lookup.
    """

    print("\n>>> MARKET DATA NODE START (Yahoo primary; web fallback)")

    if not _has_market_retry(state):
        snapshot = fetch_yfinance_market_snapshot(state["ticker"])

        if snapshot.get("ok"):
            price = float(snapshot["price_usd"])
            cap = float(snapshot["market_cap_usd_b"])
            date_value = str(snapshot.get("as_of_date", ""))
            source_url = str(snapshot.get("source_url", ""))

            source = {
                "title": f"Yahoo Finance quote for {state['ticker']}",
                "url": source_url,
                "provider": "Yahoo Finance via yfinance",
                "source_quality": "secondary_non_official",
            }

            canonical = {
                "price_usd": price,
                "market_cap_usd_b": cap,
                "as_of_date": date_value,
                "as_of_time": snapshot.get("as_of_time"),
                "timezone": snapshot.get("timezone"),
                "provider": snapshot.get("provider"),
                "source_url": source_url,
                "status": "verified",
                "notes": snapshot.get("notes", ""),
                "market_cap_method": snapshot.get("market_cap_method", "provider_reported"),
                "source_quality": snapshot.get("source_quality", "secondary_non_official"),
                "currency": snapshot.get("currency", ""),
                "exchange": snapshot.get("exchange", ""),
                "yfinance_shares_outstanding": snapshot.get("shares_outstanding"),
            }

            report = (
                "Yahoo Finance market data via yfinance. "
                f"Ticker={state['ticker']}; Price=${price:.4f}; "
                f"Market Cap=${cap:.3f}B; As-of={date_value}; "
                f"Method={canonical['market_cap_method']}."
            )

            return {
                "market_report": report,
                "market_sources": merge_sources(
                    state.get("market_sources", []),
                    [source],
                ),
                "market_snapshot": canonical,
                "market_price": price,
                "market_cap": cap,
                "market_cap_date": date_value,
            }

        print(
            "Yahoo market data incomplete/unavailable; falling back to web research. "
            f"Reason={snapshot.get('error') or 'missing required fields'}"
        )
    else:
        print("Targeted market-data retry detected; using independent web fallback.")

    return legacy_web_market_data_node(state)
