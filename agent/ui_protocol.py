from __future__ import annotations

from typing import Any

from agent.routing import actionable_issues


NODE_META = [
    {"id": "resolver", "label": "Security Resolver", "phase": "identity", "kind": "deterministic+llm", "x": 70, "y": 50,
     "description": "Resolve fuzzy company input into one canonical listed security.", "inputs": ["user_query"], "outputs": ["company", "ticker", "exchange", "currency", "country"]},
    {"id": "planner", "label": "Planner", "phase": "planning", "kind": "llm", "x": 340, "y": 50,
     "description": "Create the research work plan.", "inputs": ["company", "ticker"], "outputs": ["plan"]},
    {"id": "research_dispatch", "label": "Research Dispatch", "phase": "orchestration", "kind": "deterministic", "x": 610, "y": 50,
     "description": "Start the parallel research workstreams.", "inputs": ["plan"], "outputs": ["attempt_count"]},

    {"id": "fundamentals", "label": "Financial Data", "phase": "research", "kind": "sec+python", "x": 70, "y": 220,
     "description": "Pull SEC filings, build period-aligned TTM financials and canonical FCF.",
     "inputs": ["ticker", "research_issues"], "outputs": ["financial_snapshot", "financial_basis", "financial_period", "revenue", "operating_cash_flow", "capex", "free_cash_flow", "shares_outstanding"]},
    {"id": "market_data", "label": "Market Data", "phase": "research", "kind": "search+llm", "x": 340, "y": 220,
     "description": "Resolve current price, market cap, as-of date and public provenance.",
     "inputs": ["company", "ticker", "shares_outstanding", "research_issues"], "outputs": ["market_snapshot", "market_price", "market_cap", "market_cap_date"]},
    {"id": "competition", "label": "Competition", "phase": "research", "kind": "search+llm", "x": 610, "y": 220,
     "description": "Research competitive position, peers and evidence.",
     "inputs": ["company", "ticker", "research_issues"], "outputs": ["competition_report", "competition_sources"]},
    {"id": "risk", "label": "Risk", "phase": "research", "kind": "search+llm", "x": 880, "y": 220,
     "description": "Research material business, regulatory, technology and capital risks.",
     "inputs": ["company", "ticker", "research_issues"], "outputs": ["risk_report", "risk_sources"]},

    {"id": "merge", "label": "Evidence Hub", "phase": "synthesis", "kind": "python", "x": 475, "y": 390,
     "description": "Single fan-in barrier. Merge evidence, preserve canonical data and compute completeness.",
     "inputs": ["financial_snapshot", "market_snapshot", "competition_report", "risk_report"],
     "outputs": ["merged_sources", "evidence_summary", "evidence_completeness", "market_cap", "market_snapshot"]},

    {"id": "strategy_metrics", "label": "Strategy Metrics", "phase": "screening-data", "kind": "sec+python", "x": 475, "y": 550,
     "description": "Build a shared SEC historical-metrics profile for all investor screens.",
     "inputs": ["ticker", "market_price", "market_cap", "shares_outstanding"], "outputs": ["strategy_metrics"]},

    {"id": "strategy_graham", "label": "Graham", "phase": "strategy-screen", "kind": "python", "x": 60, "y": 720,
     "description": "Benjamin Graham defensive screen using the user-defined rules.", "inputs": ["strategy_metrics"], "outputs": ["strategy_graham"]},
    {"id": "strategy_buffett", "label": "Buffett", "phase": "strategy-screen", "kind": "python", "x": 290, "y": 720,
     "description": "Warren Buffett quality/value screen using the user-defined rules.", "inputs": ["strategy_metrics"], "outputs": ["strategy_buffett"]},
    {"id": "strategy_lynch", "label": "Lynch", "phase": "strategy-screen", "kind": "python", "x": 520, "y": 720,
     "description": "Peter Lynch growth-at-a-reasonable-price screen.", "inputs": ["strategy_metrics"], "outputs": ["strategy_lynch"]},
    {"id": "strategy_fisher", "label": "Fisher", "phase": "strategy-screen", "kind": "python", "x": 750, "y": 720,
     "description": "Philip Fisher quantitative proxy screen.", "inputs": ["strategy_metrics"], "outputs": ["strategy_fisher"]},
    {"id": "strategy_greenblatt", "label": "Greenblatt", "phase": "strategy-screen", "kind": "python", "x": 980, "y": 720,
     "description": "Joel Greenblatt Magic Formula screen with explicit unknowns when cross-sectional ranks are unavailable.", "inputs": ["strategy_metrics"], "outputs": ["strategy_greenblatt"]},

    {"id": "strategy_hohn", "label": "Chris Hohn / TCI", "phase": "strategy-screen", "kind": "python", "x": 60, "y": 870,
     "description": "TCI-style quality, capital efficiency and moat proxy screen.", "inputs": ["strategy_metrics"], "outputs": ["strategy_hohn"]},
    {"id": "strategy_druckenmiller", "label": "Druckenmiller", "phase": "strategy-screen", "kind": "python", "x": 290, "y": 870,
     "description": "Dynamic momentum/estimate-revision framework; unavailable dynamic fields stay UNKNOWN.", "inputs": ["strategy_metrics"], "outputs": ["strategy_druckenmiller"]},
    {"id": "strategy_tepper", "label": "Tepper", "phase": "strategy-screen", "kind": "python", "x": 520, "y": 870,
     "description": "Deep-value/event-driven framework; event and historical-percentile fields stay explicit.", "inputs": ["strategy_metrics"], "outputs": ["strategy_tepper"]},
    {"id": "strategy_klarman", "label": "Klarman", "phase": "strategy-screen", "kind": "python", "x": 750, "y": 870,
     "description": "Margin-of-safety framework; liquidation/NPV/catalyst requirements are not guessed.", "inputs": ["strategy_metrics"], "outputs": ["strategy_klarman"]},
    {"id": "strategy_ackman_smith", "label": "Ackman / Smith", "phase": "strategy-screen", "kind": "python", "x": 980, "y": 870,
     "description": "Quality compounder screen combining the user-defined Ackman and Terry Smith criteria.", "inputs": ["strategy_metrics"], "outputs": ["strategy_ackman_smith"]},

    {"id": "strategy_screening_hub", "label": "Strategy Screening Hub", "phase": "strategy-summary", "kind": "python", "x": 475, "y": 1030,
     "description": "Fan-in all ten screens and rank the closest matches without hiding missing data.",
     "inputs": ["strategy_graham", "strategy_buffett", "strategy_lynch", "strategy_fisher", "strategy_greenblatt", "strategy_hohn", "strategy_druckenmiller", "strategy_tepper", "strategy_klarman", "strategy_ackman_smith"],
     "outputs": ["strategy_screening"]},

    {"id": "assumption_builder", "label": "Assumption Builder", "phase": "modeling", "kind": "llm", "x": 475, "y": 1190,
     "description": "Build evidence-backed Bear/Base/Bull growth, discount and exit-multiple assumptions.",
     "inputs": ["revenue", "free_cash_flow", "market_cap", "competition_report", "risk_report", "research_issues"],
     "outputs": ["valuation_assumptions", "assumption_summary"]},
    {"id": "valuation", "label": "Python Valuation", "phase": "modeling", "kind": "python", "x": 475, "y": 1350,
     "description": "Run deterministic 5-year FCF scenario valuation.",
     "inputs": ["revenue", "free_cash_flow", "market_cap", "valuation_assumptions"], "outputs": ["valuation_result", "valuation_summary"]},
    {"id": "verification", "label": "Deterministic Verification", "phase": "verification", "kind": "python", "x": 475, "y": 1510,
     "description": "Independently recompute data alignment, valuation math and model structure.",
     "inputs": ["financial_basis", "financial_period", "market_snapshot", "valuation_result", "valuation_assumptions"], "outputs": ["deterministic_verification"]},
    {"id": "critic", "label": "LLM Critic", "phase": "verification", "kind": "llm", "x": 475, "y": 1670,
     "description": "Critique source quality and unresolved material issues without overriding deterministic checks.",
     "inputs": ["deterministic_verification", "valuation_summary", "competition_report", "risk_report"],
     "outputs": ["research_issues", "needs_revision", "revision_count", "issue_attempts", "stagnant_revision_count"]},
    {"id": "typed_router", "label": "Typed Issue Router", "phase": "decision", "kind": "python", "x": 475, "y": 1830,
     "description": "Deterministically select success, bounded targeted retry, or insufficient evidence.",
     "inputs": ["research_issues", "revision_count", "issue_attempts", "stagnant_revision_count"], "outputs": ["route"]},

    {"id": "retry_fundamentals", "label": "Retry Financial", "phase": "retry", "kind": "sec+python", "x": 1360, "y": 420,
     "description": "Targeted financial-data correction only.", "inputs": ["financial_data issues", "last-known-good financial state"], "outputs": ["corrected financial fields"]},
    {"id": "retry_market_data", "label": "Retry Market", "phase": "retry", "kind": "search+llm", "x": 1580, "y": 550,
     "description": "Targeted market-data correction only.", "inputs": ["market_data issues", "last-known-good market state"], "outputs": ["corrected market fields"]},
    {"id": "retry_competition", "label": "Retry Competition", "phase": "retry", "kind": "search+llm", "x": 1360, "y": 680,
     "description": "Targeted competition evidence correction only.", "inputs": ["competition issues"], "outputs": ["corrected competition evidence"]},
    {"id": "retry_risk", "label": "Retry Risk", "phase": "retry", "kind": "search+llm", "x": 1580, "y": 810,
     "description": "Targeted risk evidence correction only.", "inputs": ["risk issues"], "outputs": ["corrected risk evidence"]},

    {"id": "success_final", "label": "Success Final", "phase": "final", "kind": "llm", "x": 250, "y": 2000,
     "description": "Write the final research conclusion after the pipeline passes.", "inputs": ["verified state"], "outputs": ["status", "final_answer"]},
    {"id": "insufficient_final", "label": "Insufficient Evidence", "phase": "final", "kind": "llm", "x": 700, "y": 2000,
     "description": "Write the unresolved-problems report after a hard stop.", "inputs": ["unresolved blocker/major issues"], "outputs": ["status", "final_answer"]},
]

