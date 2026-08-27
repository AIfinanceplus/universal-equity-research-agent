import os

os.environ.setdefault("OPENAI_API_KEY", "test-key-for-offline-smoke")

from agent import yahoo_resolver


def main():
    original = yahoo_resolver._search_quotes

    try:
        yahoo_resolver._search_quotes = lambda query: [
            {
                "symbol": "SPCX",
                "longname": "Space Exploration Technologies Corp.",
                "exchange": "NMS",
                "quoteType": "EQUITY",
                "currency": "USD",
                "region": "US",
            }
        ]

        result = yahoo_resolver.resolve_security("spacex")
        assert result.status == "resolved"
        assert result.ticker == "SPCX"
        assert result.company_name == "Space Exploration Technologies Corp."

        result = yahoo_resolver.resolve_security("SPCX")
        assert result.status == "resolved"
        assert result.input_kind == "ticker"
        assert result.ticker == "SPCX"

        print("PASS: Yahoo resolver accepts natural company names and exact tickers without SEC mapping.")
    finally:
        yahoo_resolver._search_quotes = original


if __name__ == "__main__":
    main()
