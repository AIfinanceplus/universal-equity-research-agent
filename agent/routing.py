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


_COMPETITION_SCOPE_MARKERS = (
    "shipment",
    "shipments",
    "sell-through",
    "sell through",
    "unit",
    "units",
    "premium segment",
    "premium-segment",
    "installed base",
    "installed-base",
    "market leader",
    "market leadership",
    "market share",
    "smartphone revenue",
    "geographic scope",
)

_COMPETITION_DEFINITION_MARKERS = (
    "definition",
    "definitions",
    "reporting period",
    "reporting periods",
    "like-for-like",
    "reconcile",
    "reconciliation",
    "scope",
    "qualified",
    "source links",
    "publication dates",
)

_EXPLICIT_MODEL_LINKAGE_MARKERS = (
    "fcf growth",
    "free cash flow growth",
    "revenue growth assumption",
    "exit multiple",
    "discount rate",
    "valuation input",
    "valuation assumption",
    "scenario parameter",
    "model parameter",
    "cash flow forecast",
)


def is_nonblocking_competition_definition_gap(issue: dict) -> bool:
    """Return True for taxonomy/definition disputes that should remain caveats.

    Example: IDC and Omdia may use different shipment, sell-through, premium,
    revenue, geography, or installed-base definitions. That is useful context,
    but it should not by itself fail the entire research pipeline unless the
    disputed claim is explicitly used as a core valuation-model input.
    """

    if issue.get("type") != "competition":
        return False

    text = str(issue.get("request", "")).lower()

    has_scope_marker = any(
        marker in text
        for marker in _COMPETITION_SCOPE_MARKERS
    )

    has_definition_marker = any(
        marker in text
        for marker in _COMPETITION_DEFINITION_MARKERS
    )

    has_explicit_model_linkage = any(
        marker in text
        for marker in _EXPLICIT_MODEL_LINKAGE_MARKERS
    )

    return (
        has_scope_marker
        and has_definition_marker
        and not has_explicit_model_linkage
    )


def actionable_issues(state: dict) -> list[dict]:
    """Return only issues allowed to control graph routing."""

    return [
        issue
        for issue in state.get(
            "research_issues",
            [],
        )
        if issue.get("severity") in {
            "blocker",
            "major",
        }
        and not is_nonblocking_competition_definition_gap(
            issue
        )
    ]


def decide_route_after_critic(
    state: dict,
    *,
    max_research_attempts: int,
    retry_limits: dict[str, int] | None = None,
) -> RouteName:
    """Pure deterministic circuit breaker for the critique loop."""

    actionable = actionable_issues(
        state
    )

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
            issue.get("type") == issue_type
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
