from pathlib import Path


def main():
    text = Path("agent/graph.py").read_text(encoding="utf-8")
    assert '"retry_fundamentals"' in text
    assert '"retry_market_data"' in text
    assert '"retry_competition"' in text
    assert '"retry_risk"' in text
    assert '[\n            "fundamentals",\n            "market_data",\n            "competition",\n            "risk",\n        ],\n        "merge",' in text
    assert 'builder.add_edge(\n            retry_node,\n            "merge",' in text
    print("PASS: initial research uses one four-way join and targeted retries use separate aliases.")


if __name__ == "__main__":
    main()
