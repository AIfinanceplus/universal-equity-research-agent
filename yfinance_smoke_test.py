import os

os.environ.setdefault(
    "OPENAI_API_KEY",
    "test-key-not-used",
)

import pandas as pd

from agent.yfinance_data import normalize_yfinance_snapshot


def main():
    history = pd.DataFrame(
        {
            "Close": [249.5, 250.0],
        },
        index=pd.to_datetime(
            [
                "2026-08-25",
                "2026-08-26",
            ]
        ),
    )

    provider_cap = normalize_yfinance_snapshot(
        ticker="AAPL",
        fast_info={
            "last_price": 250.0,
            "market_cap": 3_750_000_000_000,
            "shares": 15_000_000_000,
            "currency": "USD",
            "exchange": "NMS",
            "timezone": "America/New_York",
        },
        history=history,
    )

    assert provider_cap["ok"] is True
    assert provider_cap["price_usd"] == 250.0
    assert provider_cap["market_cap_usd_b"] == 3750.0
    assert provider_cap["as_of_date"] == "2026-08-26"
    assert provider_cap["market_cap_method"] == "provider_reported"

    derived_cap = normalize_yfinance_snapshot(
        ticker="TEST",
        fast_info={
            "last_price": 100.0,
            "shares": 2_000_000_000,
            "currency": "USD",
        },
        history=history,
    )

    assert derived_cap["ok"] is True
    assert derived_cap["market_cap_usd_b"] == 200.0
    assert (
        derived_cap["market_cap_method"]
        == "derived: yfinance price * yfinance shares"
    )

    non_usd = normalize_yfinance_snapshot(
        ticker="TEST.L",
        fast_info={
            "last_price": 100.0,
            "market_cap": 200_000_000_000,
            "currency": "GBP",
        },
        history=history,
    )

    assert non_usd["ok"] is False
    assert non_usd["price_usd"] is None
    assert non_usd["market_cap_usd_b"] is None

    print(
        "PASS: yfinance adapter normalizes provider cap, derived cap, "
        "date, and non-USD safety without network access."
    )


if __name__ == "__main__":
    main()
