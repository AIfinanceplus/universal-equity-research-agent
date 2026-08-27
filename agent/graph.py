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


def is_transient_error(
    error: Exception,
):
    name = (
        error.__class__.__name__
        .lower()
    )

    text = (
        str(error)
        .lower()
    )

    signals = [
        "ratelimit",
        "rate limit",
        "429",
        "connection",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "502",
        "503",
        "504",
    ]

    return any(
        signal in name
        or
        signal in text
        for signal
        in signals
    )


api_retry_policy = RetryPolicy(
    initial_interval=12.0,
    backoff_factor=2.0,
    max_interval=30.0,
    max_attempts=3,
    jitter=True,
    retry_on=is_transient_error,
)


def build_graph(
    checkpointer=None,
):
    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "planner",
        planner_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "research_dispatch",
        research_dispatch_node,
    )

    builder.add_node(
        "fundamentals",
        fundamentals_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "market_data",
        market_data_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "competition",
        competition_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "risk",
        risk_node,
        retry_policy=
            api_retry_policy,
    )

    # Dedicated retry aliases keep targeted retries separate from the
    # initial four-way fan-out. This lets the initial research use a true
    # join barrier while a single owner node can still re-enter Evidence Hub.
    builder.add_node(
        "retry_fundamentals",
        fundamentals_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "retry_market_data",
        market_data_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "retry_competition",
        competition_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "retry_risk",
        risk_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "merge",
        merge_evidence_node,
    )

    builder.add_node(
        "assumption_builder",
        assumption_builder_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "valuation",
        valuation_node,
    )

    builder.add_node(
        "verification",
        verification_node,
    )

    builder.add_node(
        "critic",
        critic_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "success_final",
        success_final_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_node(
        "insufficient_final",
        insufficient_final_node,
        retry_policy=
            api_retry_policy,
    )

    builder.add_edge(
        START,
        "planner",
    )

    builder.add_edge(
        "planner",
        "research_dispatch",
    )

    builder.add_edge(
        "research_dispatch",
        "fundamentals",
    )

    builder.add_edge(
        "research_dispatch",
        "market_data",
    )

    builder.add_edge(
        "research_dispatch",
        "competition",
    )

    builder.add_edge(
        "research_dispatch",
        "risk",
    )

    # True fan-in barrier: Evidence Hub runs once, only after all four
    # initial research owners have completed.
    builder.add_edge(
        [
            "fundamentals",
            "market_data",
            "competition",
            "risk",
        ],
        "merge",
    )

    # A targeted retry is already a complete correction round, so it may
    # re-enter the Evidence Hub directly without waiting for unrelated nodes.
    for retry_node in (
        "retry_fundamentals",
        "retry_market_data",
        "retry_competition",
        "retry_risk",
    ):
        builder.add_edge(
            retry_node,
            "merge",
        )

    builder.add_edge(
        "merge",
        "assumption_builder",
    )

    builder.add_edge(
        "assumption_builder",
        "valuation",
    )

    builder.add_edge(
        "valuation",
        "verification",
    )

    builder.add_edge(
        "verification",
        "critic",
    )

    builder.add_conditional_edges(
        "critic",
        route_after_critic,
    )

    builder.add_edge(
        "success_final",
        END,
    )

    builder.add_edge(
        "insufficient_final",
        END,
    )

    return builder.compile(
        checkpointer=
            checkpointer
    )
