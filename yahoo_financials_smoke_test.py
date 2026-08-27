import pandas as pd

from agent.yahoo_financials import _period_payload


def main():
    column = pd.Timestamp("2026-06-30")
    income = pd.DataFrame(
        {column: [23_044_000_000]},
        index=["Total Revenue"],
    )
    cashflow = pd.DataFrame(
        {column: [9_900_000_000, -42_248_000_000]},
        index=["Operating Cash Flow", "Capital Expenditure"],
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

    print("PASS: Yahoo financial normalization computes deterministic OCF - CapEx FCF.")


if __name__ == "__main__":
    main()
