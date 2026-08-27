from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SEC_BASE = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "sec"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
LOCK = threading.Lock()
LAST_REQUEST_AT = 0.0
MIN_INTERVAL_SECONDS = 0.15
TIMEOUT_SECONDS = 25

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
QUARTERLY_FORMS = {"10-Q", "10-Q/A"}
REGISTRATION_FORMS = {"S-1", "S-1/A", "F-1", "F-1/A"}
REVENUE_CONCEPTS = [
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "Revenues"),
    ("us-gaap", "SalesRevenueNet"),
    ("us-gaap", "SalesRevenueGoodsNet"),
    ("us-gaap", "SalesRevenueServicesNet"),
    ("ifrs-full", "Revenue"),
]
OCF_CONCEPTS = [
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
]
CAPEX_CONCEPTS = [
    ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
    ("us-gaap", "PaymentsForAdditionsToPropertyPlantAndEquipment"),
    ("us-gaap", "PaymentsToAcquireProductiveAssets"),
    ("ifrs-full", "PurchaseOfPropertyPlantAndEquipment"),
]
SHARES_CONCEPTS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
]


def _user_agent() -> str:
    value = os.getenv("SEC_USER_AGENT", "").strip()
    if not value:
        raise RuntimeError(
            "SEC_USER_AGENT is missing. Add a real contact to .env, e.g. "
            "SEC_USER_AGENT=YourName your.email@example.com"
        )
    return value


