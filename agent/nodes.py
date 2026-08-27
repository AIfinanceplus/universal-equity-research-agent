from typing import Literal

from agent.config import llm, MAX_RESEARCH_ATTEMPTS
from agent.routing import decide_route_after_critic
from agent.schemas import (
    ResearchState,
    InvestmentPlan,
    MarketSnapshot,
    ValuationAssumptions,
    InvestmentCritique,
)
from agent.search import search_market_data, search_competition, search_risks
from agent.valuation import run_valuation_engine
from agent.verification import run_deterministic_verification
from agent.sec_data import load_sec_financial_snapshot

planner_llm = llm.with_structured_output(InvestmentPlan, method="json_schema")
market_extractor_llm = llm.with_structured_output(MarketSnapshot, method="json_schema")
assumption_llm = llm.with_structured_output(ValuationAssumptions, method="json_schema")
critic_llm = llm.with_structured_output(InvestmentCritique, method="json_schema")


def merge_sources(old_sources, new_sources):
    result, seen = [], set()
    for source in list(old_sources or []) + list(new_sources or []):
        url = source.get("url", "") if isinstance(source, dict) else ""
        if url and url not in seen:
            seen.add(url)
            result.append(source)
    return result


def issue_context(state: ResearchState, issue_type: str) -> str:
    return "\n".join(
        issue.get("request", "")
        for issue in state.get("research_issues", [])
        if issue.get("type") == issue_type
    )


def planner_node(state: ResearchState):
    plan = planner_llm.invoke(f"""
Create a short equity-research plan for {state['company']} ({state['ticker']}).
Use exactly these workstreams: financial_data, market_data, competition, risk, valuation.
Do not perform research; only define objectives.
""")
    return {"plan": [task.model_dump() for task in plan.tasks]}


def research_dispatch_node(state: ResearchState):
    attempt = state.get("attempt_count", 0) + 1
    print(f"\n=== INITIAL RESEARCH ROUND {attempt} ===")
    return {"attempt_count": attempt}


