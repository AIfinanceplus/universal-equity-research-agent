from __future__ import annotations

from agent.schemas import ResearchState
from agent.yahoo_financials import fetch_yahoo_financial_snapshot


def _merge_sources(old_sources, new_sources):
    result, seen = [], set()
    for source in list(old_sources or []) + list(new_sources or []):
        url = source.get("url", "") if isinstance(source, dict) else ""
        if url and url not in seen:
            seen.add(url)
            result.append(source)
    return result


def fundamentals_node(state: ResearchState):
    print("\n>>> YAHOO FINANCIAL DATA NODE START")

    yahoo = fetch_yahoo_financial_snapshot(state["ticker"])
    selected = yahoo["selected"]
    annual = yahoo["annual"]
    ttm = yahoo["ttm"]

    revenue = float(selected.get("revenue_usd_b") or 0)
    ocf = float(selected.get("operating_cash_flow_usd_b") or 0)
    capex = float(selected.get("capex_usd_b") or 0)
    fcf_value = selected.get("free_cash_flow_usd_b")
    fcf = float(fcf_value) if fcf_value is not None else 0.0

    annual_revenue = float(annual.get("revenue_usd_b") or 0)
    annual_ocf = float(annual.get("operating_cash_flow_usd_b") or 0)
    annual_capex = float(annual.get("capex_usd_b") or 0)
    annual_fcf_value = annual.get("free_cash_flow_usd_b")
    annual_fcf = float(annual_fcf_value) if annual_fcf_value is not None else 0.0

    ttm_revenue = float(ttm.get("revenue_usd_b") or 0)
    ttm_ocf = float(ttm.get("operating_cash_flow_usd_b") or 0)
    ttm_capex = float(ttm.get("capex_usd_b") or 0)
    ttm_fcf_value = ttm.get("free_cash_flow_usd_b")
    ttm_fcf = float(ttm_fcf_value) if ttm_fcf_value is not None else 0.0

    basis = yahoo["financial_basis"]
    period = yahoo["financial_period"]
    shares = float(yahoo.get("shares_outstanding") or 0)

    snapshot = {
        "provider": "Yahoo Finance via yfinance",
        "source_url": yahoo["source_url"],
        "source_quality": yahoo["source_quality"],
        "annual": annual,
        "ttm": ttm,
        "selected": selected,
        "valid": yahoo.get("valid", False),
        "errors": yahoo.get("errors", []),
        "valuation_basis": basis,
        "notes": yahoo.get("notes", ""),
    }

    report = (
        "Yahoo Finance financial statements via yfinance. "
        f"Basis={basis}; Period={period}; "
        f"Revenue=${revenue:.3f}B; OCF=${ocf:.3f}B; "
        f"CapEx=${capex:.3f}B; FCF=${fcf:.3f}B; "
        f"Errors={yahoo.get('errors', [])}."
    )

    return {
        "fundamentals_report": report,
        "fundamentals_sources": _merge_sources(
            state.get("fundamentals_sources", []),
            yahoo.get("sources", []),
        ),
        "financial_snapshot": snapshot,
        "shares_outstanding": shares,
        "annual_revenue": annual_revenue,
        "annual_operating_cash_flow": annual_ocf,
        "annual_capex": annual_capex,
        "annual_free_cash_flow": annual_fcf,
        "annual_fiscal_year": str(annual.get("period_end") or ""),
        "latest_ytd_revenue": 0.0,
        "latest_ytd_operating_cash_flow": 0.0,
        "latest_ytd_capex": 0.0,
        "latest_ytd_period": "",
        "latest_ytd_months": 0,
        "prior_ytd_revenue": 0.0,
        "prior_ytd_operating_cash_flow": 0.0,
        "prior_ytd_capex": 0.0,
        "prior_ytd_period": "",
        "prior_ytd_months": 0,
        "ttm_revenue": ttm_revenue,
        "ttm_operating_cash_flow": ttm_ocf,
        "ttm_capex": ttm_capex,
        "ttm_free_cash_flow": ttm_fcf,
        "ttm_period": period if basis == "TTM" else "",
        "revenue": revenue,
        "operating_cash_flow": ocf,
        "capex": capex,
        "free_cash_flow": fcf,
        "financial_basis": basis,
        "financial_period": period,
    }
