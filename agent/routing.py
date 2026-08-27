from __future__ import annotations

from typing import Literal

RouteName = Literal[
    "retry_fundamentals",
    "retry_market_data",
    "retry_competition",
    "retry_risk",
    "assumption_builder",
    "success_final",
    "insufficient_final",
]

DEFAULT_RETRY_LIMITS = {
    "market_data": 2,
    "financial_data": 2,
    "valuation_assumption": 1,
    "competition": 1,
    "risk": 1,
    "math": 0,
}

PRIORITY = [
    "math",
    "market_data",
    "financial_data",
    "valuation_assumption",
    "competition",
    "risk",
]

ROUTE_MAP = {
    "market_data": "retry_market_data",
    "financial_data": "retry_fundamentals",
    "valuation_assumption": "assumption_builder",
    "competition": "retry_competition",
    "risk": "retry_risk",
}


def decide_route_after_critic(
    state: dict,
    *,
    max_research_attempts: int,
    retry_limits: dict[str, int] | None = None,
) -> RouteName:
    """Pure deterministic circuit breaker for the critique loop."""

    actionable = [
        issue
        for issue in state.get(
            "research_issues",
            [],
        )
        if issue.get(
            "severity"
        )
        in {
            "blocker",
            "major",
        }
    ]

    if not actionable:
        return "success_final"

    if int(
        state.get(
            "revision_count",
            0,
        )
    ) >= max_research_attempts:
        return "insufficient_final"

    if int(
        state.get(
            "stagnant_revision_count",
            0,
        )
    ) >= 2:
        return "insufficient_final"

    limits = dict(
        DEFAULT_RETRY_LIMITS
    )

    if retry_limits:
        limits.update(
            retry_limits
        )

    issue_attempts = state.get(
        "issue_attempts",
        {},
    )

    for issue_type in PRIORITY:
        if not any(
            issue.get(
                "type"
            )
            ==
            issue_type
            for issue in actionable
        ):
            continue

        if issue_type == "math":
            return "insufficient_final"

        attempts = int(
            issue_attempts.get(
                issue_type,
                0,
            )
        )

        limit = int(
            limits.get(
                issue_type,
                0,
            )
        )

        if attempts > limit:
            return "insufficient_final"

        destination = ROUTE_MAP.get(
            issue_type
        )

        if destination:
            return destination

    return "insufficient_final"