def fundamentals_node(state: ResearchState):
    print("\n>>> SEC FINANCIAL DATA NODE START")
    sec = load_sec_financial_snapshot(state["ticker"])
    annual, current, prior, ttm = sec["annual"], sec["latest_ytd"], sec["prior_ytd"], sec["ttm"]

    annual_revenue = float(annual.get("revenue_usd_b") or 0)
    annual_ocf = float(annual.get("operating_cash_flow_usd_b") or 0)
    annual_capex = float(annual.get("capex_usd_b") or 0)
    annual_fcf = float(annual.get("free_cash_flow_usd_b") or 0)
    current_revenue = float(current.get("revenue_usd_b") or 0)
    current_ocf = float(current.get("operating_cash_flow_usd_b") or 0)
    current_capex = float(current.get("capex_usd_b") or 0)
    prior_revenue = float(prior.get("revenue_usd_b") or 0)
    prior_ocf = float(prior.get("operating_cash_flow_usd_b") or 0)
    prior_capex = float(prior.get("capex_usd_b") or 0)

    if sec.get("ttm_valid"):
        ttm_revenue = float(ttm.get("revenue_usd_b") or 0)
        ttm_ocf = float(ttm.get("operating_cash_flow_usd_b") or 0)
        ttm_capex = float(ttm.get("capex_usd_b") or 0)
        ttm_fcf = float(ttm.get("free_cash_flow_usd_b") or 0)
        financial_basis = "TTM"
        financial_period = f"TTM through {ttm.get('period_end') or ''}"
        revenue, ocf, capex, fcf = ttm_revenue, ttm_ocf, ttm_capex, ttm_fcf
    elif state.get("ttm_revenue", 0) > 0 and state.get("ttm_free_cash_flow", 0) > 0:
        ttm_revenue = state["ttm_revenue"]
        ttm_ocf = state["ttm_operating_cash_flow"]
        ttm_capex = state["ttm_capex"]
        ttm_fcf = state["ttm_free_cash_flow"]
        financial_basis = "TTM"
        financial_period = state["ttm_period"]
        revenue, ocf, capex, fcf = ttm_revenue, ttm_ocf, ttm_capex, ttm_fcf
    else:
        ttm_revenue = ttm_ocf = ttm_capex = ttm_fcf = 0.0
        financial_basis = "ANNUAL"
        financial_period = str(annual.get("period_end") or "")
        revenue, ocf, capex, fcf = annual_revenue, annual_ocf, annual_capex, annual_fcf

    shares = float((sec.get("shares") or {}).get("shares", 0) or 0)
    snapshot = {
        "provider": "SEC EDGAR",
        "cik": sec["cik"],
        "companyfacts_url": sec["companyfacts_url"],
        "submissions_url": sec["submissions_url"],
        "annual": annual,
        "latest_ytd": current,
        "prior_ytd": prior,
        "ttm": ttm,
        "shares": sec.get("shares") or {},
        "ttm_valid": sec.get("ttm_valid", False),
        "periods_aligned": sec.get("periods_aligned", False),
        "errors": sec.get("errors", []),
        "valuation_basis": financial_basis,
    }
    report = (
        f"SEC EDGAR direct structured data. CIK={sec['cik']}; "
        f"TTM valid={sec.get('ttm_valid')}; errors={sec.get('errors', [])}"
    )
    print(financial_basis, financial_period, revenue, fcf)
    return {
        "fundamentals_report": report,
        "fundamentals_sources": merge_sources(state.get("fundamentals_sources", []), sec.get("sources", [])),
        "financial_snapshot": snapshot,
        "shares_outstanding": shares,
        "annual_revenue": annual_revenue,
        "annual_operating_cash_flow": annual_ocf,
        "annual_capex": annual_capex,
        "annual_free_cash_flow": annual_fcf,
        "annual_fiscal_year": str(annual.get("period_end") or ""),
        "latest_ytd_revenue": current_revenue,
        "latest_ytd_operating_cash_flow": current_ocf,
        "latest_ytd_capex": current_capex,
        "latest_ytd_period": str(current.get("period_end") or ""),
        "latest_ytd_months": int(current.get("months") or 0),
        "prior_ytd_revenue": prior_revenue,
        "prior_ytd_operating_cash_flow": prior_ocf,
        "prior_ytd_capex": prior_capex,
        "prior_ytd_period": str(prior.get("period_end") or ""),
        "prior_ytd_months": int(prior.get("months") or 0),
        "ttm_revenue": ttm_revenue,
        "ttm_operating_cash_flow": ttm_ocf,
        "ttm_capex": ttm_capex,
        "ttm_free_cash_flow": ttm_fcf,
        "ttm_period": financial_period if financial_basis == "TTM" else "",
        "revenue": revenue,
        "operating_cash_flow": ocf,
        "capex": capex,
        "free_cash_flow": fcf,
        "financial_basis": financial_basis,
        "financial_period": financial_period,
    }


def market_data_node(state: ResearchState):
    print("\n>>> MARKET DATA NODE START")
    result = search_market_data(
        state["company"], state["ticker"], state.get("attempt_count", 1),
        issue_context(state, "market_data")
    )
    allowed_urls = [s.get("url", "") for s in result.get("sources", []) if s.get("url")]
    snapshot = market_extractor_llm.invoke(f"""
Extract current market data only from this report for {state['ticker']}.
Return price USD, Market Cap USD billions if available, as-of date/time/timezone,
provider and source URL. Source URL must be one of: {allowed_urls}
Missing => null; never use zero. 1 trillion = 1000 billion.
REPORT:\n{result['report']}
""")
    source_url = snapshot.source_url if snapshot.source_url in allowed_urls else (allowed_urls[0] if allowed_urls else "")
    old = state.get("market_snapshot", {})
    old_cap = float(state.get("market_cap", 0) or 0)
    old_price = float(state.get("market_price", 0) or 0)
    price_ok = snapshot.price_usd is not None and snapshot.price_usd > 0 and bool(source_url)
    cap_ok = snapshot.market_cap_usd_b is not None and snapshot.market_cap_usd_b > 0 and bool(source_url)

    if cap_ok:
        price = float(snapshot.price_usd) if price_ok else old_price
        cap = float(snapshot.market_cap_usd_b)
        date_value = snapshot.as_of_date or state.get("market_cap_date", "")
        canonical = {
            "price_usd": price, "market_cap_usd_b": cap, "as_of_date": date_value,
            "as_of_time": snapshot.as_of_time, "timezone": snapshot.timezone,
            "provider": snapshot.provider, "source_url": source_url, "status": "verified",
            "notes": snapshot.notes, "market_cap_method": "provider_reported",
        }
    elif price_ok:
        price, cap = float(snapshot.price_usd), old_cap
        date_value = snapshot.as_of_date or state.get("market_cap_date", "")
        canonical = {
            "price_usd": price, "market_cap_usd_b": cap if cap > 0 else None,
            "as_of_date": date_value, "as_of_time": snapshot.as_of_time,
            "timezone": snapshot.timezone, "provider": snapshot.provider,
            "source_url": source_url, "status": "verified" if cap > 0 else "price_verified",
            "notes": "Price verified; Market Cap may be derived from SEC shares.",
            "market_cap_method": old.get("market_cap_method", "") if cap > 0 else "pending_sec_share_derivation",
        }
    elif old_cap > 0 and old.get("status") in {"verified", "derived_verified"}:
        price, cap, date_value, canonical = old_price, old_cap, state.get("market_cap_date", ""), old
    else:
        price = cap = 0.0
        date_value = ""
        canonical = {"status": "unavailable"}

    return {
        "market_report": result["report"],
        "market_sources": merge_sources(state.get("market_sources", []), result.get("sources", [])),
        "market_snapshot": canonical,
        "market_price": price,
        "market_cap": cap,
        "market_cap_date": date_value,
    }


