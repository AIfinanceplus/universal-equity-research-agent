from __future__ import annotations

from copy import deepcopy
import re
from datetime import date

from bs4 import BeautifulSoup

from . import sec_data as base


# Capture the original implementation before agent.__init__ installs this
# compatibility wrapper onto agent.sec_data.load_sec_financial_snapshot.
_ORIGINAL_LOAD = base.load_sec_financial_snapshot


def _parse_money_token(token: str) -> float | None:
    text = str(token or "").strip()
    if not text or text in {"-", "—", "–"}:
        return None
    if text.endswith("%"):
        return None

    negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.replace(",", "")
        .replace("$", "")
        .replace("(", "")
        .replace(")", "")
        .replace("−", "-")
        .replace("—", "-")
        .replace("–", "-")
        .strip()
    )
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -abs(value) if negative else value


def _row_numeric_values(row) -> list[float]:
    values: list[float] = []
    cells = row.find_all(["td", "th"])
    for cell in cells:
        text = " ".join(cell.stripped_strings)
        # SEC tables often split '$' and the number into separate cells.
        # Only collect cells that actually contain at least one digit.
        if not re.search(r"\d", text):
            continue
        # Keep a single monetary/decimal token from each cell. Years in a
        # target data row are unusual and are filtered by the row-label logic.
        match = re.search(
            r"\(?\$?\s*-?\d[\d,]*(?:\.\d+)?\)?%?",
            text,
        )
        if not match:
            continue
        value = _parse_money_token(match.group(0))
        if value is not None:
            values.append(value)
    return values


def _header_years(rows: list, row_index: int) -> list[int]:
    best: list[int] = []
    # Financial tables usually put the period years in one of the last few
    # header rows immediately above the first data row.
    start = max(0, row_index - 8)
    for candidate in rows[start:row_index]:
        text = " ".join(candidate.stripped_strings)
        years = [int(x) for x in re.findall(r"\b20\d{2}\b", text)]
        if len(years) > len(best):
            best = years
    return best


def _unit_multiplier(text: str) -> float:
    lowered = text.lower()
    if "in billions" in lowered:
        return 1_000_000_000.0
    if "in millions" in lowered:
        return 1_000_000.0
    if "in thousands" in lowered:
        return 1_000.0
    return 1.0


def _table_context_text(table) -> str:
    pieces: list[str] = []
    current = table
    for _ in range(10):
        current = current.find_previous()
        if current is None:
            break
        text = " ".join(getattr(current, "stripped_strings", [])).strip()
        if text:
            pieces.append(text)
        if sum(len(x) for x in pieces) > 2500:
            break
    return " ".join(reversed(pieces))


def _pick_annual_value(
    table,
    row,
    rows: list,
    row_index: int,
    target_year: int,
) -> float | None:
    years = _header_years(rows, row_index)
    if target_year not in years:
        return None

    values = _row_numeric_values(row)
    if not values:
        return None

    # Pair the first N numeric row values with the period-year header. SEC
    # tables may append change/% columns after the period values; those are
    # intentionally ignored. If the target year appears twice (e.g. interim
    # 2025 plus FY2025), the last occurrence corresponds to the annual group.
    if len(values) < len(years):
        return None
    indices = [i for i, year in enumerate(years) if year == target_year]
    if not indices:
        return None
    index = indices[-1]
    if index >= len(values):
        return None

    table_text = " ".join(table.stripped_strings)
    return values[index] * _unit_multiplier(table_text)


