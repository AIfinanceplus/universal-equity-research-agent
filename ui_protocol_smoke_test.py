from agent.ui_protocol import GRAPH_EDGES, NODE_META, graph_metadata


def main():
    meta = graph_metadata()
    node_ids = [node["id"] for node in NODE_META]

    assert len(node_ids) == len(set(node_ids)), "Duplicate node id"

    required = {
        "resolver", "planner", "research_dispatch", "fundamentals",
        "market_data", "competition", "risk", "merge",
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
        ("typed_router", "retry_risk"),
        ("typed_router", "assumption_builder"),
        ("typed_router", "insufficient_final"),
    }:
        assert pair in edge_pairs

    assert all(edge.get("channels") for edge in GRAPH_EDGES)
    assert any("information" in edge["channels"] for edge in GRAPH_EDGES)
    assert any("logic" in edge["channels"] for edge in GRAPH_EDGES)
    assert any("decision" in edge["channels"] for edge in GRAPH_EDGES)

    assert all(
        {"x", "y", "description", "inputs", "outputs"}.issubset(node)
        for node in NODE_META
    )
    assert meta["canvas"]["height"] > 1200

    print(
        "PASS: UI protocol exposes node-level graph, information flow, "
        "logic flow and decision flow."
    )


if __name__ == "__main__":
    main()
