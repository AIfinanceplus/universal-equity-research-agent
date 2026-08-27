import json
import sys
from agent.sec_data import load_sec_financial_snapshot


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "META"
    result = load_sec_financial_snapshot(ticker)
    print("\n==============================")
    print("SEC DATA SMOKE TEST")
    print("==============================")
    print("Company:", result["company_name"])
    print("Ticker:", result["ticker"])
    print("CIK:", result["cik"])
    print("\nSEC filing targets:")
    print(json.dumps(result["period_targets"], indent=2))
    print("\nAnnual:")
    print(json.dumps(result["annual"], indent=2))
    print("\nLatest YTD:")
    print(json.dumps(result["latest_ytd"], indent=2))
    print("\nPrior comparable YTD:")
    print(json.dumps(result["prior_ytd"], indent=2))
    print("\nTTM:")
    print(json.dumps(result["ttm"], indent=2))
    print("\nShares:")
    print(json.dumps(result.get("shares"), indent=2))
    print("\nPeriods aligned:", result["periods_aligned"])
    print("TTM valid:", result["ttm_valid"])
    print("Errors:", result["errors"])


if __name__ == "__main__":
    main()
