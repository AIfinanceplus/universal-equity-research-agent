def selected_concept(metric: dict) -> str:
    for period in ("current_ytd", "annual", "prior_ytd"):
        item = metric.get(period)
        if isinstance(item, dict) and item.get("concept"):
            return item["concept"]
    return ""


def main():
    metric = {
        "annual": {"concept": "RevenueFromContractWithCustomerExcludingAssessedTax", "end": "2025-12-31"},
        "current_ytd": {"concept": "RevenueFromContractWithCustomerExcludingAssessedTax", "end": "2026-06-30"},
        "prior_ytd": {"concept": "RevenueFromContractWithCustomerExcludingAssessedTax", "end": "2025-06-30"},
    }
    assert selected_concept(metric) == "RevenueFromContractWithCustomerExcludingAssessedTax"
    print("PASS: nested SEC metric concept schema is compatible.")


if __name__ == "__main__":
    main()
