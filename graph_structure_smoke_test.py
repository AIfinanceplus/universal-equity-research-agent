from pathlib import Path


def main():
    text = Path("agent/graph.py").read_text(encoding="utf-8")

    for name in (
        "retry_fundamentals",
        "retry_market_data",
        "retry_competition",
        "retry_risk",
        "strategy_metrics",
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
        "strategy_screening_hub",
    ):
        assert f'"{name}"' in text, name

    assert 'builder.add_edge(\n        ["fundamentals", "market_data", "competition", "risk"],\n        "merge",\n    )' in text
    assert 'builder.add_edge("merge", "strategy_metrics")' in text
    assert 'builder.add_edge(list(STRATEGY_NODES), "strategy_screening_hub")' in text
    assert 'builder.add_edge("strategy_screening_hub", "assumption_builder")' in text

    print(
        "PASS: research uses one four-way evidence join, then shared strategy metrics, "
        "ten parallel investor screens and one strategy-screening fan-in hub."
    )


if __name__ == "__main__":
    main()
