from __future__ import annotations

from typing import Any


NODE_META = [
    {"id": "resolver", "label": "Security Resolver", "phase": "identity", "kind": "deterministic+llm", "x": 80, "y": 60,
     "description": "Resolve fuzzy company input into one canonical listed security.",
     "inputs": ["user_query"], "outputs": ["company", "ticker", "exchange", "currency", "country"]},
    {"id": "planner", "label": "Planner", "phase": "planning", "kind": "llm", "x": 340, "y": 60,
     "description": "Create the research work plan.",
     "inputs": ["company", "ticker"], "outputs": ["plan"]},
    {"id": "research_dispatch", "label": "Research Dispatch", "phase": "orchestration", "kind": "deterministic", "x": 600, "y": 60,
     "description": "Start the parallel research workstreams.",
     "inputs": ["plan"], "outputs": ["attempt_count"]},
    {"id": "fundamentals", "label": "Financial Data", "phase": "research", "kind": "sec+python", "x": 120, "y": 240,
     "description": "Pull SEC filings, build period-aligned TTM financials and canonical FCF.",
     "inputs": ["ticker", "research_issues"],
     "outputs": ["financial_snapshot", "financial_basis", "financial_period", "revenue", "operating_cash_flow", "capex", "free_cash_flow", "shares_outstanding"]},
    {"id": "market_data", "label": "Market Data", "phase": "research", "kind": "search+llm", "x": 400, "y": 240,
     "description": "Resolve current price, market cap, as-of date and public provenance.",
     "inputs": ["company", "ticker", "shares_outstanding", "research_issues"],
     "outputs": ["market_snapshot", "market_price", "market_cap", "market_cap_date"]},
    {"id": "competition", "label": "Competition", "phase": "research", "kind": "search+llm", "x": 680, "y": 240,
     "description": "Research competitive position, peers and evidence.",
     "inputs": ["company", "ticker", "research_issues"], "outputs": ["competition_report", "competition_sources"]},
    {"id": "risk", "label": "Risk", "phase": "research", "kind": "search+llm", "x": 960, "y": 240,
     "description": "Research material business, regulatory, technology and capital risks.",
     "inputs": ["company", "ticker", "research_issues"], "outputs": ["risk_report", "risk_sources"]},
    {"id": "merge", "label": "Evidence Hub", "phase": "synthesis", "kind": "python", "x": 540, "y": 430,
     "description": "Single fan-in barrier. Merge evidence, preserve canonical data and compute completeness.",
     "inputs": ["financial_snapshot", "market_snapshot", "competition_report", "risk_report"],
     "outputs": ["merged_sources", "evidence_summary", "evidence_completeness", "market_cap", "market_snapshot"]},
    {"id": "assumption_builder", "label": "Assumption Builder", "phase": "modeling", "kind": "llm", "x": 540, "y": 600,
     "description": "Build evidence-backed Bear/Base/Bull growth, discount and exit-multiple assumptions.",
     "inputs": ["revenue", "free_cash_flow", "market_cap", "competition_report", "risk_report", "research_issues"],
     "outputs": ["valuation_assumptions", "assumption_summary"]},
    {"id": "valuation", "label": "Python Valuation", "phase": "modeling", "kind": "python", "x": 540, "y": 770,
     "description": "Run deterministic 5-year FCF scenario valuation.",
     "inputs": ["revenue", "free_cash_flow", "market_cap", "valuation_assumptions"],
     "outputs": ["valuation_result", "valuation_summary"]},
    {"id": "verification", "label": "Deterministic Verification", "phase": "verification", "kind": "python", "x": 540, "y": 940,
     "description": "Independently recompute data alignment, valuation math and model structure.",
     "inputs": ["financial_basis", "financial_period", "market_snapshot", "valuation_result", "valuation_assumptions"],
     "outputs": ["deterministic_verification"]},
    {"id": "critic", "label": "LLM Critic", "phase": "verification", "kind": "llm", "x": 540, "y": 1110,
     "description": "Critique source quality and unresolved material issues without overriding deterministic checks.",
     "inputs": ["deterministic_verification", "valuation_summary", "competition_report", "risk_report"],
     "outputs": ["research_issues", "needs_revision", "revision_count", "issue_attempts", "stagnant_revision_count"]},
    {"id": "typed_router", "label": "Typed Issue Router", "phase": "decision", "kind": "python", "x": 540, "y": 1280,
     "description": "Deterministically select success, bounded targeted retry, or insufficient evidence.",
     "inputs": ["research_issues", "revision_count", "issue_attempts", "stagnant_revision_count"], "outputs": ["route"]},
    {"id": "retry_fundamentals", "label": "Retry Financial", "phase": "retry", "kind": "sec+python", "x": 980, "y": 480,
     "description": "Targeted financial-data correction only.",
     "inputs": ["financial_data issues", "last-known-good financial state"], "outputs": ["corrected financial fields"]},
    {"id": "retry_market_data", "label": "Retry Market", "phase": "retry", "kind": "search+llm", "x": 1180, "y": 610,
     "description": "Targeted market-data correction only.",
     "inputs": ["market_data issues", "last-known-good market state"], "outputs": ["corrected market fields"]},
    {"id": "retry_competition", "label": "Retry Competition", "phase": "retry", "kind": "search+llm", "x": 980, "y": 740,
     "description": "Targeted competition evidence correction only.",
     "inputs": ["competition issues"], "outputs": ["corrected competition evidence"]},
    {"id": "retry_risk", "label": "Retry Risk", "phase": "retry", "kind": "search+llm", "x": 1180, "y": 870,
     "description": "Targeted risk evidence correction only.",
     "inputs": ["risk issues"], "outputs": ["corrected risk evidence"]},
    {"id": "success_final", "label": "Success Final", "phase": "final", "kind": "llm", "x": 330, "y": 1450,
     "description": "Write the final research conclusion after the pipeline passes.",
     "inputs": ["verified state"], "outputs": ["status", "final_answer"]},
    {"id": "insufficient_final", "label": "Insufficient Evidence", "phase": "final", "kind": "llm", "x": 750, "y": 1450,
     "description": "Write the unresolved-problems report after a hard stop.",
     "inputs": ["unresolved blocker/major issues"], "outputs": ["status", "final_answer"]},
]

