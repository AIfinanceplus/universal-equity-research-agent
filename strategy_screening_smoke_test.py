from agent.strategy_screening import evaluate_strategy


def base_metrics():
    return {
        "revenue_usd_b": 100.0,
        "current_ratio": 2.5,
        "long_term_debt_usd_b": 5.0,
        "net_current_assets_usd_b": 10.0,
        "net_income_positive_years": 10,
        "dividend_positive_years": 18,
        "pe_3yr_avg_eps": 12.0,
        "pb": 1.4,
        "price_usd": 100.0,
        "graham_number": 120.0,
        "roe_5y_avg": 0.20,
        "debt_to_equity": 0.30,
        "fcf_positive_years": 8,
        "net_margin": 0.18,
        "eps_cagr_5y": 0.18,
        "market_cap_usd_b": 500.0,
        "fcf_yield": 0.06,
        "peg": 0.8,
        "revenue_cagr_5y": 0.12,
        "rd_to_revenue": 0.08,
        "fcf_conversion_net_income": 0.90,
        "greenblatt_roc_proxy": 0.30,
        "greenblatt_earnings_yield_proxy": 0.08,
        "operating_margin": 0.25,
        "gross_margin": 0.50,
        "fcf_to_ebitda_proxy": 0.85,
        "fcf_cagr_5y": 0.08,
        "net_debt_to_fcf": 1.0,
        "interest_coverage": 20.0,
        "p_fcf": 20.0,
        "roce_proxy": 0.22,
        "capex_to_revenue": 0.05,
        "history_years": {
            "revenue": 10,
            "eps": 10,
            "net_income": 10,
            "fcf": 10,
            "dividends": 18,
        },
    }


def main():
    metrics = base_metrics()

    graham = evaluate_strategy("graham", metrics)
    assert graham["verdict"] == "PASS", graham
    assert graham["counts"]["fail"] == 0
    print("PASS: Graham screen can produce a full deterministic PASS.")

    buffett = evaluate_strategy("buffett", metrics)
    assert buffett["counts"]["pass"] >= 6
    assert any(rule["status"] == "unknown" for rule in buffett["rules"])
    print("PASS: Buffett screen preserves unavailable ROIC as UNKNOWN.")

    druck = evaluate_strategy("druckenmiller", metrics)
    assert druck["verdict"] == "INSUFFICIENT_DATA"
    assert druck["counts"]["unknown"] == len(druck["rules"])
    print("PASS: dynamic Druckenmiller fields are not hallucinated.")

    weak = dict(metrics)
    weak["fcf_yield"] = 0.01
    weak["debt_to_equity"] = 1.5
    buffett_fail = evaluate_strategy("buffett", weak)
    assert buffett_fail["verdict"] == "FAIL"
    assert buffett_fail["counts"]["fail"] >= 2
    print("PASS: deterministic threshold violations produce FAIL.")


if __name__ == "__main__":
    main()
