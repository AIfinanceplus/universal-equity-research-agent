import pandas as pd

from agent.yahoo_financials import _period_payload


def main():
    column = pd.Timestamp("2026-06-30")

    # yfinance get_* methods default to pretty=False, so production row names
    # commonly arrive in compact CamelCase form.
    income = pd.DataFrame(
        {column: [23_044_000_000]},
        index=["TotalRevenue"],
    )
    cashflow = pd.DataFrame(
        {column: [9_900_000_000, -42_248_000_000]},
        index=["OperatingCashFlow", "CapitalExpenditure"],
    )

    result = _period_payload(
        income=income,
        cashflow=cashflow,
        basis="TTM",
    )

    assert result["period_end"] == "2026-06-30"
    assert result["revenue_usd_b"] == 23.044
    assert result["operating_cash_flow_usd_b"] == 9.9
    assert result["capex_usd_b"] == 42.248
    assert result["free_cash_flow_usd_b"] == -32.348

    # Pretty labels must remain compatible too.
    income_pretty = pd.DataFrame(
        {column: [23_044_000_000]},
        index=["Total Revenue"],
    )
    cashflow_pretty = pd.DataFrame(
        {column: [9_900_000_000, -42_248_000_000]},
        index=["Operating Cash Flow", "Capital Expenditure"],
    )
    pretty = _period_payload(
        income=income_pretty,
        cashflow=cashflow_pretty,
        basis="TTM",
    )
    assert pretty["revenue_usd_b"] == 23.044
    assert pretty["operating_cash_flow_usd_b"] == 9.9
    assert pretty["capex_usd_b"] == 42.248

    print(
        "PASS: Yahoo financial normalization handles compact and pretty row "
        "names and computes deterministic OCF - CapEx FCF."
    )


if __name__ == "__main__":
    main()