def competition_node(state: ResearchState):
    result = search_competition(
        state["company"], state["ticker"], state.get("attempt_count", 1),
        issue_context(state, "competition")
    )
    return {
        "competition_report": result["report"],
        "competition_sources": merge_sources(state.get("competition_sources", []), result.get("sources", [])),
    }


def risk_node(state: ResearchState):
    result = search_risks(
        state["company"], state["ticker"], state.get("attempt_count", 1),
        issue_context(state, "risk")
    )
    return {
        "risk_report": result["report"],
        "risk_sources": merge_sources(state.get("risk_sources", []), result.get("sources", [])),
    }


def merge_evidence_node(state: ResearchState):
    print("\n=== EVIDENCE HUB ===")
    cap = float(state.get("market_cap", 0) or 0)
    price = float(state.get("market_price", 0) or 0)
    shares = float(state.get("shares_outstanding", 0) or 0)
    snapshot = dict(state.get("market_snapshot", {}))
    if cap <= 0 and price > 0 and shares > 0:
        cap = price * shares / 1_000_000_000
        snapshot.update({
            "market_cap_usd_b": cap,
            "market_cap_method": "derived: market_price * SEC shares_outstanding",
            "shares_outstanding": shares,
            "shares_source_url": (state.get("financial_snapshot", {}).get("shares", {}) or {}).get("filing_url", ""),
        })
        if snapshot.get("status") in {"verified", "price_verified"}:
            snapshot["status"] = "derived_verified"
    all_sources = (
        state.get("fundamentals_sources", []) + state.get("market_sources", [])
        + state.get("competition_sources", []) + state.get("risk_sources", [])
    )
    merged = merge_sources([], all_sources)
    score = 0.0
    score += 0.10 if state.get("revenue", 0) > 0 else 0
    score += 0.10 if state.get("free_cash_flow", 0) > 0 else 0
    score += 0.10 if cap > 0 else 0
    score += 0.10 if snapshot.get("status") in {"verified", "derived_verified"} else 0
    score += 0.15 if state.get("financial_basis") == "TTM" else (0.05 if state.get("financial_basis") == "ANNUAL" else 0)
    score += 0.15 if len(state.get("fundamentals_sources", [])) >= 2 else 0
    score += 0.15 if state.get("competition_sources") else 0
    score += 0.15 if state.get("risk_sources") else 0
    score = min(score, 1.0)
    summary = (
        f"Financial basis: {state.get('financial_basis')}\n"
        f"Financial period: {state.get('financial_period')}\n"
        f"Unique sources: {len(merged)}\nEvidence completeness: {score:.2f}"
    )
    print(summary)
    return {
        "market_cap": cap,
        "market_snapshot": snapshot,
        "merged_sources": merged,
        "evidence_summary": summary,
        "evidence_completeness": score,
    }


