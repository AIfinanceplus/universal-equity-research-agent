from __future__ import annotations

from agent.schemas import ResearchState


def _merge_sources(old_sources, new_sources):
    result, seen = [], set()
    for source in list(old_sources or []) + list(new_sources or []):
        url = source.get("url", "") if isinstance(source, dict) else ""
        if url and url not in seen:
            seen.add(url)
            result.append(source)
    return result


def merge_evidence_node(state: ResearchState):
    print("\n=== EVIDENCE HUB (YAHOO-ONLY) ===")

    cap = float(state.get("market_cap", 0) or 0)
    price = float(state.get("market_price", 0) or 0)
    shares = float(state.get("shares_outstanding", 0) or 0)
    snapshot = dict(state.get("market_snapshot", {}))

    if cap <= 0 and price > 0 and shares > 0:
        cap = price * shares / 1_000_000_000
        snapshot.update({
            "market_cap_usd_b": cap,
            "market_cap_method": "derived: Yahoo price * Yahoo shares_outstanding",
            "shares_outstanding": shares,
        })
        if snapshot.get("status") in {"verified", "price_verified"}:
            snapshot["status"] = "derived_verified"

    all_sources = (
        state.get("fundamentals_sources", [])
        + state.get("market_sources", [])
        + state.get("competition_sources", [])
        + state.get("risk_sources", [])
    )
    merged = _merge_sources([], all_sources)

    financial_ok = bool(state.get("financial_snapshot", {}).get("valid"))
    revenue_present = state.get("revenue") is not None and float(state.get("revenue", 0) or 0) > 0
    fcf_present = financial_ok and state.get("free_cash_flow") is not None
    market_ok = snapshot.get("status") in {"verified", "derived_verified"}

    score = 0.0
    score += 0.15 if revenue_present else 0.0
    score += 0.15 if fcf_present else 0.0
    score += 0.15 if cap > 0 else 0.0
    score += 0.10 if market_ok else 0.0
    score += 0.15 if state.get("financial_basis") == "TTM" else (0.08 if state.get("financial_basis") == "ANNUAL" else 0.0)
    score += 0.10 if state.get("fundamentals_sources") else 0.0
    score += 0.10 if state.get("competition_sources") else 0.0
    score += 0.10 if state.get("risk_sources") else 0.0
    score = min(score, 1.0)

    summary = (
        f"Financial provider: Yahoo Finance via yfinance\n"
        f"Financial basis: {state.get('financial_basis')}\n"
        f"Financial period: {state.get('financial_period')}\n"
        f"Unique sources: {len(merged)}\n"
        f"Evidence completeness: {score:.2f}"
    )

    return {
        "market_cap": cap,
        "market_snapshot": snapshot,
        "merged_sources": merged,
        "evidence_summary": summary,
        "evidence_completeness": score,
    }