GRAPH_EDGES = [
    {"id": "resolver-planner", "source": "resolver", "target": "planner", "channels": ["logic", "information"], "label": "canonical security"},
    {"id": "planner-dispatch", "source": "planner", "target": "research_dispatch", "channels": ["logic", "information"], "label": "research plan"},
    {"id": "dispatch-fundamentals", "source": "research_dispatch", "target": "fundamentals", "channels": ["logic"], "label": "fan-out"},
    {"id": "dispatch-market", "source": "research_dispatch", "target": "market_data", "channels": ["logic"], "label": "fan-out"},
    {"id": "dispatch-competition", "source": "research_dispatch", "target": "competition", "channels": ["logic"], "label": "fan-out"},
    {"id": "dispatch-risk", "source": "research_dispatch", "target": "risk", "channels": ["logic"], "label": "fan-out"},
    {"id": "fundamentals-merge", "source": "fundamentals", "target": "merge", "channels": ["information", "logic"], "label": "financial snapshot"},
    {"id": "market-merge", "source": "market_data", "target": "merge", "channels": ["information", "logic"], "label": "market snapshot"},
    {"id": "competition-merge", "source": "competition", "target": "merge", "channels": ["information", "logic"], "label": "competition evidence"},
    {"id": "risk-merge", "source": "risk", "target": "merge", "channels": ["information", "logic"], "label": "risk evidence"},
    {"id": "merge-assumption", "source": "merge", "target": "assumption_builder", "channels": ["information", "logic"], "label": "evidence package"},
    {"id": "assumption-valuation", "source": "assumption_builder", "target": "valuation", "channels": ["information", "logic"], "label": "scenario assumptions"},
    {"id": "valuation-verification", "source": "valuation", "target": "verification", "channels": ["information", "logic"], "label": "valuation outputs"},
    {"id": "verification-critic", "source": "verification", "target": "critic", "channels": ["information", "logic"], "label": "deterministic verdict"},
    {"id": "critic-router", "source": "critic", "target": "typed_router", "channels": ["information", "decision", "logic"], "label": "typed issues"},
    {"id": "router-success", "source": "typed_router", "target": "success_final", "channels": ["decision", "logic"], "label": "no actionable issues"},
    {"id": "router-insufficient", "source": "typed_router", "target": "insufficient_final", "channels": ["decision", "logic"], "label": "hard stop"},
    {"id": "router-retry-financial", "source": "typed_router", "target": "retry_fundamentals", "channels": ["decision", "logic"], "label": "financial_data"},
    {"id": "router-retry-market", "source": "typed_router", "target": "retry_market_data", "channels": ["decision", "logic"], "label": "market_data"},
    {"id": "router-retry-competition", "source": "typed_router", "target": "retry_competition", "channels": ["decision", "logic"], "label": "competition"},
    {"id": "router-retry-risk", "source": "typed_router", "target": "retry_risk", "channels": ["decision", "logic"], "label": "risk"},
    {"id": "router-retry-assumption", "source": "typed_router", "target": "assumption_builder", "channels": ["decision", "logic"], "label": "valuation_assumption"},
    {"id": "retry-financial-merge", "source": "retry_fundamentals", "target": "merge", "channels": ["information", "logic"], "label": "corrected financials"},
    {"id": "retry-market-merge", "source": "retry_market_data", "target": "merge", "channels": ["information", "logic"], "label": "corrected market"},
    {"id": "retry-competition-merge", "source": "retry_competition", "target": "merge", "channels": ["information", "logic"], "label": "corrected evidence"},
    {"id": "retry-risk-merge", "source": "retry_risk", "target": "merge", "channels": ["information", "logic"], "label": "corrected evidence"},
]