def _parse_registration_html_annual_companyfacts(
    html: str,
    filing: dict,
    quarterly_target: dict | None,
) -> dict:
    """Parse a conservative annual Revenue/OCF/CapEx baseline from S-1 HTML.

    Some IPO registration statements contain audited financial tables as
    ordinary HTML rather than company-level iXBRL. This parser only accepts
    tables that explicitly expose a "Year Ended" period and maps row values to
    the visible year header. It does not use LLM extraction.
    """

    soup = BeautifulSoup(html, "html.parser")
    cutoff = base._to_date((quarterly_target or {}).get("report_date"))
    target_year = (cutoff.year - 1) if cutoff else (date.today().year - 1)

    candidates: dict[str, list[tuple[int, float]]] = {
        "revenue": [],
        "ocf": [],
        "capex": [],
    }

    for table in soup.find_all("table"):
        table_text = " ".join(table.stripped_strings)
        lower_table = table_text.lower()
        if "year ended" not in lower_table:
            continue

        rows = table.find_all("tr")
        if not rows:
            continue

        context = (_table_context_text(table) + " " + table_text[:2500]).lower()

        for index, row in enumerate(rows):
            row_text = " ".join(row.stripped_strings)
            normalized = re.sub(r"\s+", " ", row_text).strip().lower()
            if not normalized:
                continue

            metric = None
            score = 0

            if re.match(r"^(total\s+)?revenue\b", normalized):
                metric = "revenue"
                # Prefer consolidated statements over segment tables. If the
                # filing lacks explicit wording, the later tie-breaker favors
                # the larger consolidated value.
                if "consolidated results of operations" in context:
                    score += 6
                if "consolidated statements of operations" in context:
                    score += 6
                if "net income" in lower_table or "net loss" in lower_table:
                    score += 3
                if any(word in context for word in (
                    "segment results space",
                    "segment results connectivity",
                    "segment results ai",
                )):
                    score -= 2

            elif "net cash provided by operating activities" in normalized:
                metric = "ocf"
                score += 5
                if "statement of cash flows" in context:
                    score += 4

            elif re.match(r"^total\s+capital\s+expenditures\b", normalized):
                metric = "capex"
                score += 5
                if "capital expenditures" in context:
                    score += 2

            if metric is None:
                continue

            value = _pick_annual_value(
                table,
                row,
                rows,
                index,
                target_year,
            )
            if value is None:
                continue

            candidates[metric].append((score, abs(float(value))))

    selected: dict[str, float] = {}
    for metric, rows in candidates.items():
        if not rows:
            continue
        # Highest semantic score first, then largest amount. The second
        # criterion is especially useful for distinguishing consolidated
        # revenue from individual segment revenue when table headings are
        # sparse in old-style SEC HTML.
        selected[metric] = max(rows, key=lambda item: (item[0], item[1]))[1]

    if not all(key in selected for key in ("revenue", "ocf", "capex")):
        return {"facts": {}}

    start = f"{target_year}-01-01"
    end = f"{target_year}-12-31"
    filed = filing.get("filing_date", "")
    form = filing.get("form", "")
    accn = filing.get("accession", "")

    def fact(value: float) -> dict:
        return {
            "val": value,
            "start": start,
            "end": end,
            "filed": filed,
            "form": form,
            "accn": accn,
        }

    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [fact(selected["revenue"])]}
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": [fact(selected["ocf"])]}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": [fact(selected["capex"])]}
                },
            }
        }
    }


def _merge_companyfacts(primary: dict, extra: dict) -> dict:
    merged = deepcopy(primary)
    target_facts = merged.setdefault("facts", {})
    for namespace, concepts in (extra.get("facts", {}) or {}).items():
        ns = target_facts.setdefault(namespace, {})
        for concept, payload in concepts.items():
            destination = ns.setdefault(concept, {"units": {}})
            destination_units = destination.setdefault("units", {})
            for unit, facts in (payload.get("units", {}) or {}).items():
                destination_units.setdefault(unit, []).extend(deepcopy(facts))
    return merged


