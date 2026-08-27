from __future__ import annotations

import re
from typing import Any

import yfinance as yf


YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{ticker}/"


def _is_empty(frame: Any) -> bool:
    try:
        return frame is None or frame.empty
    except Exception:
        return True


def _column_date(frame: Any) -> str:
    if _is_empty(frame):
        return ""
    try:
        column = frame.columns[0]
        if hasattr(column, "date"):
            return column.date().isoformat()
        text = str(column)
        return text[:10] if len(text) >= 10 else ""
    except Exception:
        return ""


def _canonical_label(value: Any) -> str:
    """Normalize Yahoo/yfinance row labels across pretty and compact modes.

    yfinance get_* financial methods default to pretty=False, so a row can be
    returned as either ``TotalRevenue`` or ``Total Revenue`` depending on which
    API/property produced the DataFrame. Matching on an alphanumeric canonical
    form makes both representations equivalent without fuzzy guessing.
    """

    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _available_rows(frame: Any, limit: int = 30) -> list[str]:
    if _is_empty(frame):
        return []
    try:
        return [str(label) for label in list(frame.index)[:limit]]
    except Exception:
        return []


def _row_value(frame: Any, aliases: tuple[str, ...]) -> float | None:
    if _is_empty(frame):
        return None

    try:
        index_map = {
            _canonical_label(label): label
            for label in frame.index
        }

        for alias in aliases:
            label = index_map.get(_canonical_label(alias))
            if label is None:
                continue

            row = frame.loc[label]
            value = row.iloc[0] if hasattr(row, "iloc") else row

            if value is None:
                continue

            number = float(value)
            if number != number:  # NaN
                continue

            return number

    except Exception:
        return None

    return None


def _positive(value: float | None) -> float | None:
    if value is None:
        return None
    return value if value > 0 else None


def _capex_abs(value: float | None) -> float | None:
    if value is None:
        return None
    return abs(float(value))


def _period_payload(
    *,
    income: Any,
    cashflow: Any,
    basis: str,
) -> dict:
    revenue = _positive(
        _row_value(
            income,
            (
                "Total Revenue",
                "TotalRevenue",
                "Operating Revenue",
                "OperatingRevenue",
                "Revenue",
            ),
        )
    )

    ocf = _row_value(
        cashflow,
        (
            "Operating Cash Flow",
            "OperatingCashFlow",
            "Total Cash From Operating Activities",
            "TotalCashFromOperatingActivities",
            "Cash Flow From Continuing Operating Activities",
            "CashFlowFromContinuingOperatingActivities",
        ),
    )

    capex = _capex_abs(
        _row_value(
            cashflow,
            (
                "Capital Expenditure",
                "CapitalExpenditure",
                "Capital Expenditures",
                "CapitalExpenditures",
                "Purchase Of PPE",
                "PurchaseOfPPE",
                "Purchases Of Property Plant And Equipment",
                "PurchasesOfPropertyPlantAndEquipment",
            ),
        )
    )

    fcf = None
    if ocf is not None and capex is not None:
        # Yahoo usually reports CapEx as a negative cash-flow line. Normalize
        # magnitude first, then recompute FCF deterministically.
        fcf = float(ocf) - float(capex)

    period_end = _column_date(income) or _column_date(cashflow)

    return {
        "basis": basis,
        "period_end": period_end,
        "revenue_usd_b": revenue / 1_000_000_000 if revenue is not None else None,
        "operating_cash_flow_usd_b": ocf / 1_000_000_000 if ocf is not None else None,
        "capex_usd_b": capex / 1_000_000_000 if capex is not None else None,
        "free_cash_flow_usd_b": fcf / 1_000_000_000 if fcf is not None else None,
        "income_rows": _available_rows(income),
        "cashflow_rows": _available_rows(cashflow),
    }


def _first_nonempty(*frames: Any):
    for frame in frames:
        if not _is_empty(frame):
            return frame
    return None


def _latest_annual(security: yf.Ticker) -> dict:
    income = None
    cashflow = None

    try:
        income = security.get_income_stmt(
            freq="yearly",
            pretty=False,
        )
    except Exception:
        pass

    if _is_empty(income):
        try:
            income = security.income_stmt
        except Exception:
            income = None

    try:
        cashflow = security.get_cashflow(
            freq="yearly",
            pretty=False,
        )
    except Exception:
        pass

    if _is_empty(cashflow):
        try:
            cashflow = security.cashflow
        except Exception:
            cashflow = None

    return _period_payload(
        income=income,
        cashflow=cashflow,
        basis="ANNUAL",
    )


def _ttm(security: yf.Ticker) -> dict:
    income = None
    cashflow = None

    # Income statement officially supports freq="trailing".
    try:
        income = security.get_income_stmt(
            freq="trailing",
            pretty=False,
        )
    except Exception:
        pass

    if _is_empty(income):
        try:
            income = security.ttm_income_stmt
        except Exception:
            income = None

    # get_cashflow documents yearly/quarterly frequencies; use the dedicated
    # TTM property for trailing cash flow instead of relying on an unsupported
    # freq="trailing" call.
    try:
        cashflow = security.ttm_cashflow
    except Exception:
        cashflow = None

    if _is_empty(cashflow):
        try:
            cashflow = security.ttm_cash_flow
        except Exception:
            cashflow = None

    return _period_payload(
        income=income,
        cashflow=cashflow,
        basis="TTM",
    )


def _shares_from_fast_info(security: yf.Ticker) -> float | None:
    try:
        fast = security.fast_info
        value = getattr(fast, "shares", None)
        if value is None:
            value = fast["shares"]
        number = float(value)
        return number if number > 0 else None
    except Exception:
        return None


def fetch_yahoo_financial_snapshot(ticker: str) -> dict:
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Empty ticker")

    security = yf.Ticker(symbol)
    ttm = _ttm(security)
    annual = _latest_annual(security)

    use_ttm = all(
        ttm.get(key) is not None
        for key in (
            "revenue_usd_b",
            "operating_cash_flow_usd_b",
            "capex_usd_b",
            "free_cash_flow_usd_b",
        )
    )

    selected = ttm if use_ttm else annual
    basis = "TTM" if use_ttm else "ANNUAL"
    period_end = str(selected.get("period_end") or "")

    errors: list[str] = []
    for field in (
        "revenue_usd_b",
        "operating_cash_flow_usd_b",
        "capex_usd_b",
        "free_cash_flow_usd_b",
    ):
        if selected.get(field) is None:
            errors.append(f"Missing Yahoo Finance field: {field}")

    source_url = YAHOO_QUOTE_URL.format(ticker=symbol)

    return {
        "provider": "Yahoo Finance via yfinance",
        "ticker": symbol,
        "company_name": "",
        "source_url": source_url,
        "source_quality": "secondary_non_official",
        "financial_basis": basis,
        "financial_period": (
            f"TTM through {period_end}"
            if basis == "TTM" and period_end
            else period_end
        ),
        "annual": annual,
        "ttm": ttm,
        "selected": selected,
        "shares_outstanding": _shares_from_fast_info(security),
        "valid": not errors,
        "errors": errors,
        "sources": [
            {
                "title": f"Yahoo Finance financials for {symbol}",
                "url": source_url,
                "provider": "Yahoo Finance via yfinance",
                "source_quality": "secondary_non_official",
            }
        ],
        "notes": (
            "Financial statements retrieved from Yahoo Finance via yfinance. "
            "Free cash flow is deterministically recomputed as operating cash "
            "flow minus absolute capital expenditure."
        ),
    }
