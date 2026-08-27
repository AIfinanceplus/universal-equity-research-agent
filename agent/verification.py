import re
from datetime import date

TOLERANCE = 1e-4


def nearly_equal(a: float, b: float, tolerance: float = TOLERANCE) -> bool:
    denominator = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denominator <= tolerance


def _iso_date(value: str):
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


def _date_alignment(financial_period: str, financial_basis: str, market_snapshot: dict):
    failures, warnings = [], []
    financial_date = _iso_date(financial_period)
    market_date = _iso_date(market_snapshot.get("as_of_date", ""))
    if not financial_date or not market_date:
        warnings.append("无法确定 Financial / Market 日期差。")
        return failures, warnings, None
    gap = (market_date - financial_date).days
    if gap < -7:
        failures.append("Financial period 晚于 Market date，存在明显时间对齐错误。")
    elif financial_basis == "TTM":
        if gap > 220:
            failures.append(f"TTM financial period 相对市场日期过旧：{gap} 天。")
        elif gap > 140:
            warnings.append(f"TTM financial period 与市场日期相差较大：{gap} 天。")
    else:
        if gap > 500:
            failures.append(f"Annual financial period 相对市场日期过旧：{gap} 天。")
        elif gap > 300:
            warnings.append(f"Annual financial period 与市场日期相差较大：{gap} 天。")
    return failures, warnings, gap


def _recompute_scenario(starting_fcf, current_market_cap, growth_rate, discount_rate, exit_multiple, years):
    current = starting_fcf
    rows = []
    for year in range(1, years + 1):
        current *= 1 + growth_rate
        factor = (1 + discount_rate) ** year
        rows.append({
            "year": year,
            "projected_fcf": current,
            "discount_factor": factor,
            "present_value_fcf": current / factor,
        })
    explicit = sum(r["present_value_fcf"] for r in rows)
    terminal = rows[-1]["projected_fcf"] * exit_multiple
    terminal_factor = (1 + discount_rate) ** years
    terminal_pv = terminal / terminal_factor
    equity = explicit + terminal_pv
    return {
        "yearly_cash_flows": rows,
        "explicit_period_pv": explicit,
        "final_year_fcf": rows[-1]["projected_fcf"],
        "terminal_value": terminal,
        "terminal_discount_factor": terminal_factor,
        "discounted_terminal_value": terminal_pv,
        "estimated_equity_value": equity,
        "implied_return": equity / current_market_cap - 1,
    }


def run_deterministic_verification(
    *, revenue: float, free_cash_flow: float, market_cap: float,
    financial_basis: str, financial_period: str, market_snapshot: dict,
    evidence_completeness: float, valuation_result: dict, assumptions: dict,
    source_count: int,
):
    data_failures, math_failures, model_failures, warnings = [], [], [], []
    score = 1.0
    if revenue <= 0: data_failures.append("Revenue 缺失或无效。")
    if free_cash_flow <= 0: data_failures.append("Free Cash Flow 缺失或无效。")
    if market_cap <= 0: data_failures.append("Market Cap 缺失或无效。")
    if market_snapshot.get("status") not in {"verified", "derived_verified"}:
        data_failures.append("Market Snapshot 尚未验证。")
    if not market_snapshot.get("as_of_date"):
        data_failures.append("Market Snapshot 缺少明确 as-of date。")
    if not market_snapshot.get("source_url"):
        data_failures.append("Market Snapshot 缺少可核验 source URL。")

    alignment_failures, alignment_warnings, gap = _date_alignment(financial_period, financial_basis, market_snapshot)
    data_failures += alignment_failures
    warnings += alignment_warnings
    if financial_basis != "TTM":
        warnings.append("当前估值使用 Annual 数据，未成功构建 TTM。")
        score -= 0.10
    if evidence_completeness < 0.80:
        warnings.append("Evidence completeness 低于 0.80。")
        score -= 0.10
    if source_count < 4:
        warnings.append("独特来源数量少于 4 个。")
        score -= 0.05

    if not assumptions:
        model_failures.append("Valuation assumptions 缺失。")
    else:
        try:
            bear, base, bull = assumptions["bear"], assumptions["base"], assumptions["bull"]
            if not bear["fcf_growth_rate"] <= base["fcf_growth_rate"] <= bull["fcf_growth_rate"]:
                model_failures.append("Bear/Base/Bull FCF growth 顺序异常。")
            if not bear["exit_multiple"] <= base["exit_multiple"] <= bull["exit_multiple"]:
                model_failures.append("Bear/Base/Bull exit multiple 顺序异常。")
            if not bear["discount_rate"] >= base["discount_rate"] >= bull["discount_rate"]:
                model_failures.append("Bear/Base/Bull discount rate 顺序异常。")
            for name, scenario in (("bear", bear), ("base", base), ("bull", bull)):
                if not scenario.get("rationale"): model_failures.append(f"{name} 缺少 rationale。")
                if len(scenario.get("evidence", [])) < 2: model_failures.append(f"{name} 至少需要 2 条 evidence。")
        except KeyError:
            model_failures.append("Valuation assumptions 字段不完整。")

    if not valuation_result.get("valid", False):
        data_failures.append("Valuation Engine 无法完成估值。")
    else:
        core = valuation_result["core_metrics"]
        expected = {
            "price_to_sales": market_cap / revenue,
            "price_to_fcf": market_cap / free_cash_flow,
            "fcf_yield": free_cash_flow / market_cap,
        }
        for field, value in expected.items():
            if not nearly_equal(float(core[field]), float(value)):
                math_failures.append(f"{field} 数学不一致。")
        scenarios = valuation_result["scenarios"]
        for name in ("bear", "base", "bull"):
            reported, a = scenarios[name], assumptions[name]
            recomputed = _recompute_scenario(
                free_cash_flow, market_cap, a["fcf_growth_rate"], a["discount_rate"],
                a["exit_multiple"], reported["years"]
            )
            for field in (
                "explicit_period_pv", "final_year_fcf", "terminal_value", "terminal_discount_factor",
                "discounted_terminal_value", "estimated_equity_value", "implied_return",
            ):
                if not nearly_equal(float(reported[field]), float(recomputed[field])):
                    math_failures.append(f"{name} scenario {field} 数学不一致。")
            if len(reported.get("yearly_cash_flows", [])) != len(recomputed["yearly_cash_flows"]):
                math_failures.append(f"{name} yearly cash-flow rows 数量异常。")
            else:
                for r, e in zip(reported["yearly_cash_flows"], recomputed["yearly_cash_flows"]):
                    for field in ("projected_fcf", "discount_factor", "present_value_fcf"):
                        if not nearly_equal(float(r[field]), float(e[field])):
                            math_failures.append(f"{name} year {r.get('year')} {field} 数学不一致。")
        if not scenarios["bear"]["estimated_equity_value"] <= scenarios["base"]["estimated_equity_value"] <= scenarios["bull"]["estimated_equity_value"]:
            model_failures.append("Bear/Base/Bull 估值结果顺序异常。")

    if data_failures: score = min(score, 0.60)
    if model_failures: score = min(score, 0.50)
    if math_failures: score = min(score, 0.40)
    score = max(0.0, min(score, 1.0))
    return {
        "passed": not data_failures and not math_failures and not model_failures,
        "score": score,
        "financial_market_gap_days": gap,
        "data_failures": data_failures,
        "math_failures": math_failures,
        "model_failures": model_failures,
        "warnings": warnings,
    }
