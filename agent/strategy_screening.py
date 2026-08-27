from __future__ import annotations

import math
from typing import Any, Callable

from agent.sec_data import get_companyfacts, resolve_cik


ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

CONCEPTS = {
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
    ],
    "net_income": [
        ("us-gaap", "NetIncomeLoss"),
        ("us-gaap", "ProfitLoss"),
    ],
    "operating_income": [
        ("us-gaap", "OperatingIncomeLoss"),
    ],
    "gross_profit": [
        ("us-gaap", "GrossProfit"),
    ],
    "current_assets": [("us-gaap", "AssetsCurrent")],
    "current_liabilities": [("us-gaap", "LiabilitiesCurrent")],
    "total_assets": [("us-gaap", "Assets")],
    "equity": [
        ("us-gaap", "StockholdersEquity"),
        ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    ],
    "long_term_debt": [
        ("us-gaap", "LongTermDebtNoncurrent"),
        ("us-gaap", "LongTermDebtAndFinanceLeaseObligationsNoncurrent"),
        ("us-gaap", "LongTermDebt"),
    ],
    "current_debt": [
        ("us-gaap", "LongTermDebtCurrent"),
        ("us-gaap", "ShortTermBorrowings"),
        ("us-gaap", "ShortTermDebtCurrent"),
    ],
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    ],
    "ppe_net": [("us-gaap", "PropertyPlantAndEquipmentNet")],
    "interest_expense": [
        ("us-gaap", "InterestExpenseNonOperating"),
        ("us-gaap", "InterestExpense"),
    ],
    "rd": [("us-gaap", "ResearchAndDevelopmentExpense")],
    "da": [
        ("us-gaap", "DepreciationDepletionAndAmortization"),
        ("us-gaap", "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment"),
    ],
    "ocf": [("us-gaap", "NetCashProvidedByUsedInOperatingActivities")],
    "capex": [
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ("us-gaap", "PaymentsForAdditionsToPropertyPlantAndEquipment"),
    ],
    "dividends": [
        ("us-gaap", "PaymentsOfDividends"),
        ("us-gaap", "PaymentsOfDividendsCommonStock"),
    ],
    "eps": [
        ("us-gaap", "EarningsPerShareDiluted"),
        ("us-gaap", "EarningsPerShareBasic"),
    ],
}

UNITS = {
    "eps": "USD/shares",
}


def _duration_days(fact: dict) -> int | None:
    start = fact.get("start")
    end = fact.get("end")
    if not start or not end:
        return None
    try:
        from datetime import date
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except Exception:
        return None


def _annual_series(companyfacts: dict, metric: str) -> list[dict]:
    candidates: list[dict] = []
    wanted_unit = UNITS.get(metric, "USD")

    for priority, (namespace, concept) in enumerate(CONCEPTS[metric]):
        data = companyfacts.get("facts", {}).get(namespace, {}).get(concept, {})
        units = data.get("units", {})
        raw = units.get(wanted_unit)
        if raw is None and units:
            raw = next((items for items in units.values() if isinstance(items, list)), [])

        for fact in raw or []:
            if fact.get("form") not in ANNUAL_FORMS:
                continue
            if fact.get("fp") not in {None, "", "FY"}:
                continue
            if "val" not in fact or not fact.get("end"):
                continue

            duration = _duration_days(fact)
            if duration is not None and not 280 <= duration <= 430:
                continue

            candidates.append({
                "end": str(fact.get("end")),
                "filed": str(fact.get("filed") or ""),
                "fy": fact.get("fy"),
                "value": float(fact["val"]),
                "concept": concept,
                "priority": priority,
            })

    by_end: dict[str, dict] = {}
    for item in candidates:
        current = by_end.get(item["end"])
        if current is None or (
            item["filed"], -item["priority"]
        ) > (
            current["filed"], -current["priority"]
        ):
            by_end[item["end"]] = item

    return sorted(by_end.values(), key=lambda item: item["end"])[-12:]


def _latest(series: list[dict]) -> float | None:
    return float(series[-1]["value"]) if series else None


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _cagr(series: list[dict], years: int = 5) -> float | None:
    if len(series) < years + 1:
        return None
    start = float(series[-(years + 1)]["value"])
    end = float(series[-1]["value"])
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _consecutive_positive_years(series: list[dict]) -> int:
    count = 0
    for item in reversed(series):
        if float(item["value"]) > 0:
            count += 1
        else:
            break
    return count