CANVAS = {"width": 1450, "height": 1580, "node_width": 190, "node_height": 74}
_NODE_BY_ID = {item["id"]: item for item in NODE_META}


def graph_metadata() -> dict[str, Any]:
    return {
        "canvas": CANVAS,
        "nodes": NODE_META,
        "edges": GRAPH_EDGES,
        "legend": {
            "information": "字段、证据、财务快照在节点之间传递",
            "logic": "LangGraph 实际执行顺序 / fan-out / fan-in",
            "decision": "Critic → Router 的条件判断与定向重试",
        },
    }


def node_meta(node: str) -> dict[str, Any]:
    return _NODE_BY_ID.get(node, {
        "id": node, "label": node, "description": "", "inputs": [],
        "outputs": [], "phase": "unknown", "kind": "unknown",
    })


def _preview(value: Any) -> Any:
    if isinstance(value, str):
        return value[:357] + "..." if len(value) > 360 else value
    if isinstance(value, list):
        if len(value) > 8:
            return {"count": len(value), "sample": [_preview(item) for item in value[:4]]}
        return [_preview(item) for item in value]
    if isinstance(value, dict):
        if len(value) > 16:
            keys = list(value.keys())
            return {"keys": keys[:16], "key_count": len(keys)}
        return {str(key): _preview(item) for key, item in value.items()}
    return value


def snapshot_keys(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: _preview(data.get(key)) for key in keys if key in data}


def compact_state_patch(update: dict[str, Any]) -> dict[str, Any]:
    hidden = {
        "fundamentals_report", "competition_report", "risk_report", "market_report",
        "fundamentals_sources", "market_sources", "competition_sources", "risk_sources",
        "merged_sources",
    }
    return {key: value for key, value in update.items() if key not in hidden}


