from agent.ui_protocol import GRAPH_EDGES, NODE_META, graph_metadata


def main():
    meta = graph_metadata()
    node_ids = [node["id"] for node in NODE_META]

    assert len(node_ids) == len(set(node_ids)), "Duplicate node id"

    required = {
        "resolver", "planner", "research_dispatch", "fundamentals",
        "market_data", "competition", "risk", "merge", "strategy_metrics",
        "strategy_graham", "strategy_buffett", "strategy_lynch",
        "strategy_fisher", "strategy_greenblatt", "strategy_hohn",
        "strategy_druckenmiller", "strategy_tepper", "strategy_klarman",
        "strategy_ackman_smith", "strategy_screening_hub",
        "assumption_builder", "valuation", "verification", "critic",
        "typed_router", "retry_fundamentals", "retry_market_data",
        "retry_competition", "retry_risk", "success_final",
        "insufficient_final",
    }
    assert required.issubset(set(node_ids))

    edge_pairs = {(edge["source"], edge["target"]) for edge in GRAPH_EDGES}
    for pair in {
        ("fundamentals", "merge"),
        ("market_data", "merge"),
        ("competition", "merge"),
        ("risk", "merge"),
        ("merge", "strategy_metrics"),
        ("strategy_metrics", "strategy_graham"),
        ("strategy_metrics", "strategy_ackman_smith"),
        ("strategy_graham", "strategy_screening_hub"),
        ("strategy_ackman_smith", "strategy_screening_hub"),
        ("strategy_screening_hub", "assumption_builder"),
        ("typed_router", "retry_risk"),
        ("typed_router", "assumption_builder"),
        ("typed_router", "insufficient_final"),
    }:
        assert pair in edge_pairs, pair

    assert all(edge.get("channels") for edge in GRAPH_EDGES)
    assert any("information" in edge["channels"] for edge in GRAPH_EDGES)
    assert any("logic" in edge["channels"] for edge in GRAPH_EDGES)
    assert any("decision" in edge["channels"] for edge in GRAPH_EDGES)

    assert all(
        {"x", "y", "description", "inputs", "outputs"}.issubset(node)
        for node in NODE_META
    )
    assert meta["canvas"]["height"] > 2000
    assert meta["canvas"]["width"] >= 1800

    print(
        "PASS: UI protocol exposes node-level research, ten investor screens, "
        "information flow, logic flow and decision flow."
    )


if __name__ == "__main__":
    main()
