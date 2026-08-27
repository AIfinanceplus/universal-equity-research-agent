from __future__ import annotations

from agent.strategy_screening import (
    STRATEGIES,
    build_strategy_metrics,
    evaluate_strategy,
)


def strategy_metrics_node(state: dict):
    print("\n=== STRATEGY METRICS NODE ===")
    metrics = build_strategy_metrics(state)
    return {"strategy_metrics": metrics}


def _screen(state: dict, name: str, key: str):
    result = evaluate_strategy(name, state.get("strategy_metrics", {}))
    print(f"STRATEGY {name}: {result['verdict']} coverage={result['coverage']:.2f}")
    return {key: result}


def graham_screen_node(state: dict):
    return _screen(state, "graham", "strategy_graham")


def buffett_screen_node(state: dict):
    return _screen(state, "buffett", "strategy_buffett")


def lynch_screen_node(state: dict):
    return _screen(state, "lynch", "strategy_lynch")


def fisher_screen_node(state: dict):
    return _screen(state, "fisher", "strategy_fisher")


def greenblatt_screen_node(state: dict):
    return _screen(state, "greenblatt", "strategy_greenblatt")


def hohn_screen_node(state: dict):
    return _screen(state, "hohn", "strategy_hohn")


def druckenmiller_screen_node(state: dict):
    return _screen(state, "druckenmiller", "strategy_druckenmiller")


def tepper_screen_node(state: dict):
    return _screen(state, "tepper", "strategy_tepper")


def klarman_screen_node(state: dict):
    return _screen(state, "klarman", "strategy_klarman")


def ackman_smith_screen_node(state: dict):
    return _screen(state, "ackman_smith", "strategy_ackman_smith")


def strategy_screening_hub_node(state: dict):
    results = {
        "graham": state.get("strategy_graham", {}),
        "buffett": state.get("strategy_buffett", {}),
        "lynch": state.get("strategy_lynch", {}),
        "fisher": state.get("strategy_fisher", {}),
        "greenblatt": state.get("strategy_greenblatt", {}),
        "hohn": state.get("strategy_hohn", {}),
        "druckenmiller": state.get("strategy_druckenmiller", {}),
        "tepper": state.get("strategy_tepper", {}),
        "klarman": state.get("strategy_klarman", {}),
        "ackman_smith": state.get("strategy_ackman_smith", {}),
    }

    verdict_counts = {}
    for result in results.values():
        verdict = result.get("verdict", "INSUFFICIENT_DATA")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    ranked = sorted(
        results.values(),
        key=lambda item: (
            item.get("counts", {}).get("fail", 0),
            -item.get("counts", {}).get("pass", 0),
            -item.get("coverage", 0.0),
        ),
    )

    summary = {
        "results": results,
        "verdict_counts": verdict_counts,
        "best_matches": [
            {
                "strategy": item.get("strategy"),
                "title": item.get("title"),
                "verdict": item.get("verdict"),
                "coverage": item.get("coverage"),
                "pass": item.get("counts", {}).get("pass", 0),
                "fail": item.get("counts", {}).get("fail", 0),
                "unknown": item.get("counts", {}).get("unknown", 0),
            }
            for item in ranked[:5]
        ],
        "methodology": (
            "Rules are the user-supplied strategy criteria. "
            "PASS/FAIL is deterministic where data is available. "
            "UNKNOWN is used instead of guessing when the system lacks a reliable field."
        ),
    }

    return {"strategy_screening": summary}
