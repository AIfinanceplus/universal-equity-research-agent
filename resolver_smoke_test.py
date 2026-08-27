from agent.resolver import (
    _damerau_levenshtein,
    _validate_resolved_result,
)
from agent.schemas import (
    ResolvedSecurity,
    SecurityCandidate,
)


def main():
    assert _damerau_levenshtein(
        "CLAM",
        "CALM",
    ) == 1

    assert _damerau_levenshtein(
        "CLAM",
        "CLAR",
    ) == 1

    nearby = [
        SecurityCandidate(
            company_name="Cal-Maine Foods, Inc.",
            ticker="CALM",
            exchange="NASDAQ",
            country="United States",
            currency="USD",
            share_class="Common Stock",
            notes="Nearby verified ticker.",
        )
    ]

    model_result = ResolvedSecurity(
        status="resolved",
        company_name="Cal-Maine Foods, Inc.",
        ticker="CALM",
        exchange="NASDAQ",
        country="United States",
        currency="USD",
        share_class="Common Stock",
        confidence=0.95,
        candidates=[],
        notes="Likely intended ticker.",
    )

    guarded = _validate_resolved_result(
        "CLAM",
        model_result,
        nearby,
    )

    assert guarded.status == "ambiguous"
    assert guarded.ticker == ""
    assert any(
        candidate.ticker == "CALM"
        for candidate in guarded.candidates
    )

    exact = _validate_resolved_result(
        "CALM",
        model_result,
        nearby,
    )

    assert exact.status == "resolved"
    assert exact.ticker == "CALM"

    print(
        "PASS: mistyped tickers are suggested but never silently corrected."
    )


if __name__ == "__main__":
    main()