def assumption_builder_node(state: ResearchState):
    print("\n=== ASSUMPTION BUILDER ===")
    current_pfcf = state["market_cap"] / state["free_cash_flow"] if state.get("market_cap", 0) > 0 and state.get("free_cash_flow", 0) > 0 else None
    result = assumption_llm.invoke(f"""
Build transparent Bear/Base/Bull research assumptions for {state['company']} ({state['ticker']}).
Financial basis: {state['financial_basis']} {state['financial_period']}
Revenue: {state['revenue']}B; FCF: {state['free_cash_flow']}B; Market Cap: {state['market_cap']}B;
Current P/FCF: {current_pfcf}
Competition:\n{state['competition_report']}
Risk:\n{state['risk_report']}
Targeted correction:\n{issue_context(state, 'valuation_assumption')}

For each scenario choose annual FCF growth, simplified discount rate, exit FCF multiple,
rationale and at least 2 concrete evidence items. Enforce bear growth <= base <= bull,
bear exit <= base <= bull, bear discount >= base >= bull. Explain why the exit multiple
contracts/stays stable/expands relative to observable current P/FCF. These are research
scenarios, not guidance and not a standard WACC DCF. basis must equal {state['financial_basis']}.
""")
    payload = result.model_dump()
    return {
        "valuation_assumptions": payload,
        "assumption_summary": result.notes or "Bear/Base/Bull assumptions built from evidence.",
    }


def valuation_node(state: ResearchState):
    result = run_valuation_engine(
        revenue=state["revenue"], free_cash_flow=state["free_cash_flow"],
        market_cap=state["market_cap"], assumptions=state["valuation_assumptions"]
    )
    if not result.get("valid"):
        return {"valuation_result": result, "valuation_summary": result.get("reason", "Valuation failed")}
    core = result["core_metrics"]
    lines = [
        result["methodology"],
        f"Financial Basis: {state['financial_basis']}",
        f"Financial Period: {state['financial_period']}",
        f"Revenue: ${state['revenue']:.2f}B",
        f"Starting FCF: ${state['free_cash_flow']:.2f}B",
        f"Market Cap: ${state['market_cap']:.2f}B",
        f"Market Date: {state['market_cap_date']}",
        f"P/S: {core['price_to_sales']:.2f}x; P/FCF: {core['price_to_fcf']:.2f}x; FCF Yield: {core['fcf_yield']:.2%}",
    ]
    for name in ("bear", "base", "bull"):
        s = result["scenarios"][name]
        lines.append(
            f"{name.upper()}: growth={s['growth_rate']:.2%}, discount={s['discount_rate']:.2%}, "
            f"exit={s['exit_multiple']:.2f}x, explicitPV=${s['explicit_period_pv']:.2f}B, "
            f"terminalPV=${s['discounted_terminal_value']:.2f}B, equity=${s['estimated_equity_value']:.2f}B, "
            f"return={s['implied_return']:.2%}"
        )
    return {"valuation_result": result, "valuation_summary": "\n".join(lines)}


def verification_node(state: ResearchState):
    result = run_deterministic_verification(
        revenue=state["revenue"], free_cash_flow=state["free_cash_flow"], market_cap=state["market_cap"],
        financial_basis=state["financial_basis"], financial_period=state["financial_period"],
        market_snapshot=state["market_snapshot"], evidence_completeness=state["evidence_completeness"],
        valuation_result=state["valuation_result"], assumptions=state["valuation_assumptions"],
        source_count=len(state.get("merged_sources", [])),
    )
    return {"deterministic_verification": result}


def _append_unique(issues: list[dict], issue: dict):
    key = (issue["type"], issue["severity"], issue["request"])
    if key not in {(i["type"], i["severity"], i["request"]) for i in issues}:
        issues.append(issue)


def critic_node(state: ResearchState):
    print("\n=== INVESTMENT CRITIC ===")
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
- If SEC provider + ttm_valid=True, do not create blocker/major financial-data issues merely for
  wanting more quarter history, working-capital detail or normalization.
- Latest public TTM plus current market price is normal; exact same-day financials are not required.
- If math_failures=[], do not create an actionable math issue.
- This intentionally uses a simplified 5-year FCF scenario model; do not require WACC/FCFF/FCFE,
  standard DCF, EPS model, SOTP or full comps as blockers.
- More risk/competition quantification alone is normally minor.
- Assumptions are judgmental by design; major only if rationale/evidence/order is absent,
  contradictory or clearly implausible without explanation.