def _avg_ratio(numer: list[dict], denom: list[dict], years: int = 5) -> float | None:
    dmap = {item["end"]: float(item["value"]) for item in denom}
    vals = [
        float(item["value"]) / dmap[item["end"]]
        for item in numer
        if item["end"] in dmap and dmap[item["end"]] != 0
    ]
    vals = vals[-years:]
    return sum(vals) / len(vals) if vals else None


def _series_binary(a: list[dict], b: list[dict], fn: Callable[[float, float], float]) -> list[dict]:
    bmap = {item["end"]: float(item["value"]) for item in b}
    out = []
    for item in a:
        if item["end"] in bmap:
            out.append({"end": item["end"], "value": fn(float(item["value"]), bmap[item["end"]])})
    return out


def build_strategy_metrics(state: dict) -> dict[str, Any]:
    resolved = resolve_cik(state["ticker"])
    companyfacts = get_companyfacts(resolved["cik"])
    series = {name: _annual_series(companyfacts, name) for name in CONCEPTS}

    revenue = series["revenue"]
    net_income = series["net_income"]
    operating_income = series["operating_income"]
    equity = series["equity"]
    ocf = series["ocf"]
    capex = series["capex"]
    fcf_series = _series_binary(ocf, capex, lambda x, y: x - abs(y))

    latest_revenue = _latest(revenue)
    latest_net_income = _latest(net_income)
    latest_operating_income = _latest(operating_income)
    latest_equity = _latest(equity)
    current_assets = _latest(series["current_assets"])
    current_liabilities = _latest(series["current_liabilities"])
    long_term_debt = _latest(series["long_term_debt"])
    current_debt = _latest(series["current_debt"]) or 0.0
    total_debt = (long_term_debt or 0.0) + current_debt if long_term_debt is not None or current_debt else None
    cash = _latest(series["cash"])
    ppe = _latest(series["ppe_net"])
    total_assets = _latest(series["total_assets"])
    interest = _latest(series["interest_expense"])
    rd = _latest(series["rd"])
    da = _latest(series["da"])
    gross_profit = _latest(series["gross_profit"])
    latest_fcf = _latest(fcf_series)
    latest_eps = _latest(series["eps"])

    market_cap_b = float(state.get("market_cap") or 0.0)
    market_cap = market_cap_b * 1_000_000_000 if market_cap_b > 0 else None
    price = float(state.get("market_price") or 0.0) or None
    shares = float(state.get("shares_outstanding") or 0.0) or None

    bvps = _safe_div(latest_equity, shares)
    pe = _safe_div(price, latest_eps)
    eps3 = None
    if len(series["eps"]) >= 3:
        eps3 = sum(float(x["value"]) for x in series["eps"][-3:]) / 3
    pe_3yr_avg_eps = _safe_div(price, eps3)
    pb = _safe_div(price, bvps)
    graham_number = None
    if latest_eps is not None and bvps is not None and latest_eps > 0 and bvps > 0:
        graham_number = math.sqrt(22.5 * latest_eps * bvps)

    current_ratio = _safe_div(current_assets, current_liabilities)
    net_current_assets = (
        current_assets - current_liabilities
        if current_assets is not None and current_liabilities is not None
        else None
    )
    debt_to_equity = _safe_div(total_debt, latest_equity)
    net_margin = _safe_div(latest_net_income, latest_revenue)
    operating_margin = _safe_div(latest_operating_income, latest_revenue)
    gross_margin = _safe_div(gross_profit, latest_revenue)
    roe_5y_avg = _avg_ratio(net_income, equity, 5)
    revenue_cagr_5y = _cagr(revenue, 5)
    eps_cagr_5y = _cagr(series["eps"], 5)
    fcf_cagr_5y = _cagr(fcf_series, 5)
    fcf_conversion_net_income = _safe_div(latest_fcf, latest_net_income)
    capex_to_revenue = _safe_div(abs(_latest(capex) or 0.0), latest_revenue)
    rd_to_revenue = _safe_div(rd, latest_revenue)
    interest_coverage = _safe_div(latest_operating_income, interest)

    enterprise_value = None
    if market_cap is not None:
        enterprise_value = market_cap + (total_debt or 0.0) - (cash or 0.0)

    greenblatt_ey_proxy = _safe_div(latest_operating_income, enterprise_value)
    greenblatt_roc_proxy = None
    if latest_operating_income is not None and ppe is not None and net_current_assets is not None:
        greenblatt_roc_proxy = _safe_div(latest_operating_income, ppe + net_current_assets)

    roce_proxy = None
    if latest_operating_income is not None and total_assets is not None and current_liabilities is not None:
        roce_proxy = _safe_div(latest_operating_income, total_assets - current_liabilities)

    ebitda_proxy = (
        latest_operating_income + da
        if latest_operating_income is not None and da is not None
        else None
    )
    fcf_to_ebitda = _safe_div(latest_fcf, ebitda_proxy)
    net_debt_to_fcf = None
    if latest_fcf not in {None, 0}:
        net_debt_to_fcf = ((total_debt or 0.0) - (cash or 0.0)) / latest_fcf

    p_fcf = None
    fcf_yield = None
    if market_cap is not None and latest_fcf not in {None, 0}:
        p_fcf = market_cap / latest_fcf
        fcf_yield = latest_fcf / market_cap

    peg = None
    if pe is not None and eps_cagr_5y is not None and eps_cagr_5y > 0:
        peg = pe / (eps_cagr_5y * 100)

    dividends_years = _consecutive_positive_years(series["dividends"])
    net_income_positive_years = _consecutive_positive_years(net_income)
    fcf_positive_years = _consecutive_positive_years(fcf_series)

    return {
        "provider": "SEC EDGAR Company Facts + canonical market snapshot",
        "companyfacts_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{resolved['cik']}.json",
        "as_of_market_date": state.get("market_cap_date", ""),
        "market_cap_usd_b": market_cap_b if market_cap_b > 0 else None,
        "price_usd": price,
        "revenue_usd_b": latest_revenue / 1e9 if latest_revenue is not None else None,
        "current_ratio": current_ratio,
        "net_current_assets_usd_b": net_current_assets / 1e9 if net_current_assets is not None else None,
        "long_term_debt_usd_b": long_term_debt / 1e9 if long_term_debt is not None else None,
        "debt_to_equity": debt_to_equity,
        "net_margin": net_margin,
        "operating_margin": operating_margin,
        "gross_margin": gross_margin,
        "roe_5y_avg": roe_5y_avg,
        "revenue_cagr_5y": revenue_cagr_5y,
        "eps_cagr_5y": eps_cagr_5y,
        "fcf_cagr_5y": fcf_cagr_5y,
        "fcf_conversion_net_income": fcf_conversion_net_income,
        "fcf_to_ebitda_proxy": fcf_to_ebitda,
        "capex_to_revenue": capex_to_revenue,
        "rd_to_revenue": rd_to_revenue,
        "interest_coverage": interest_coverage,
        "roce_proxy": roce_proxy,
        "greenblatt_roc_proxy": greenblatt_roc_proxy,
        "greenblatt_earnings_yield_proxy": greenblatt_ey_proxy,
        "p_fcf": p_fcf,
        "fcf_yield": fcf_yield,
        "pe": pe,
        "pe_3yr_avg_eps": pe_3yr_avg_eps,
        "pb": pb,
        "peg": peg,
        "eps_latest": latest_eps,
        "eps_3yr_avg": eps3,
        "bvps": bvps,
        "graham_number": graham_number,
        "net_income_positive_years": net_income_positive_years,
        "dividend_positive_years": dividends_years,
        "fcf_positive_years": fcf_positive_years,
        "net_debt_to_fcf": net_debt_to_fcf,
        "history_years": {
            "revenue": len(revenue),
            "eps": len(series["eps"]),
            "net_income": len(net_income),
            "fcf": len(fcf_series),
            "dividends": len(series["dividends"]),
        },
        "notes": [
            "ROCE, Greenblatt ROC and Earnings Yield are accounting proxies based on SEC concepts.",
            "Historical P/E percentile, analyst revisions, relative strength, catalysts, liquidation value and qualitative management/moat tests are not inferred from SEC data.",
        ],
    }