def _build_registration_snapshot(ticker: str) -> dict:
    identity = base.resolve_cik(ticker)
    cik, cik_int = identity["cik"], identity["cik_int"]
    submissions = base.get_submissions(cik)
    companyfacts = base.get_companyfacts(cik)
    targets = base.filing_targets(submissions)
    quarterly_target = targets.get("quarterly")
    registration = targets.get("registration")

    if not registration:
        raise RuntimeError(
            "No annual financial baseline found in SEC periodic reports or IPO registration statements"
        )

    registration_url = base._filing_document_url(cik_int, registration)
    if not registration_url:
        raise RuntimeError("SEC registration statement primary document is unavailable")

    html = base._get_text(registration_url)

    registration_facts = base._parse_inline_registration_companyfacts(
        html,
        registration,
    )
    annual_target = base._registration_annual_target(
        registration_facts,
        quarterly_target,
    )
    annual_source = "registration_statement_inline_xbrl"

    if not annual_target:
        registration_facts = _parse_registration_html_annual_companyfacts(
            html,
            registration,
            quarterly_target,
        )
        annual_target = base._registration_annual_target(
            registration_facts,
            quarterly_target,
        )
        annual_source = "registration_statement_html_table"

    if not annual_target:
        raise RuntimeError(
            "SEC registration statement found, but audited annual Revenue/OCF/CapEx could not be parsed"
        )

    combined = _merge_companyfacts(companyfacts, registration_facts)
    targets["annual"] = annual_target
    targets["annual_source"] = annual_source

    revenue = base._select_metric(
        combined,
        base.REVENUE_CONCEPTS,
        cik_int,
        annual_target,
        quarterly_target,
    )
    ocf = base._select_metric(
        combined,
        base.OCF_CONCEPTS,
        cik_int,
        annual_target,
        quarterly_target,
    )
    capex = base._select_metric(
        combined,
        base.CAPEX_CONCEPTS,
        cik_int,
        annual_target,
        quarterly_target,
        True,
    )

    shares = base._latest_shares(companyfacts, cik_int)
    if not shares or float(shares.get("shares", 0) or 0) <= 0:
        shares = base._cover_shares(cik_int, quarterly_target or registration)

    ar = base._value_b(revenue, "annual")
    ao = base._value_b(ocf, "annual")
    ac = base._value_b(capex, "annual")
    cr = base._value_b(revenue, "current_ytd")
    co = base._value_b(ocf, "current_ytd")
    cc = base._value_b(capex, "current_ytd")
    pr = base._value_b(revenue, "prior_ytd")
    po = base._value_b(ocf, "prior_ytd")
    pc = base._value_b(capex, "prior_ytd")

    tr = base._ttm(ar, cr, pr)
    to = base._ttm(ao, co, po)
    tc = base._ttm(ac, cc, pc)
    afcf = ao - ac if ao is not None and ac is not None else None
    tfcf = to - tc if to is not None and tc is not None else None
    latest_months = base._months(revenue.get("current_ytd"))
    prior_months = base._months(revenue.get("prior_ytd"))

    errors: list[str] = []
    required = {
        "annual_revenue": ar,
        "annual_ocf": ao,
        "annual_capex": ac,
        "latest_ytd_revenue": cr,
        "latest_ytd_ocf": co,
        "latest_ytd_capex": cc,
        "prior_ytd_revenue": pr,
        "prior_ytd_ocf": po,
        "prior_ytd_capex": pc,
    }
    errors += [
        f"Missing SEC structured input: {key}"
        for key, value in required.items()
        if value is None
    ]
    errors += base._period_alignment([revenue, ocf, capex])

    expected_annual = annual_target["report_date"]
    for name, metric in (("Revenue", revenue), ("OCF", ocf), ("CapEx", capex)):
        actual = (metric.get("annual") or {}).get("end")
        if actual != expected_annual:
            errors.append(
                f"{name} annual stale/mismatched: expected {expected_annual}, got {actual}"
            )

    if quarterly_target:
        expected_q = quarterly_target["report_date"]
        for name, metric in (("Revenue", revenue), ("OCF", ocf), ("CapEx", capex)):
            actual = (metric.get("current_ytd") or {}).get("end")
            if actual != expected_q:
                errors.append(
                    f"{name} current YTD stale/mismatched: expected {expected_q}, got {actual}"
                )

    ttm_valid = (
        not errors
        and latest_months > 0
        and latest_months == prior_months
        and None not in (tr, to, tc, tfcf)
    )

    companyfacts_url = f"{base.SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    submissions_url = f"{base.SEC_BASE}/submissions/CIK{cik}.json"
    sources = [
        {"title": "SEC EDGAR Company Facts", "url": companyfacts_url},
        {"title": "SEC EDGAR Submissions", "url": submissions_url},
        {"title": "SEC IPO Registration Statement", "url": registration_url},
    ]
    seen = {source["url"] for source in sources}
    for metric_name, metric in (
        ("Revenue", revenue),
        ("Operating Cash Flow", ocf),
        ("CapEx", capex),
    ):
        for period in ("annual", "current_ytd", "prior_ytd"):
            item = metric.get(period)
            url = (item or {}).get("filing_url", "")
            if url and url not in seen:
                seen.add(url)
                sources.append({
                    "title": f"SEC {metric_name} {period} {(item or {}).get('end')}",
                    "url": url,
                })

    def concept(metric: dict, period: str):
        item = metric.get(period)
        return item.get("concept") if item else None

    return {
        "provider": "SEC EDGAR",
        "company_name": (
            companyfacts.get("entityName")
            or submissions.get("name")
            or identity["title"]
        ),
        "ticker": ticker.upper(),
        "cik": cik,
        "cik_int": cik_int,
        "period_targets": targets,
        "companyfacts_url": companyfacts_url,
        "submissions_url": submissions_url,
        "revenue_metric": revenue,
        "ocf_metric": ocf,
        "capex_metric": capex,
        "shares": shares,
        "annual": {
            "revenue_usd_b": ar,
            "operating_cash_flow_usd_b": ao,
            "capex_usd_b": ac,
            "free_cash_flow_usd_b": afcf,
            "period_end": (revenue.get("annual") or {}).get("end"),
            "filing_date": (revenue.get("annual") or {}).get("filed"),
            "revenue_concept": concept(revenue, "annual"),
            "ocf_concept": concept(ocf, "annual"),
            "capex_concept": concept(capex, "annual"),
        },
        "latest_ytd": {
            "revenue_usd_b": cr,
            "operating_cash_flow_usd_b": co,
            "capex_usd_b": cc,
            "period_start": (revenue.get("current_ytd") or {}).get("start"),
            "period_end": (revenue.get("current_ytd") or {}).get("end"),
            "months": latest_months,
            "revenue_concept": concept(revenue, "current_ytd"),
            "ocf_concept": concept(ocf, "current_ytd"),
            "capex_concept": concept(capex, "current_ytd"),
        },
        "prior_ytd": {
            "revenue_usd_b": pr,
            "operating_cash_flow_usd_b": po,
            "capex_usd_b": pc,
            "period_start": (revenue.get("prior_ytd") or {}).get("start"),
            "period_end": (revenue.get("prior_ytd") or {}).get("end"),
            "months": prior_months,
            "revenue_concept": concept(revenue, "prior_ytd"),
            "ocf_concept": concept(ocf, "prior_ytd"),
            "capex_concept": concept(capex, "prior_ytd"),
        },
        "ttm": {
            "revenue_usd_b": tr,
            "operating_cash_flow_usd_b": to,
            "capex_usd_b": tc,
            "free_cash_flow_usd_b": tfcf,
            "period_end": (revenue.get("current_ytd") or {}).get("end"),
        },
        "ttm_valid": ttm_valid,
        "periods_aligned": not base._period_alignment([revenue, ocf, capex]),
        "errors": errors,
        "sources": sources,
    }


def load_sec_financial_snapshot(ticker: str) -> dict:
    """Run the standard SEC selector, then fall back for newly public issuers."""

    try:
        return _ORIGINAL_LOAD(ticker)
    except RuntimeError as exc:
        message = str(exc)
        if (
            "No annual financial baseline" not in message
            and "No current annual filing target" not in message
        ):
            raise
    return _build_registration_snapshot(ticker)
