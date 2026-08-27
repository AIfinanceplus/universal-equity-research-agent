from __future__ import annotations


def _set_unknown(rule: dict, note: str):
    rule["status"] = "unknown"
    rule["note"] = (rule.get("note", "") + " " + note).strip()


def _set_fail(rule: dict, note: str):
    rule["status"] = "fail"
    rule["note"] = (rule.get("note", "") + " " + note).strip()


def calibrate_strategy_result(name: str, metrics: dict, result: dict) -> dict:
    """Calibrate deterministic outputs without changing user-defined thresholds.

    The evaluator may know that a condition is numerically below a threshold, but
    a historical criterion must not be marked FAIL when the available history is
    shorter than the user's required lookback. Likewise negative valuation ratios
    must not accidentally pass an upper-bound rule.
    """

    rules = [dict(rule) for rule in result.get("rules", [])]
    by_id = {rule.get("id"): rule for rule in rules}
    history = metrics.get("history_years", {}) or {}

    if name == "graham":
        if history.get("net_income", 0) < 10 and "profit_10y" in by_id:
            _set_unknown(
                by_id["profit_10y"],
                f"Available SEC annual net-income history is only {history.get('net_income', 0)} years; 10-year test cannot be completed.",
            )
        if history.get("dividends", 0) < 15 and "dividends" in by_id:
            _set_unknown(
                by_id["dividends"],
                f"Available SEC dividend history is only {history.get('dividends', 0)} years; 15-year test cannot be completed.",
            )
        if "pe3" in by_id and isinstance(by_id["pe3"].get("actual"), (int, float)) and by_id["pe3"]["actual"] <= 0:
            _set_fail(by_id["pe3"], "Negative/non-positive P/E does not satisfy the Graham quality/valuation test.")
        if "pb_combo" in by_id:
            actual = by_id["pb_combo"].get("actual") or {}
            pb = actual.get("pb") if isinstance(actual, dict) else None
            combo = actual.get("pe_x_pb") if isinstance(actual, dict) else None
            if (isinstance(pb, (int, float)) and pb <= 0) or (isinstance(combo, (int, float)) and combo <= 0):
                _set_fail(by_id["pb_combo"], "Negative book value or earnings cannot qualify through the upper-bound shortcut.")

    if name == "buffett":
        if history.get("fcf", 0) < 5 and "fcf_years" in by_id:
            _set_unknown(
                by_id["fcf_years"],
                f"Only {history.get('fcf', 0)} annual FCF observations are available; multi-year persistence test is incomplete.",
            )

    if name == "lynch":
        if history.get("fcf", 0) < 1 and "fcf" in by_id:
            _set_unknown(by_id["fcf"], "No annual FCF history is available.")

    if name == "ackman_smith":
        if history.get("fcf", 0) < 5 and "fcf" in by_id:
            _set_unknown(
                by_id["fcf"],
                f"Only {history.get('fcf', 0)} annual FCF observations are available; 5-year persistence cannot be established.",
            )
        if "roce" in by_id:
            _set_unknown(
                by_id["roce"],
                "Current engine exposes a latest-period ROCE proxy; user rule requires a 5-year average, so this remains UNKNOWN.",
            )
        if "p_fcf" in by_id and isinstance(by_id["p_fcf"].get("actual"), (int, float)) and by_id["p_fcf"]["actual"] <= 0:
            _set_fail(by_id["p_fcf"], "Non-positive P/FCF reflects non-positive FCF and does not satisfy the quality screen.")

    counts = {
        key: sum(1 for rule in rules if rule.get("status") == key)
        for key in ("pass", "fail", "unknown")
    }
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

    calibrated = dict(result)
    calibrated.update(
        rules=rules,
        counts=counts,
        coverage=coverage,
        verdict=verdict,
    )
    return calibrated
