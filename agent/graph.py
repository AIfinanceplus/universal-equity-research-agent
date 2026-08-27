from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.types import RetryPolicy

from agent.schemas import ResearchState
from agent.nodes import (
    planner_node,
    research_dispatch_node,
    fundamentals_node,
    market_data_node,
    competition_node,
    risk_node,
    merge_evidence_node,
    assumption_builder_node,
    valuation_node,
    verification_node,
    critic_node,
    success_final_node,
    insufficient_final_node,
    route_after_critic,
)
from agent.strategy_nodes import (
    strategy_metrics_node,
    graham_screen_node,
    buffett_screen_node,
    lynch_screen_node,
    fisher_screen_node,
    greenblatt_screen_node,
    hohn_screen_node,
    druckenmiller_screen_node,
    tepper_screen_node,
    klarman_screen_node,
    ackman_smith_screen_node,
    strategy_screening_hub_node,
)


def is_transient_error(error: Exception):
    name = error.__class__.__name__.lower()
    text = str(error).lower()
    signals = [
        "ratelimit", "rate limit", "429", "connection", "timeout",
        "timed out", "temporarily unavailable", "502", "503", "504",
    ]
    return any(signal in name or signal in text for signal in signals)


api_retry_policy = RetryPolicy(
    initial_interval=12.0,
    backoff_factor=2.0,
    max_interval=30.0,
    max_attempts=3,
    jitter=True,
    retry_on=is_transient_error,
)


STRATEGY_NODES = (
    "strategy_graham",
    "strategy_buffett",
    "strategy_lynch",
    "strategy_fisher",
    "strategy_greenblatt",
    "strategy_hohn",
    "strategy_druckenmiller",
    "strategy_tepper",
    "strategy_klarman",
    "strategy_ackman_smith",
)


def build_graph(checkpointer=None):
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node, retry_policy=api_retry_policy)
    builder.add_node("research_dispatch", research_dispatch_node)
    builder.add_node("fundamentals", fundamentals_node, retry_policy=api_retry_policy)
    builder.add_node("market_data", market_data_node, retry_policy=api_retry_policy)
    builder.add_node("competition", competition_node, retry_policy=api_retry_policy)
    builder.add_node("risk", risk_node, retry_policy=api_retry_policy)

    builder.add_node("retry_fundamentals", fundamentals_node, retry_policy=api_retry_policy)
    builder.add_node("retry_market_data", market_data_node, retry_policy=api_retry_policy)
    builder.add_node("retry_competition", competition_node, retry_policy=api_retry_policy)
    builder.add_node("retry_risk", risk_node, retry_policy=api_retry_policy)

    builder.add_node("merge", merge_evidence_node)

    # Strategy layer: one shared SEC metric-enrichment node, then ten pure-Python
    # investor screens in parallel, followed by one fan-in summary hub.
    builder.add_node("strategy_metrics", strategy_metrics_node, retry_policy=api_retry_policy)
    builder.add_node("strategy_graham", graham_screen_node)
    builder.add_node("strategy_buffett", buffett_screen_node)
    builder.add_node("strategy_lynch", lynch_screen_node)
    builder.add_node("strategy_fisher", fisher_screen_node)
    builder.add_node("strategy_greenblatt", greenblatt_screen_node)
    builder.add_node("strategy_hohn", hohn_screen_node)
    builder.add_node("strategy_druckenmiller", druckenmiller_screen_node)
    builder.add_node("strategy_tepper", tepper_screen_node)
    builder.add_node("strategy_klarman", klarman_screen_node)
    builder.add_node("strategy_ackman_smith", ackman_smith_screen_node)
    builder.add_node("strategy_screening_hub", strategy_screening_hub_node)

    builder.add_node("assumption_builder", assumption_builder_node, retry_policy=api_retry_policy)
    builder.add_node("valuation", valuation_node)
    builder.add_node("verification", verification_node)
    builder.add_node("critic", critic_node, retry_policy=api_retry_policy)
    builder.add_node("success_final", success_final_node, retry_policy=api_retry_policy)
    builder.add_node("insufficient_final", insufficient_final_node, retry_policy=api_retry_policy)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "research_dispatch")

    for node in ("fundamentals", "market_data", "competition", "risk"):
        builder.add_edge("research_dispatch", node)

    builder.add_edge(
        ["fundamentals", "market_data", "competition", "risk"],
        "merge",
    )

    for retry_node in (
        "retry_fundamentals",
        "retry_market_data",
        "retry_competition",
        "retry_risk",
    ):
        builder.add_edge(retry_node, "merge")

    builder.add_edge("merge", "strategy_metrics")

    for node in STRATEGY_NODES:
        builder.add_edge("strategy_metrics", node)

    builder.add_edge(list(STRATEGY_NODES), "strategy_screening_hub")
    builder.add_edge("strategy_screening_hub", "assumption_builder")

    builder.add_edge("assumption_builder", "valuation")
    builder.add_edge("valuation", "verification")
    builder.add_edge("verification", "critic")
    builder.add_conditional_edges("critic", route_after_critic)

    builder.add_edge("success_final", END)
    builder.add_edge("insufficient_final", END)

    return builder.compile(checkpointer=checkpointer)
