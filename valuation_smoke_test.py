from agent.valuation import run_valuation_engine
from agent.verification import run_deterministic_verification


def assumptions():
    return {
        "basis": "TTM",
        "bear": {"fcf_growth_rate": 0.03, "discount_rate": 0.11, "exit_multiple": 14.0, "rationale": "Conservative growth and multiple contraction.", "evidence": ["Current FCF is positive.", "Bear case assumes slower growth."]},
        "base": {"fcf_growth_rate": 0.07, "discount_rate": 0.09, "exit_multiple": 18.0, "rationale": "Moderate growth with stable economics.", "evidence": ["Current FCF is positive.", "Base case uses middle parameters."]},
        "bull": {"fcf_growth_rate": 0.11, "discount_rate": 0.08, "exit_multiple": 22.0, "rationale": "Higher growth and stronger terminal economics.", "evidence": ["Current FCF is positive.", "Bull case assumes stronger growth."]},
    }


def verify(period):
    a = assumptions()
    valuation = run_valuation_engine(revenue=200.0, free_cash_flow=50.0, market_cap=1000.0, assumptions=a)
    verification = run_deterministic_verification(
        revenue=200.0, free_cash_flow=50.0, market_cap=1000.0,
        financial_basis="TTM", financial_period=period,
        market_snapshot={"status": "verified", "as_of_date": "2026-08-26", "source_url": "https://example.com/market"},
        evidence_completeness=0.95, valuation_result=valuation, assumptions=a, source_count=8,
    )
    return valuation, verification


def main():
    valuation, verification = verify("TTM through 2026-06-30")
    assert valuation["valid"] is True
    assert verification["passed"] is True, verification
    assert verification["math_failures"] == []
    print("PASS: current TTM + current market date + full valuation math.")

    _, stale = verify("TTM through 2018-09-30")
    assert stale["passed"] is False
    assert any("过旧" in failure for failure in stale["data_failures"])
    print("PASS: stale 2018 TTM is deterministically rejected.")


if __name__ == "__main__":
    main()