Return only genuine unresolved issues using allowed typed issue categories.
""")

    issues = []
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
    sec_ttm = state.get("financial_snapshot", {}).get("provider") == "SEC EDGAR" and state.get("financial_snapshot", {}).get("ttm_valid") is True
    market_ok = state.get("market_snapshot", {}).get("status") in {"verified", "derived_verified"} and bool(state.get("market_snapshot", {}).get("source_url"))

    for raw in [i.model_dump() for i in result.issues]:
        issue = dict(raw)
        t, sev, req = issue["type"], issue["severity"], issue["request"]
        if t == "financial_data" and sec_ttm and data_ok and sev in {"blocker", "major"}:
            issue.update(severity="minor", request="Optional financial-data extension: " + req)
        if t == "market_data" and market_ok and data_ok and sev in {"blocker", "major"}:
            issue.update(severity="minor", request="Optional market-data extension: " + req)
        if t == "math" and math_ok:
            issue.update(severity="minor", request="Non-blocking presentation clarification: " + req)
        if t == "valuation_assumption" and model_ok and sev in {"blocker", "major"} and state.get("revision_count", 0) >= 1:
            issue.update(severity="minor", request="Residual assumption uncertainty: " + req)
        if t in {"competition", "risk"} and sev == "major" and ("quant" in req.lower() or "sensitivity" in req.lower()):
            issue["severity"] = "minor"
        _append_unique(issues, issue)

    actionable = [i for i in issues if i["severity"] in {"blocker", "major"}]
    needs_revision = bool(actionable)
    revision_count = state.get("revision_count", 0) + (1 if needs_revision else 0)
    issue_attempts = dict(state.get("issue_attempts", {}))
    for t in ("financial_data", "market_data", "valuation_assumption", "competition", "risk", "math"):
        issue_attempts.setdefault(t, 0)
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
        f"Source quality: {result.source_quality}\nFinancial consistency: {result.financial_consistency}\n"
        f"Valuation assumptions: {result.valuation_assumptions}\nCritic confidence: {result.confidence:.2f}\n"
        f"Revision count: {revision_count}\nSelected issue type: {selected}\n"
        f"Issue attempts: {issue_attempts}\nStagnant revision count: {stagnant}\nNeeds revision: {needs_revision}"
    )
    return {
        "critic_result": result.model_dump(),
        "research_issues": issues,
        "verification_summary": summary,
        "critique": "\n".join(i["request"] for i in actionable),
        "needs_revision": needs_revision,
        "revision_count": revision_count,
        "issue_attempts": issue_attempts,
        "last_issue_signature": signature,
        "stagnant_revision_count": stagnant,
    }


def _message_text(response) -> str:
    text = getattr(response, "text", None)
    return text if isinstance(text, str) else str(response.content)


def success_final_node(state: ResearchState):
    response = llm.invoke(f"""
Write a concise professional equity-research conclusion for {state['company']} ({state['ticker']}).
Use the verified Python numbers exactly. Bear/Base/Bull are research scenarios, not company forecasts.
Do not call the simplified model a standard DCF. status=success means the pipeline passed, not that
this stock must be bought.
FINANCIAL: {state['financial_snapshot']}
MARKET: {state['market_snapshot']}
VALUATION: {state['valuation_summary']}
VERIFICATION: {state['verification_summary']}
COMPETITION: {state['competition_report']}
RISK: {state['risk_report']}
""")
    return {"status": "success", "final_answer": _message_text(response)}


def insufficient_final_node(state: ResearchState):
    response = llm.invoke(f"""
Write the final unresolved-problems report for {state['company']} ({state['ticker']}).
Only report unresolved blocker/major issues; distinguish data, math, model/assumption and evidence.
Never claim Python was not run and do not force a buy/sell conclusion.
VERIFICATION: {state['verification_summary']}
ISSUES: {state['research_issues']}
VALUATION: {state['valuation_summary']}
""")
    return {"status": "insufficient_evidence", "final_answer": _message_text(response)}


def route_after_critic(state: ResearchState) -> Literal[
    "retry_fundamentals", "retry_market_data", "retry_competition", "retry_risk",
    "assumption_builder", "success_final", "insufficient_final",
]:
    destination = decide_route_after_critic(
        state,
        max_research_attempts=MAX_RESEARCH_ATTEMPTS,
    )
    print(
        f"\n=== TYPED ISSUE ROUTER ===\nrevision_count={state.get('revision_count', 0)}\n"
        f"issue_attempts={state.get('issue_attempts', {})}\n"
        f"stagnant_revision_count={state.get('stagnant_revision_count', 0)}\nROUTER → {destination}"
    )
    return destination