def summarize_node(node: str, state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    if node in {"fundamentals", "retry_fundamentals"}:
        snapshot = state.get("financial_snapshot", {})
        return {
            "provider": snapshot.get("provider"), "basis": state.get("financial_basis"),
            "period": state.get("financial_period"), "revenue_usd_b": state.get("revenue"),
            "ocf_usd_b": state.get("operating_cash_flow"), "capex_usd_b": state.get("capex"),
            "fcf_usd_b": state.get("free_cash_flow"), "shares_outstanding": state.get("shares_outstanding"),
            "ttm_valid": snapshot.get("ttm_valid"), "periods_aligned": snapshot.get("periods_aligned"),
            "source_count": len(state.get("fundamentals_sources", [])),
        }
    if node in {"market_data", "retry_market_data"}:
        snapshot = state.get("market_snapshot", {})
        return {
            "price_usd": state.get("market_price"), "market_cap_usd_b": state.get("market_cap"),
            "as_of_date": state.get("market_cap_date") or snapshot.get("as_of_date"),
            "status": snapshot.get("status"), "provider": snapshot.get("provider"),
            "source_url": snapshot.get("source_url"), "market_cap_method": snapshot.get("market_cap_method"),
            "source_count": len(state.get("market_sources", [])),
        }
    if node in {"competition", "retry_competition"}:
        return {"source_count": len(state.get("competition_sources", [])), "report_preview": _preview(state.get("competition_report", ""))}
    if node in {"risk", "retry_risk"}:
        return {"source_count": len(state.get("risk_sources", [])), "report_preview": _preview(state.get("risk_report", ""))}
    if node == "merge":
        return {"evidence_completeness": state.get("evidence_completeness"), "unique_sources": len(state.get("merged_sources", [])), "financial_basis": state.get("financial_basis"), "market_cap_usd_b": state.get("market_cap")}
    if node == "assumption_builder":
        assumptions = state.get("valuation_assumptions", {})
        return {scenario: {"fcf_growth_rate": assumptions.get(scenario, {}).get("fcf_growth_rate"), "discount_rate": assumptions.get(scenario, {}).get("discount_rate"), "exit_multiple": assumptions.get(scenario, {}).get("exit_multiple")} for scenario in ("bear", "base", "bull")}
    if node == "valuation":
        result = state.get("valuation_result", {})
        scenarios = result.get("scenarios", {})
        return {"valid": result.get("valid"), "core_metrics": _preview(result.get("core_metrics", {})), "scenario_equity_values": {name: item.get("estimated_equity_value") for name, item in scenarios.items()}}
    if node == "verification":
        verification = state.get("deterministic_verification", {})
        return {"passed": verification.get("passed"), "score": verification.get("score"), "financial_market_gap_days": verification.get("financial_market_gap_days"), "data_failures": len(verification.get("data_failures", [])), "math_failures": len(verification.get("math_failures", [])), "model_failures": len(verification.get("model_failures", [])), "warnings": len(verification.get("warnings", []))}
    if node == "critic":
        return {"needs_revision": state.get("needs_revision"), "revision_count": state.get("revision_count"), "issue_attempts": _preview(state.get("issue_attempts", {})), "stagnant_revision_count": state.get("stagnant_revision_count"), "issues": _preview(state.get("research_issues", []))}
    if node in {"success_final", "insufficient_final"}:
        return {"status": state.get("status"), "answer_preview": _preview(state.get("final_answer", ""))}
    if node == "planner":
        return {"tasks": _preview(state.get("plan", []))}
    if node == "research_dispatch":
        return {"attempt_count": state.get("attempt_count"), "parallel_workstreams": ["fundamentals", "market_data", "competition", "risk"]}
    return {"output_keys": sorted(update.keys())}


def decision_snapshot(state: dict[str, Any], route: str) -> dict[str, Any]:
    actionable = [issue for issue in state.get("research_issues", []) if issue.get("severity") in {"blocker", "major"}]
    return {
        "route": route, "needs_revision": bool(actionable), "revision_count": state.get("revision_count", 0),
        "issue_attempts": state.get("issue_attempts", {}), "stagnant_revision_count": state.get("stagnant_revision_count", 0),
        "actionable_issues": actionable,
        "candidates": ["success_final", "retry_fundamentals", "retry_market_data", "assumption_builder", "retry_competition", "retry_risk", "insufficient_final"],
    }
