def safe_divide(numerator: float, denominator: float):
    if denominator == 0:
        return None
    return numerator / denominator


def calculate_core_metrics(revenue: float, free_cash_flow: float, market_cap: float):
    return {
        "price_to_sales": safe_divide(market_cap, revenue),
        "price_to_fcf": safe_divide(market_cap, free_cash_flow),
        "fcf_yield": safe_divide(free_cash_flow, market_cap),
    }


def project_fcf(starting_fcf: float, growth_rate: float, years: int):
    values = []
    current = starting_fcf
    for _ in range(years):
        current = current * (1 + growth_rate)
        values.append(current)
    return values


def build_yearly_cash_flow_table(*, projected_fcf: list[float], discount_rate: float):
    rows = []
    for year, cash_flow in enumerate(projected_fcf, start=1):
        discount_factor = (1 + discount_rate) ** year
        present_value = cash_flow / discount_factor
        rows.append({
            "year": year,
            "projected_fcf": cash_flow,
            "discount_factor": discount_factor,
            "present_value_fcf": present_value,
        })
    return rows


def calculate_scenario(
    *,
    starting_fcf: float,
    current_market_cap: float,
    growth_rate: float,
    discount_rate: float,
    exit_multiple: float,
    years: int = 5,
):
    projected_fcf = project_fcf(starting_fcf, growth_rate, years)
    yearly_cash_flows = build_yearly_cash_flow_table(
        projected_fcf=projected_fcf,
        discount_rate=discount_rate,
    )
    explicit_period_pv = sum(row["present_value_fcf"] for row in yearly_cash_flows)
    final_year_fcf = projected_fcf[-1]
    terminal_value = final_year_fcf * exit_multiple
    terminal_discount_factor = (1 + discount_rate) ** years
    discounted_terminal_value = terminal_value / terminal_discount_factor
    estimated_equity_value = explicit_period_pv + discounted_terminal_value
    implied_return = estimated_equity_value / current_market_cap - 1
    return {
        "starting_fcf": starting_fcf,
        "growth_rate": growth_rate,
        "discount_rate": discount_rate,
        "exit_multiple": exit_multiple,
        "years": years,
        "projected_fcf": projected_fcf,
        "yearly_cash_flows": yearly_cash_flows,
        "explicit_period_pv": explicit_period_pv,
        "final_year_fcf": final_year_fcf,
        "terminal_value": terminal_value,
        "terminal_discount_factor": terminal_discount_factor,
        "discounted_terminal_value": discounted_terminal_value,
        "estimated_equity_value": estimated_equity_value,
        "current_market_cap": current_market_cap,
        "implied_return": implied_return,
        "formula": {
            "projected_fcf": "FCF_t = FCF_0 × (1 + g)^t",
            "explicit_period_pv": "Σ[FCF_t / (1 + r)^t], t=1..N",
            "terminal_value": "FCF_N × exit_multiple",
            "discounted_terminal_value": "terminal_value / (1 + r)^N",
            "estimated_equity_value": "explicit_period_pv + discounted_terminal_value",
            "implied_return": "estimated_equity_value / current_market_cap - 1",
        },
    }


def run_valuation_engine(
    *,
    revenue: float,
    free_cash_flow: float,
    market_cap: float,
    assumptions: dict,
):
    if revenue <= 0 or free_cash_flow <= 0 or market_cap <= 0:
        return {"valid": False, "reason": "关键财务数据缺失或无效。"}
    if not assumptions:
        return {"valid": False, "reason": "Valuation assumptions 缺失。"}
    try:
        bear = assumptions["bear"]
        base = assumptions["base"]
        bull = assumptions["bull"]
    except KeyError:
        return {"valid": False, "reason": "Valuation assumptions 结构不完整。"}

    core_metrics = calculate_core_metrics(revenue, free_cash_flow, market_cap)
    scenarios = {}
    for name, values in {"bear": bear, "base": base, "bull": bull}.items():
        scenarios[name] = calculate_scenario(
            starting_fcf=free_cash_flow,
            current_market_cap=market_cap,
            growth_rate=values["fcf_growth_rate"],
            discount_rate=values["discount_rate"],
            exit_multiple=values["exit_multiple"],
            years=5,
        )

    return {
        "valid": True,
        "methodology": (
            "Simplified 5-year FCF scenario valuation. Includes discounted annual FCF "
            "for years 1-5 plus a terminal value based on year-5 FCF × exit multiple. "
            "This is not a standard WACC DCF."
        ),
        "units": "USD billions",
        "core_metrics": core_metrics,
        "scenarios": scenarios,
        "assumptions": assumptions,
    }
