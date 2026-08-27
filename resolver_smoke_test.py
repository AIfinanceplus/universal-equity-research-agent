import os

# The resolver module constructs ChatOpenAI clients at import time.
# This smoke test never sends a network request, so a dummy key is enough
# to exercise the pure resolver guard helpers in CI.
os.environ.setdefault(
    "OPENAI_API_KEY",
    "test-key-not-used",
)

from agent.resolver import (
    _damerau_levenshtein,
    _validate_resolved_result,
)
from agent.schemas import (
    ResolvedSecurity,
    SecurityCandidate,
)


def candidate(company: str, ticker: str) -> SecurityCandidate:
    return SecurityCandidate(
        company_name=company,
        ticker=ticker,
        exchange="NASDAQ",
        country="United States",
        currency="USD",
        share_class="Common Stock",
        notes="Nearby verified ticker.",
    )


def main():
    assert _damerau_levenshtein("CLAM", "CALM") == 1
    assert _damerau_levenshtein("CLAM", "CLAR") == 1

    # Natural-language company/brand input may map to a different ticker.
    spacex = ResolvedSecurity(
        status="resolved",
        input_kind="brand",
        listing_status="listed",
        company_name="Space Exploration Technologies Corp.",
        ticker="SPCX",
        exchange="NASDAQ",
        country="United States",
        currency="USD",
        share_class="Class A Common Stock",
        confidence=0.99,
        candidates=[],
        notes="SpaceX is the verified company brand.",
    )

    resolved_spacex = _validate_resolved_result(
        "spacex",
        spacex,
        [candidate("Space Exploration Technologies Corp.", "SPCX")],
        explicit_ticker=False,
    )

    assert resolved_spacex.status == "resolved"
    assert resolved_spacex.ticker == "SPCX"

    tesla = ResolvedSecurity(
        status="resolved",
        input_kind="company_name",
        listing_status="listed",
        company_name="Tesla, Inc.",
        ticker="TSLA",
        exchange="NASDAQ",
        country="United States",
        currency="USD",
        share_class="Common Stock",
        confidence=0.99,
        candidates=[],
        notes="Tesla company-name input.",
    )

    resolved_tesla = _validate_resolved_result(
        "tesla",
        tesla,
        [],
        explicit_ticker=False,
    )

    assert resolved_tesla.status == "resolved"
    assert resolved_tesla.ticker == "TSLA"

    # A genuinely mistyped ticker with multiple nearby symbols must remain ambiguous.
    nearby = [
        candidate("Cal-Maine Foods, Inc.", "CALM"),
        candidate("Clarus Corporation", "CLAR"),
    ]

    typo_result = ResolvedSecurity(
        status="resolved",
        input_kind="ticker_typo",
        listing_status="listed",
        company_name="Cal-Maine Foods, Inc.",
        ticker="CALM",
        exchange="NASDAQ",
        country="United States",
        currency="USD",
        share_class="Common Stock",
        confidence=0.95,
        candidates=[],
        notes="Likely ticker typo.",
    )

    guarded_typo = _validate_resolved_result(
        "CLAM",
        typo_result,
        nearby,
        explicit_ticker=False,
    )

    assert guarded_typo.status == "ambiguous"
    assert guarded_typo.ticker == ""
    assert {c.ticker for c in guarded_typo.candidates} >= {"CALM", "CLAR"}

    # Exact verified ticker input remains strict and cannot silently switch securities.
    exact_aapl = ResolvedSecurity(
        status="resolved",
        input_kind="ticker",
        listing_status="listed",
        company_name="Apple Inc.",
        ticker="AAPL",
        exchange="NASDAQ",
        country="United States",
        currency="USD",
        share_class="Common Stock",
        confidence=1.0,
        candidates=[],
        notes="Exact ticker.",
    )

    exact = _validate_resolved_result(
        "aapl",
        exact_aapl,
        [],
        explicit_ticker=True,
    )

    assert exact.status == "resolved"
    assert exact.ticker == "AAPL"

    wrong_switch = exact_aapl.model_copy(
        update={
            "ticker": "MSFT",
            "company_name": "Microsoft Corporation",
        }
    )

    blocked = _validate_resolved_result(
        "AAPL",
        wrong_switch,
        [],
        explicit_ticker=True,
    )

    assert blocked.status == "ambiguous"

    print(
        "PASS: company/brand names auto-resolve, exact tickers stay strict, and true typo ambiguity is preserved."
    )


if __name__ == "__main__":
    main()
