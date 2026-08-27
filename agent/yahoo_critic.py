from __future__ import annotations

from agent.config import llm
from agent.schemas import InvestmentCritique, ResearchState


critic_llm = llm.with_structured_output(
    InvestmentCritique,
    method="json_schema",
)


def _append_unique(issues: list[dict], issue: dict):
    key = (issue["type"], issue["severity"], issue["request"])
    if key not in {(i["type"], i["severity"], i["request"]) for i in issues}:
        issues.append(issue)


def critic_node(state: ResearchState):
    print("\n=== INVESTMENT CRITIC (YAHOO-ONLY) ===")
    deterministic = state["deterministic_verification"]

    result = critic_llm.invoke(f"""
You are an independent investment-committee critic for {state['company']} ({state['ticker']}).
Financial snapshot:\n{state['financial_snapshot']}
Market snapshot:\n{state['market_snapshot']}
Assumptions:\n{state['valuation_assumptions']}
Valuation:\n{state['valuation_summary']}
Python verification:\n{deterministic}
Competition:\n{state['competition_report']}
Risk:\n{state['risk_report']}

HARD RULES:
- Python verification is authoritative for data presence/date alignment/math/scenario structure.
- Financial and market data are intentionally sourced from Yahoo Finance via yfinance in this research configuration.
- If the Yahoo financial snapshot is valid and Python reports no financial-data failure, do not invent a blocker/major merely because another provider was not used.
- Latest TTM financials plus current market price is normal; exact same-day financials are not required.
- If math_failures=[], do not create an actionable math issue.
- This intentionally uses a simplified 5-year FCF scenario model; do not require WACC/FCFF/FCFE, standard DCF, EPS model, SOTP or full comps as blockers.
- More risk/competition quantification alone is normally minor.
- Assumptions are judgmental by design; major only if rationale/evidence/order is absent, contradictory or clearly implausible without explanation.
Return only genuine unresolved issues using allowed typed issue categories.
""")

    issues: list[dict] = []
    for failure in deterministic.get("data_failures", []):
        issue_type = "market_data" if "market" in failure.lower() or "source url" in failure.lower() else "financial_data"
        _append_unique(issues, {"type": issue_type, "severity": "blocker", "request": failure})

    for failure in deterministic.get("math_failures", []):
        _append_unique(issues, {"type": "math", "severity": "blocker", "request": failure})

    for failure in deterministic.get("model_failures", []):
        _append_unique(issues, {"type": "valuation_assumption", "severity": "major", "request": failure})

    data_ok = not deterministic.get("data_failures")
    math_ok = not deterministic.get("math_failures")
    model_ok = not deterministic.get("model_failures")
    yahoo_financial_ok = (
        state.get("financial_snapshot", {}).get("provider") == "Yahoo Finance via yfinance"
        and state.get("financial_snapshot", {}).get("valid") is True
    )
    market_ok = (
        state.get("market_snapshot", {}).get("status") in {"verified", "derived_verified"}
        and bool(state.get("market_snapshot", {}).get("source_url"))
    )

    for raw in [item.model_dump() for item in result.issues]:
        issue = dict(raw)
        issue_type = issue["type"]
        severity = issue["severity"]
        request = issue["request"]

        if issue_type == "financial_data" and yahoo_financial_ok and data_ok and severity in {"blocker", "major"}:
            issue.update(
                severity="minor",
                request="可选的财务数据扩展：" + request,
            )

        if issue_type == "market_data" and market_ok and data_ok and severity in {"blocker", "major"}:
            issue.update(
                severity="minor",
                request="可选的市场数据扩展：" + request,
            )

        if issue_type == "math" and math_ok:
            issue.update(
                severity="minor",
                request="非阻断性的展示说明：" + request,
            )

        if (
            issue_type == "valuation_assumption"
            and model_ok
            and severity in {"blocker", "major"}
            and state.get("revision_count", 0) >= 1
        ):
            issue.update(
                severity="minor",
                request="剩余估值假设不确定性：" + request,
            )

        if issue_type in {"competition", "risk"} and severity == "major" and (
            "quant" in request.lower() or "sensitivity" in request.lower()
        ):
            issue["severity"] = "minor"

        _append_unique(issues, issue)

    actionable = [issue for issue in issues if issue["severity"] in {"blocker", "major"}]
    needs_revision = bool(actionable)
    revision_count = state.get("revision_count", 0) + (1 if needs_revision else 0)

    issue_attempts = dict(state.get("issue_attempts", {}))
    for issue_type in ("financial_data", "market_data", "valuation_assumption", "competition", "risk", "math"):
        issue_attempts.setdefault(issue_type, 0)

    priority = ["math", "market_data", "financial_data", "valuation_assumption", "competition", "risk"]
    selected = next((t for t in priority if any(i["type"] == t for i in actionable)), "")
    if needs_revision and selected:
        issue_attempts[selected] += 1

    signature = "|".join(sorted({i["type"] for i in actionable}))
    previous = state.get("last_issue_signature", "")
    stagnant = state.get("stagnant_revision_count", 0)
    if needs_revision and signature and signature == previous:
        stagnant += 1
    elif needs_revision:
        stagnant = 0
    else:
        stagnant = 0

    summary = (
        f"Deterministic score: {deterministic['score']:.2f}\n"
        f"Financial/Market gap days: {deterministic.get('financial_market_gap_days')}\n"
        f"Data failures: {len(deterministic.get('data_failures', []))}\n"
        f"Math failures: {len(deterministic.get('math_failures', []))}\n"
        f"Model failures: {len(deterministic.get('model_failures', []))}\n"
        f"Source quality: {result.source_quality}\n"
        f"Financial consistency: {result.financial_consistency}\n"
        f"Valuation assumptions: {result.valuation_assumptions}\n"
        f"Critic confidence: {result.confidence:.2f}\n"
        f"Revision count: {revision_count}\n"
        f"Selected issue type: {selected}\n"
        f"Issue attempts: {issue_attempts}\n"
        f"Stagnant revision count: {stagnant}\n"
        f"Needs revision: {needs_revision}"
    )

    return {
        "critic_result": result.model_dump(),
        "research_issues": issues,
        "verification_summary": summary,
        "critique": "\n".join(issue["request"] for issue in actionable),
        "needs_revision": needs_revision,
        "revision_count": revision_count,
        "issue_attempts": issue_attempts,
        "last_issue_signature": signature,
        "stagnant_revision_count": stagnant,
    }