def _rule(rule_id: str, label: str, status: str, actual: Any = None, threshold: str = "", note: str = "") -> dict:
    return {
        "id": rule_id,
        "label": label,
        "status": status,
        "actual": actual,
        "threshold": threshold,
        "note": note,
    }


def _num_rule(rule_id: str, label: str, actual: float | None, predicate: Callable[[float], bool], threshold: str, note: str = "") -> dict:
    if actual is None:
        return _rule(rule_id, label, "unknown", None, threshold, note)
    return _rule(rule_id, label, "pass" if predicate(actual) else "fail", actual, threshold, note)


def _unknown(rule_id: str, label: str, note: str) -> dict:
    return _rule(rule_id, label, "unknown", None, "", note)


def _finalize(name: str, title: str, rules: list[dict]) -> dict:
    counts = {key: sum(1 for rule in rules if rule["status"] == key) for key in ("pass", "fail", "unknown")}
    known = counts["pass"] + counts["fail"]
    coverage = known / len(rules) if rules else 0.0
    if counts["fail"] > 0:
        verdict = "FAIL"
    elif coverage >= 0.75 and counts["unknown"] == 0:
        verdict = "PASS"
    elif coverage >= 0.35:
        verdict = "PARTIAL"
    else:
        verdict = "INSUFFICIENT_DATA"
    return {
        "strategy": name,
        "title": title,
        "verdict": verdict,
        "coverage": coverage,
        "counts": counts,
        "rules": rules,
    }