STRATEGY_IDS = [
    "strategy_graham", "strategy_buffett", "strategy_lynch", "strategy_fisher", "strategy_greenblatt",
    "strategy_hohn", "strategy_druckenmiller", "strategy_tepper", "strategy_klarman", "strategy_ackman_smith",
]

GRAPH_EDGES = [
    {"id": "resolver-planner", "source": "resolver", "target": "planner", "channels": ["logic", "information"], "label": "canonical security"},
    {"id": "planner-dispatch", "source": "planner", "target": "research_dispatch", "channels": ["logic", "information"], "label": "research plan"},
    *[
        {"id": f"dispatch-{node}", "source": "research_dispatch", "target": node, "channels": ["logic"], "label": "fan-out"}
        for node in ("fundamentals", "market_data", "competition", "risk")
    ],
    {"id": "fundamentals-merge", "source": "fundamentals", "target": "merge", "channels": ["information", "logic"], "label": "financial snapshot"},
    {"id": "market-merge", "source": "market_data", "target": "merge", "channels": ["information", "logic"], "label": "market snapshot"},
    {"id": "competition-merge", "source": "competition", "target": "merge", "channels": ["information", "logic"], "label": "competition evidence"},
    {"id": "risk-merge", "source": "risk", "target": "merge", "channels": ["information", "logic"], "label": "risk evidence"},
    {"id": "merge-strategy-metrics", "source": "merge", "target": "strategy_metrics", "channels": ["information", "logic"], "label": "canonical research state"},
    *[
        {"id": f"metrics-{node}", "source": "strategy_metrics", "target": node, "channels": ["information", "logic"], "label": "shared metrics"}
        for node in STRATEGY_IDS
    ],
    *[
        {"id": f"{node}-screen-hub", "source": node, "target": "strategy_screening_hub", "channels": ["information", "logic"], "label": "rule verdicts"}
        for node in STRATEGY_IDS
    ],
    {"id": "screen-hub-assumption", "source": "strategy_screening_hub", "target": "assumption_builder", "channels": ["information", "logic"], "label": "strategy matrix"},
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

CANVAS = {"width": 1850, "height": 2140, "node_width": 205, "node_height": 74}
_NODE_BY_ID = {item["id"]: item for item in NODE_META}


def graph_metadata() -> dict[str, Any]:
    return {
        "canvas": CANVAS,
        "nodes": NODE_META,
        "edges": GRAPH_EDGES,
        "legend": {
            "information": "字段、证据、财务快照和策略指标在节点之间传递",
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
        "merged_sources", "strategy_metrics",
        "strategy_graham", "strategy_buffett", "strategy_lynch", "strategy_fisher",
        "strategy_greenblatt", "strategy_hohn", "strategy_druckenmiller", "strategy_tepper",
        "strategy_klarman", "strategy_ackman_smith",
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
    if node == "strategy_metrics":
        metrics = state.get("strategy_metrics", {})
        keep = ["current_ratio", "debt_to_equity", "net_margin", "roe_5y_avg", "revenue_cagr_5y", "eps_cagr_5y", "p_fcf", "fcf_yield", "pe", "pb", "peg", "graham_number"]
        return {key: metrics.get(key) for key in keep}
    if node in STRATEGY_IDS:
        result = state.get(node, {})
        return {"title": result.get("title"), "verdict": result.get("verdict"), "coverage": result.get("coverage"), "counts": result.get("counts"), "rules": _preview(result.get("rules", []))}
    if node == "strategy_screening_hub":
        screen = state.get("strategy_screening", {})
        return {"verdict_counts": screen.get("verdict_counts", {}), "best_matches": screen.get("best_matches", [])}
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
    actionable = actionable_issues(state)
    return {
        "route": route,
        "needs_revision": bool(actionable),
        "revision_count": state.get("revision_count", 0),
        "issue_attempts": state.get("issue_attempts", {}),
        "stagnant_revision_count": state.get("stagnant_revision_count", 0),
        "actionable_issues": actionable,
        "all_critic_issues": state.get("research_issues", []),
        "candidates": ["success_final", "retry_fundamentals", "retry_market_data", "assumption_builder", "retry_competition", "retry_risk", "insufficient_final"],
    }