def _headers():
    return {
        "User-Agent": _user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json,text/plain,*/*",
    }


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key.replace('/', '_').replace(':', '_')}.json"


def _get_json(url: str, *, cache_key: str, max_age_seconds: int):
    path = _cache_path(cache_key)
    if path.exists() and time.time() - path.stat().st_mtime <= max_age_seconds:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    global LAST_REQUEST_AT
    last_error = None
    for attempt in range(4):
        try:
            with LOCK:
                wait = MIN_INTERVAL_SECONDS - (time.monotonic() - LAST_REQUEST_AT)
                if wait > 0:
                    time.sleep(wait)
                response = SESSION.get(url, headers=_headers(), timeout=TIMEOUT_SECONDS)
                LAST_REQUEST_AT = time.monotonic()
            if response.status_code == 200:
                payload = response.json()
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                return payload
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = RuntimeError(f"SEC HTTP {response.status_code}")
                time.sleep(min(8, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(f"SEC HTTP {response.status_code}: {response.text[:300]}")
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(min(8, 1.5 * (2 ** attempt)))
    raise RuntimeError(f"SEC request failed after retries: {last_error}")


def _get_text(url: str) -> str:
    global LAST_REQUEST_AT
    last_error = None
    for attempt in range(4):
        try:
            with LOCK:
                wait = MIN_INTERVAL_SECONDS - (time.monotonic() - LAST_REQUEST_AT)
                if wait > 0:
                    time.sleep(wait)
                response = SESSION.get(url, headers=_headers(), timeout=TIMEOUT_SECONDS)
                LAST_REQUEST_AT = time.monotonic()
            if response.status_code == 200:
                return response.text
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = RuntimeError(f"SEC HTTP {response.status_code}")
                time.sleep(min(8, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(f"SEC HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(min(8, 1.5 * (2 ** attempt)))
    raise RuntimeError(f"SEC filing request failed after retries: {last_error}")


def get_company_tickers():
    return _get_json(
        f"{SEC_WWW}/files/company_tickers.json",
        cache_key="company_tickers",
        max_age_seconds=86400,
    )


def _ticker_key(value: str) -> str:
    return value.strip().upper().replace(".", "-").replace("/", "-")


def resolve_cik(ticker: str) -> dict:
    wanted = _ticker_key(ticker)
    for row in get_company_tickers().values():
        if _ticker_key(row.get("ticker", "")) == wanted:
            cik_int = int(row["cik_str"])
            return {
                "ticker": row.get("ticker", ticker),
                "title": row.get("title", ""),
                "cik_int": cik_int,
                "cik": str(cik_int).zfill(10),
            }
    raise ValueError(f"Ticker {ticker} not found in SEC ticker mapping")


def get_submissions(cik: str):
    return _get_json(
        f"{SEC_BASE}/submissions/CIK{cik}.json",
        cache_key=f"submissions_{cik}",
        max_age_seconds=900,
    )


def get_companyfacts(cik: str):
    return _get_json(
        f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json",
        cache_key=f"companyfacts_{cik}",
        max_age_seconds=900,
    )


def filing_index_url(cik_int: int, accession: str) -> str:
    if not accession:
        return ""
    compact = accession.replace("-", "")
    return f"{SEC_WWW}/Archives/edgar/data/{cik_int}/{compact}/{accession}-index.html"


def _submission_rows(submissions: dict) -> list[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    rows = []
    for i, form in enumerate(forms):
        def field(name):
            values = recent.get(name, [])
            return values[i] if i < len(values) else ""
        rows.append({
            "form": form,
            "report_date": field("reportDate"),
            "filing_date": field("filingDate"),
            "accession": field("accessionNumber"),
            "primary_document": field("primaryDocument"),
        })
    return rows


def _latest_filing(rows: list[dict], forms: set[str]) -> dict | None:
    candidates = [r for r in rows if r.get("form") in forms and r.get("report_date")]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda r: (
            r.get("report_date", ""),
            r.get("filing_date", ""),
            1 if not str(r.get("form", "")).endswith("/A") else 0,
        ),
    )


def filing_targets(submissions: dict) -> dict:
    rows = _submission_rows(submissions)
    annual = _latest_filing(rows, ANNUAL_FORMS)
    quarters = [r for r in rows if r.get("form") in QUARTERLY_FORMS and r.get("report_date")]
    if annual:
        quarters = [r for r in quarters if r["report_date"] > annual["report_date"]]
    quarterly = _latest_filing(quarters, QUARTERLY_FORMS) if quarters else None
    return {
        "annual": annual,
        "quarterly": quarterly,
        "annual_source": "periodic_report" if annual else "",
    }


def _to_date(value: str | None):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _duration(fact: dict):
    start, end = _to_date(fact.get("start")), _to_date(fact.get("end"))
    return (end - start).days if start and end else None


def _unit_facts(companyfacts: dict, namespace: str, concept: str, unit: str) -> list[dict]:
    concept_data = companyfacts.get("facts", {}).get(namespace, {}).get(concept)
    if not concept_data:
        return []
    units = concept_data.get("units", {})
    raw = units.get(unit)
    if raw is None:
        raw = next((v for v in units.values() if isinstance(v, list)), [])
    out = []
    for fact in raw:
        if isinstance(fact, dict) and "val" in fact:
            item = dict(fact)
            item["_namespace"] = namespace
            item["_concept"] = concept
            out.append(item)
    return out


def _candidate_facts(companyfacts: dict, concepts: list[tuple[str, str]], unit: str) -> list[dict]:
    out = []
    for priority, (namespace, concept) in enumerate(concepts):
        for fact in _unit_facts(companyfacts, namespace, concept, unit):
            fact["_priority"] = priority
            out.append(fact)
    return out


def _registration_annual_target(
    companyfacts: dict,
    quarterly_target: dict | None = None,
) -> dict | None:
    """Find the newest complete audited-style annual period in an IPO registration statement.

    Newly public issuers can have a valid S-1/F-1 with audited historical annual
    financials before they have filed their first 10-K/20-F. Company Facts preserves
    those registration-statement XBRL facts, so use the latest annual period that is
    simultaneously available for Revenue, OCF and CapEx.
    """

    metric_sets = []
    cutoff = _to_date((quarterly_target or {}).get("report_date"))

    for concepts in (REVENUE_CONCEPTS, OCF_CONCEPTS, CAPEX_CONCEPTS):
        by_end: dict[str, list[dict]] = {}

        for fact in _candidate_facts(companyfacts, concepts, "USD"):
            if fact.get("form") not in REGISTRATION_FORMS:
                continue

            duration = _duration(fact)
            end = _to_date(fact.get("end"))

            if duration is None or not 270 <= duration <= 430 or not end:
                continue

            if cutoff and end >= cutoff:
                continue

            by_end.setdefault(fact.get("end", ""), []).append(fact)

        metric_sets.append(by_end)

    if not metric_sets or any(not item for item in metric_sets):
        return None

    common_ends = set(metric_sets[0])
    for item in metric_sets[1:]:
        common_ends &= set(item)

    if not common_ends:
        return None

    report_date = max(common_ends)
    candidate_facts = [
        fact
        for item in metric_sets
        for fact in item.get(report_date, [])
    ]

    if not candidate_facts:
        return None

    anchor = max(
        candidate_facts,
        key=lambda fact: (
            fact.get("filed", ""),
            int(str(fact.get("form", "")).endswith("/A")),
            int(bool(fact.get("accn"))),
            -int(fact.get("_priority", 999)),
        ),
    )

    return {
        "form": anchor.get("form", ""),
        "report_date": report_date,
        "filing_date": anchor.get("filed", ""),
        "accession": anchor.get("accn", ""),
        "primary_document": "",
        "source": "registration_statement",
    }


def _select_annual(facts: list[dict], target: dict):
    candidates = []
    allowed_forms = set(ANNUAL_FORMS)
    if target.get("source") == "registration_statement":
        allowed_forms |= REGISTRATION_FORMS

    for fact in facts:
        if fact.get("end") != target["report_date"] or fact.get("form") not in allowed_forms:
            continue
        duration = _duration(fact)
        if duration is None or not 270 <= duration <= 430:
            continue
        candidates.append((
            int(fact.get("accn") == target.get("accession")),
            fact.get("filed", ""),
            int(str(fact.get("form", "")).endswith("/A")),
            -int(fact.get("_priority", 999)),
            fact,
        ))
    return max(candidates, default=(None, None, None, None, None))[-1]


def _select_current_ytd(facts: list[dict], target: dict):
    candidates = []
    for fact in facts:
        if fact.get("end") != target["report_date"] or fact.get("form") not in QUARTERLY_FORMS:
            continue
        duration = _duration(fact)
        if duration is None or not 60 <= duration <= 310:
            continue
        candidates.append((
            int(fact.get("accn") == target.get("accession")),
            duration,
            fact.get("filed", ""),
            -int(fact.get("_priority", 999)),
            fact,
        ))
    return max(candidates, default=(None, None, None, None, None))[-1]


def _select_prior_ytd(facts: list[dict], current: dict | None, target_accession: str):
    if not current:
        return None
    current_end, current_duration = _to_date(current.get("end")), _duration(current)
    if not current_end or current_duration is None:
        return None
    candidates = []
    for fact in facts:
        if fact.get("form") not in QUARTERLY_FORMS:
            continue
        end, duration = _to_date(fact.get("end")), _duration(fact)
        if not end or duration is None or end >= current_end:
            continue
        year_gap = (current_end - end).days
        duration_gap = abs(duration - current_duration)
        if not 330 <= year_gap <= 400 or duration_gap > 35:
            continue
        candidates.append((
            int(fact.get("accn") == target_accession),
            int(fact.get("_namespace") == current.get("_namespace")),
            int(fact.get("_concept") == current.get("_concept")),
            -(abs(year_gap - 365) + 2 * duration_gap),
            fact.get("filed", ""),
            -int(fact.get("_priority", 999)),
            fact,
        ))
    return max(candidates, default=(None,) * 7)[-1]


def _payload(fact: dict | None, cik_int: int, normalize_abs: bool = False):
    if not fact:
        return None
    value = float(fact["val"])
    if normalize_abs:
        value = abs(value)
    return {
        "value": value,
        "value_usd_b": value / 1_000_000_000,
        "start": fact.get("start"),
        "end": fact.get("end"),
        "filed": fact.get("filed"),
        "form": fact.get("form"),
        "fy": fact.get("fy"),
        "fp": fact.get("fp"),
        "frame": fact.get("frame"),
        "accession": fact.get("accn", ""),
        "concept": fact.get("_concept"),
        "namespace": fact.get("_namespace"),
        "filing_url": filing_index_url(cik_int, fact.get("accn", "")),
    }


def _select_metric(companyfacts: dict, concepts, cik_int: int, annual_target: dict, quarterly_target: dict | None, normalize_abs=False):
    facts = _candidate_facts(companyfacts, concepts, "USD")
    annual = _select_annual(facts, annual_target)
    current = _select_current_ytd(facts, quarterly_target) if quarterly_target else None
    prior = _select_prior_ytd(facts, current, quarterly_target.get("accession", "")) if quarterly_target else None
    return {
        "annual": _payload(annual, cik_int, normalize_abs),
        "current_ytd": _payload(current, cik_int, normalize_abs),
        "prior_ytd": _payload(prior, cik_int, normalize_abs),
    }


def _latest_shares(companyfacts: dict, cik_int: int):
    facts = _candidate_facts(companyfacts, SHARES_CONCEPTS, "shares")
    candidates = [
        f for f in facts
        if f.get("form") in (ANNUAL_FORMS | QUARTERLY_FORMS | REGISTRATION_FORMS) and _to_date(f.get("end"))
    ]
    if not candidates:
        return None
    fact = max(candidates, key=lambda f: (f.get("end", ""), f.get("filed", ""), -int(f.get("_priority", 999))))
    payload = _payload(fact, cik_int)
    payload["shares"] = payload.pop("value")
    payload.pop("value_usd_b", None)
    payload["method"] = "companyfacts"
    return payload


def _filing_document_url(cik_int: int, filing: dict | None) -> str:
    if not filing or not filing.get("accession") or not filing.get("primary_document"):
        return ""
    compact = filing["accession"].replace("-", "")
    return f"{SEC_WWW}/Archives/edgar/data/{cik_int}/{compact}/{filing['primary_document']}"


def _cover_shares(cik_int: int, filing: dict | None):
    url = _filing_document_url(cik_int, filing)
    if not url:
        return None
    text = " ".join(BeautifulSoup(_get_text(url), "html.parser").stripped_strings)
    pattern = re.compile(
        r'(Class\s+[A-Z0-9]+\s+Common\s+Stock|Common\s+Stock)'
        r'.{0,500}?(\d{1,3}(?:,\d{3}){2,})\s+shares\s+outstanding\s+as\s+of',
        re.IGNORECASE,
    )
    rows, seen = [], set()
    for label, shares_text in pattern.findall(text):
        row = (" ".join(label.split()), int(shares_text.replace(",", "")))
        if row in seen:
            continue
        seen.add(row)
        rows.append({"class": row[0], "shares": float(row[1])})
    if not rows:
        return None
    return {
        "shares": sum(r["shares"] for r in rows),
        "method": "sec_filing_cover_sum",
        "classes": rows,
        "filing_url": url,
        "end": filing.get("report_date"),
        "filed": filing.get("filing_date"),
        "form": filing.get("form"),
    }


def _value_b(metric: dict, period: str):
    item = metric.get(period)
    return float(item["value_usd_b"]) if item else None


def _ttm(annual, current, prior):
    return annual + current - prior if None not in (annual, current, prior) else None


def _months(item: dict | None):
    if not item:
        return 0
    start, end = _to_date(item.get("start")), _to_date(item.get("end"))
    if not start or not end:
        return 0
    return max(1, min(4, round((end - start).days / 91.25))) * 3


def _period_alignment(metrics: list[dict]):
    errors = []
    for period in ("annual", "current_ytd", "prior_ytd"):
        ends = [m[period]["end"] for m in metrics if m.get(period)]
        if len(ends) != len(metrics):
            errors.append(f"Missing metric period: {period}")
        elif len(set(ends)) != 1:
            errors.append(f"Cross-metric period mismatch for {period}: {ends}")
    return errors


def load_sec_financial_snapshot(ticker: str) -> dict:
    identity = resolve_cik(ticker)
    cik, cik_int = identity["cik"], identity["cik_int"]
    submissions = get_submissions(cik)
    companyfacts = get_companyfacts(cik)
    targets = filing_targets(submissions)
    annual_target, quarterly_target = targets["annual"], targets["quarterly"]

    if not annual_target:
        annual_target = _registration_annual_target(companyfacts, quarterly_target)
        if annual_target:
            targets["annual"] = annual_target
            targets["annual_source"] = "registration_statement"

    if not annual_target:
        raise RuntimeError(
            "No annual financial baseline found in SEC periodic reports or IPO registration statements"
        )

    revenue = _select_metric(companyfacts, REVENUE_CONCEPTS, cik_int, annual_target, quarterly_target)
    ocf = _select_metric(companyfacts, OCF_CONCEPTS, cik_int, annual_target, quarterly_target)
    capex = _select_metric(companyfacts, CAPEX_CONCEPTS, cik_int, annual_target, quarterly_target, True)
    shares = _latest_shares(companyfacts, cik_int)
    if not shares or float(shares.get("shares", 0) or 0) <= 0:
        shares = _cover_shares(cik_int, quarterly_target or annual_target)

    ar, ao, ac = _value_b(revenue, "annual"), _value_b(ocf, "annual"), _value_b(capex, "annual")
    cr, co, cc = _value_b(revenue, "current_ytd"), _value_b(ocf, "current_ytd"), _value_b(capex, "current_ytd")
    pr, po, pc = _value_b(revenue, "prior_ytd"), _value_b(ocf, "prior_ytd"), _value_b(capex, "prior_ytd")
    tr, to, tc = _ttm(ar, cr, pr), _ttm(ao, co, po), _ttm(ac, cc, pc)
    afcf = ao - ac if ao is not None and ac is not None else None
    tfcf = to - tc if to is not None and tc is not None else None
    latest_months, prior_months = _months(revenue.get("current_ytd")), _months(revenue.get("prior_ytd"))

    errors = []
    required = {"annual_revenue": ar, "annual_ocf": ao, "annual_capex": ac,
                "latest_ytd_revenue": cr, "latest_ytd_ocf": co, "latest_ytd_capex": cc,
                "prior_ytd_revenue": pr, "prior_ytd_ocf": po, "prior_ytd_capex": pc}
    errors += [f"Missing SEC XBRL input: {k}" for k, v in required.items() if v is None]
    errors += _period_alignment([revenue, ocf, capex])
    expected_annual = annual_target["report_date"]
    for name, metric in (("Revenue", revenue), ("OCF", ocf), ("CapEx", capex)):
        actual = (metric.get("annual") or {}).get("end")
        if actual != expected_annual:
            errors.append(f"{name} annual stale/mismatched: expected {expected_annual}, got {actual}")
    if quarterly_target:
        expected_q = quarterly_target["report_date"]
        for name, metric in (("Revenue", revenue), ("OCF", ocf), ("CapEx", capex)):
            actual = (metric.get("current_ytd") or {}).get("end")
            if actual != expected_q:
                errors.append(f"{name} current YTD stale/mismatched: expected {expected_q}, got {actual}")

    ttm_valid = (
        not errors
        and latest_months > 0
        and latest_months == prior_months
        and None not in (tr, to, tc, tfcf)
    )
    companyfacts_url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    submissions_url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    sources = [
        {"title": "SEC EDGAR Company Facts", "url": companyfacts_url},
        {"title": "SEC EDGAR Submissions", "url": submissions_url},
    ]
    seen = {s["url"] for s in sources}
    for metric_name, metric in (("Revenue", revenue), ("Operating Cash Flow", ocf), ("CapEx", capex)):
        for period in ("annual", "current_ytd", "prior_ytd"):
            item = metric.get(period)
            if item and item.get("filing_url") and item["filing_url"] not in seen:
                seen.add(item["filing_url"])
                sources.append({"title": f"SEC {metric_name} {period} {item.get('end')}", "url": item["filing_url"]})

    def summary_item(metric, period):
        item = metric.get(period)
        return item.get("concept") if item else None

    return {
        "provider": "SEC EDGAR",
        "company_name": companyfacts.get("entityName") or submissions.get("name") or identity["title"],
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
            "revenue_usd_b": ar, "operating_cash_flow_usd_b": ao, "capex_usd_b": ac,
            "free_cash_flow_usd_b": afcf,
            "period_end": (revenue.get("annual") or {}).get("end"),
            "filing_date": (revenue.get("annual") or {}).get("filed"),
            "revenue_concept": summary_item(revenue, "annual"),
            "ocf_concept": summary_item(ocf, "annual"),
            "capex_concept": summary_item(capex, "annual"),
        },
        "latest_ytd": {
            "revenue_usd_b": cr, "operating_cash_flow_usd_b": co, "capex_usd_b": cc,
            "period_start": (revenue.get("current_ytd") or {}).get("start"),
            "period_end": (revenue.get("current_ytd") or {}).get("end"),
            "months": latest_months,
            "revenue_concept": summary_item(revenue, "current_ytd"),
            "ocf_concept": summary_item(ocf, "current_ytd"),
            "capex_concept": summary_item(capex, "current_ytd"),
        },
        "prior_ytd": {
            "revenue_usd_b": pr, "operating_cash_flow_usd_b": po, "capex_usd_b": pc,
            "period_start": (revenue.get("prior_ytd") or {}).get("start"),
            "period_end": (revenue.get("prior_ytd") or {}).get("end"),
            "months": prior_months,
            "revenue_concept": summary_item(revenue, "prior_ytd"),
            "ocf_concept": summary_item(ocf, "prior_ytd"),
            "capex_concept": summary_item(capex, "prior_ytd"),
        },
        "ttm": {
            "revenue_usd_b": tr, "operating_cash_flow_usd_b": to, "capex_usd_b": tc,
            "free_cash_flow_usd_b": tfcf,
            "period_end": (revenue.get("current_ytd") or {}).get("end"),
        },
        "ttm_valid": ttm_valid,
        "periods_aligned": not _period_alignment([revenue, ocf, capex]),
        "errors": errors,
        "sources": sources,
    }