def evaluate_strategy(name: str, metrics: dict) -> dict:
    m = metrics

    if name == "graham":
        rules = [
            _num_rule("sales", "年销售额", m.get("revenue_usd_b"), lambda x: x >= 1, ">= $1B"),
            _num_rule("current_ratio", "流动比率", m.get("current_ratio"), lambda x: x >= 2, ">= 2.0"),
            _num_rule("debt_nca", "长期债务 <= 净流动资产", None if m.get("long_term_debt_usd_b") is None or m.get("net_current_assets_usd_b") is None else m["long_term_debt_usd_b"] - m["net_current_assets_usd_b"], lambda x: x <= 0, "long-term debt <= net current assets"),
            _num_rule("profit_10y", "过去10年每年净利润 > 0", m.get("net_income_positive_years"), lambda x: x >= 10, ">= 10 years"),
            _num_rule("dividends", "连续派息", m.get("dividend_positive_years"), lambda x: x >= 15, ">= 15 years"),
            _num_rule("pe3", "P/E（3年平均EPS）", m.get("pe_3yr_avg_eps"), lambda x: x <= 15, "<= 15"),
        ]
        pe3, pb = m.get("pe_3yr_avg_eps"), m.get("pb")
        combo = None if pe3 is None or pb is None else pe3 * pb
        pb_ok = None if pb is None and combo is None else ((pb is not None and pb <= 1.5) or (combo is not None and combo <= 22.5))
        rules.append(_rule("pb_combo", "P/B <= 1.5 或 P/E×P/B <= 22.5", "unknown" if pb_ok is None else ("pass" if pb_ok else "fail"), {"pb": pb, "pe_x_pb": combo}, "P/B <=1.5 OR product <=22.5"))
        price, gn = m.get("price_usd"), m.get("graham_number")
        rules.append(_rule("graham_number", "价格 <= Graham Number", "unknown" if price is None or gn is None else ("pass" if price <= gn else "fail"), {"price": price, "graham_number": gn}, "Price <= sqrt(22.5×EPS×BVPS)"))
        return _finalize(name, "Benjamin Graham · Defensive", rules)

    if name == "buffett":
        return _finalize(name, "Warren Buffett", [
            _num_rule("roe", "5年平均ROE", m.get("roe_5y_avg"), lambda x: x >= .15, ">= 15%"),
            _num_rule("de", "债务/权益", m.get("debt_to_equity"), lambda x: x <= .5, "<= 0.5"),
            _num_rule("fcf_years", "FCF连续多年为正", m.get("fcf_positive_years"), lambda x: x >= 5, ">= 5 years"),
            _num_rule("net_margin", "净利率", m.get("net_margin"), lambda x: x >= .10, ">= 10%"),
            _unknown("roic", "ROIC >= 10–15%", "当前仅有会计代理值，未把 proxy 当作精确 ROIC。"),
            _num_rule("earnings_growth", "过去5–10年盈利稳定增长", m.get("eps_cagr_5y"), lambda x: x > 0, "> 0% 5y EPS CAGR", "仅作为稳定增长的初筛代理。"),
            _num_rule("market_cap", "市值", m.get("market_cap_usd_b"), lambda x: x >= 1, ">= $1B"),
            _num_rule("owner_yield", "业主收益/FCF收益率", m.get("fcf_yield"), lambda x: x >= .05, ">= 5%"),
        ])

    if name == "lynch":
        return _finalize(name, "Peter Lynch", [
            _num_rule("peg", "PEG", m.get("peg"), lambda x: x <= 1, "<= 1.0"),
            _num_rule("eps_growth", "EPS 5年CAGR", m.get("eps_cagr_5y"), lambda x: .15 <= x <= .25, "15–25%"),
            _num_rule("revenue_growth", "收入增长率", m.get("revenue_cagr_5y"), lambda x: x >= .10, ">= 10% 5y CAGR"),
            _unknown("historical_pe", "当前P/E < 自身5年历史平均P/E", "需要历史价格/估值时间序列。"),
            _unknown("relative_debt", "债务/权益较低（行业相对）", "需要行业可比公司分布。"),
            _num_rule("fcf", "自由现金流正", m.get("fcf_positive_years"), lambda x: x >= 1, ">= 1 positive year"),
        ])

    if name == "fisher":
        return _finalize(name, "Philip Fisher · Quant Proxy", [
            _num_rule("revenue_cagr", "收入5年CAGR", m.get("revenue_cagr_5y"), lambda x: x >= .15, ">= 15%"),
            _num_rule("eps_cagr", "EPS 5年CAGR", m.get("eps_cagr_5y"), lambda x: x >= .15, ">= 15%"),
            _unknown("op_margin_industry", "营业利润率 >= 行业平均", "需要行业基准。"),
            _num_rule("rd", "研发费用/收入", m.get("rd_to_revenue"), lambda x: .05 <= x <= .15, "5–15%（成长公司）"),
            _num_rule("fcf_conversion", "FCF转化率高", m.get("fcf_conversion_net_income"), lambda x: x >= .8, ">= 80% proxy", "用 FCF/Net Income 作为量化代理。"),
        ])

    if name == "greenblatt":
        return _finalize(name, "Joel Greenblatt · Magic Formula", [
            _num_rule("market_cap", "市值", m.get("market_cap_usd_b"), lambda x: x >= .05, ">= $50M"),
            _unknown("sector_exclusion", "排除金融、公用事业", "需要标准行业分类。"),
            _unknown("roc_rank", "ROC全市场前30%", f"当前ROC proxy={m.get('greenblatt_roc_proxy')}; 需要全市场横截面排名。"),
            _unknown("ey_rank", "Earnings Yield全市场前30%", f"当前EY proxy={m.get('greenblatt_earnings_yield_proxy')}; 需要全市场横截面排名。"),
            _unknown("combined_rank", "综合排名前20–30只", "需要全市场排名数据库。"),
        ])

    if name == "hohn":
        return _finalize(name, "Chris Hohn · TCI", [
            _unknown("roic_industry", "ROIC/ROE持续高于行业", f"ROE 5y={m.get('roe_5y_avg')}; 需要行业溢价基准与精确ROIC。"),
            _unknown("margin_industry", "营业利润率高且稳定", f"当前营业利润率={m.get('operating_margin')}; 需要行业和历史稳定性基准。"),
            _num_rule("fcf_conversion", "FCF转化率高", m.get("fcf_conversion_net_income"), lambda x: x >= .8, ">=80% proxy"),
            _rule("capex", "资本支出/收入低", "unknown", m.get("capex_to_revenue"), "", "用户规则未给统一数值阈值，因此不擅自设阈值。"),
            _unknown("cyclicality", "排除高竞争/周期性行业", "需要行业分类与周期性判断。"),
            _unknown("moat", "护城河：高毛利持续性 + 定价权", f"当前毛利率={m.get('gross_margin')}; 定价权需要竞争证据。"),
        ])

    if name == "druckenmiller":
        return _finalize(name, "Stanley Druckenmiller", [
            _unknown("rs", "相对强度领先市场", "需要价格时间序列和基准指数。"),
            _unknown("eps_revision", "前瞻EPS预期上修", "需要分析师预期修正数据。"),
            _unknown("breakout", "价格趋势/技术突破确认", "需要价格技术面数据。"),
            _unknown("concentration", "高信念集中仓位", "属于组合层决策，不是单股票静态财务字段。"),
        ])

    if name == "tepper":
        return _finalize(name, "David Tepper", [
            _unknown("historical_discount", "P/B或P/E处于历史低分位", f"当前P/E={m.get('pe')}, P/B={m.get('pb')}; 需要历史估值分位。"),
            _unknown("repair", "资产负债表可修复/资产支持强", f"current ratio={m.get('current_ratio')}, D/E={m.get('debt_to_equity')}; 需要趋势和资产质量。"),
            _unknown("event", "高潜在上行空间（事件驱动）", "需要事件/催化剂分析。"),
            _unknown("vol_value", "高波动 + 低估值", "需要历史波动率与估值分位。"),
        ])

    if name == "klarman":
        return _finalize(name, "Seth Klarman", [
            _unknown("mos", "价格较清算价值/NPV/SOTP折价30–50%", "需要资产重估、NPV或分部估值。"),
            _unknown("catalyst", "明确催化剂", "需要事件研究。"),
            _unknown("downside", "下行风险有限/资产覆盖", "需要资产质量和情景清算分析。"),
            _rule("cash", "高现金持有比例", "unknown", None, "", "可进一步加入现金/资产或现金/市值阈值；用户规则未给统一数值标准。"),
        ])

    if name == "ackman_smith":
        return _finalize(name, "Bill Ackman / Terry Smith", [
            _unknown("simple", "业务简单可预测", "定性条件。"),
            _num_rule("fcf", "FCF强劲生成", m.get("fcf_positive_years"), lambda x: x >= 5, ">=5 positive years proxy"),
            _unknown("barriers", "高进入壁垒 + 主导地位", "需要竞争与行业结构证据。"),
            _num_rule("roe", "高ROE", m.get("roe_5y_avg"), lambda x: x >= .15, ">=15%"),
            _num_rule("leverage", "低杠杆", m.get("debt_to_equity"), lambda x: x <= .5, "D/E <=0.5 proxy"),
            _unknown("management", "优秀管理", "定性治理/资本配置评价。"),
            _num_rule("roce", "ROCE 5年平均 >=15%", m.get("roce_proxy"), lambda x: x >= .15, ">=15%", "当前为最新期 EBIT/(Assets-Current Liabilities) proxy，非5年均值。"),
            _num_rule("op_margin", "营业利润率", m.get("operating_margin"), lambda x: x >= .10, ">=10%"),
            _num_rule("gross_margin", "毛利率", m.get("gross_margin"), lambda x: x >= .40, ">=40%"),
            _num_rule("cash_conversion", "现金转化率", m.get("fcf_to_ebitda_proxy"), lambda x: x >= .80, ">=80% EBITDA→FCF proxy"),
            _num_rule("fcf_growth", "FCF 5年增长", m.get("fcf_cagr_5y"), lambda x: x >= 0, ">=0%"),
            _num_rule("net_debt_fcf", "净债务/FCF", m.get("net_debt_to_fcf"), lambda x: x <= 5, "<=5"),
            _num_rule("interest", "利息覆盖率", m.get("interest_coverage"), lambda x: x >= 10, ">=10"),
            _num_rule("p_fcf", "P/FCF", m.get("p_fcf"), lambda x: x <= 30, "<=30"),
            _num_rule("market_cap", "市值", m.get("market_cap_usd_b"), lambda x: x >= 5, ">= $5B"),
            _unknown("cyclical", "排除高杠杆/强周期行业", "需要行业分类和周期性判断。"),
        ])

    raise ValueError(f"Unknown strategy: {name}")


STRATEGIES = [
    "graham",
    "buffett",
    "lynch",
    "fisher",
    "greenblatt",
    "hohn",
    "druckenmiller",
    "tepper",
    "klarman",
    "ackman_smith",
]
