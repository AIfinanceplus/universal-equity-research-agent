from agent.routing import (
    actionable_issues,
    decide_route_after_critic,
    is_nonblocking_competition_definition_gap,
)


def base_state():
    return {
        "research_issues": [],
        "revision_count": 0,
        "issue_attempts": {
            "financial_data": 0,
            "market_data": 0,
            "valuation_assumption": 0,
            "competition": 0,
            "risk": 0,
            "math": 0,
        },
        "stagnant_revision_count": 0,
    }


def route(state):
    return decide_route_after_critic(
        state,
        max_research_attempts=3,
    )


def main():
    state = base_state()
    assert route(state) == "success_final"
    print("PASS: no actionable issues routes to success_final.")

    state = base_state()
    state["research_issues"] = [
        {
            "type": "risk",
            "severity": "major",
            "request": "Quantify downside risk.",
        }
    ]
    state["revision_count"] = 1
    state["issue_attempts"]["risk"] = 1
    assert route(state) == "retry_risk"
    state["revision_count"] = 2
    state["issue_attempts"]["risk"] = 2
    assert route(state) == "insufficient_final"
    print("PASS: risk gets one retry and then exits.")

    state = base_state()
    state["research_issues"] = [
        {
            "type": "market_data",
            "severity": "blocker",
            "request": "Need market source.",
        }
    ]
    state["revision_count"] = 3
    assert route(state) == "insufficient_final"
    print("PASS: global revision limit exits.")

    state = base_state()
    state["research_issues"] = [
        {
            "type": "valuation_assumption",
            "severity": "major",
            "request": "Same unresolved assumption.",
        }
    ]
    state["revision_count"] = 2
    state["issue_attempts"]["valuation_assumption"] = 1
    state["stagnant_revision_count"] = 2
    assert route(state) == "insufficient_final"
    print("PASS: stagnant issue set exits.")

    state = base_state()
    state["research_issues"] = [
        {
            "type": "math",
            "severity": "blocker",
            "request": "Math mismatch.",
        }
    ]
    state["revision_count"] = 1
    assert route(state) == "insufficient_final"
    print("PASS: math failure never loops back.")

    apple_definition_issue = {
        "type": "competition",
        "severity": "major",
        "request": (
            "Reconcile the IDC and Omdia market-leadership claim. "
            "Document reporting periods, shipment versus sell-through definitions, "
            "geographic scope, premium-segment units, smartphone revenue and installed base."
        ),
    }

    assert is_nonblocking_competition_definition_gap(
        apple_definition_issue
    ) is True

    state = base_state()
    state["research_issues"] = [
        apple_definition_issue
    ]

    assert actionable_issues(state) == []
    assert route(state) == "success_final"
    print(
        "PASS: IDC/Omdia definition-only competition gap is a caveat, not a pipeline blocker."
    )

    model_linked_issue = dict(
        apple_definition_issue
    )
    model_linked_issue["request"] += (
        " This claim directly determines the revenue growth assumption in the valuation model."
    )

    state = base_state()
    state["research_issues"] = [
        model_linked_issue
    ]

    assert is_nonblocking_competition_definition_gap(
        model_linked_issue
    ) is False
    assert route(state) == "retry_competition"
    print(
        "PASS: definition gap remains actionable when explicitly linked to a core valuation input."
    )


if __name__ == "__main__":
    main()
