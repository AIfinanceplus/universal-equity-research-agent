import re

from agent.config import llm, search_llm
from agent.schemas import ResolvedSecurity, SecurityCandidate
from agent.search import response_text
from agent.sec_data import get_company_tickers


resolver_llm = llm.with_structured_output(
    ResolvedSecurity,
    method="json_schema",
)

resolver_search_llm = search_llm.bind_tools(
    [
        {
            "type": "web_search_preview",
        }
    ]
)


def looks_like_ticker(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"[A-Za-z0-9.\-]{1,12}",
            value.strip(),
        )
    )


def _ticker_key(value: str) -> str:
    return (
        value.strip()
        .upper()
        .replace(".", "-")
        .replace("/", "-")
    )


def _damerau_levenshtein(a: str, b: str) -> int:
    """Small deterministic edit distance for ticker typo suggestions."""

    a = _ticker_key(a)
    b = _ticker_key(b)

    rows = len(a) + 1
    cols = len(b) + 1

    d = [
        [0] * cols
        for _ in range(rows)
    ]

    for i in range(rows):
        d[i][0] = i

    for j in range(cols):
        d[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1

            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )

            if (
                i > 1
                and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                d[i][j] = min(
                    d[i][j],
                    d[i - 2][j - 2] + 1,
                )

    return d[-1][-1]


def _sec_ticker_candidates(
    query: str,
    *,
    max_candidates: int = 5,
) -> list[SecurityCandidate]:
    """Return close US-listed ticker suggestions without silently correcting."""

    if not looks_like_ticker(query):
        return []

    wanted = _ticker_key(query)

    try:
        mapping = get_company_tickers()
    except Exception:
        return []

    ranked = []

    for row in mapping.values():
        ticker = _ticker_key(
            str(
                row.get(
                    "ticker",
                    "",
                )
            )
        )

        if not ticker:
            continue

        distance = _damerau_levenshtein(
            wanted,
            ticker,
        )

        # For short tickers, only one edit is a useful suggestion.
        # For longer symbols, allow two edits but rank them lower.
        threshold = 1 if len(wanted) <= 5 else 2

        if distance > threshold:
            continue

        ranked.append(
            (
                distance,
                abs(len(ticker) - len(wanted)),
                ticker,
                row,
            )
        )

    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    result = []

    for distance, _, ticker, row in ranked[:max_candidates]:
        result.append(
            SecurityCandidate(
                company_name=str(
                    row.get(
                        "title",
                        "",
                    )
                ),
                ticker=ticker,
                exchange="",
                country="United States",
                currency="USD",
                share_class="",
                notes=(
                    f"SEC ticker mapping 中的相近代码；"
                    f"与输入 {_ticker_key(query)} 的编辑距离为 {distance}。"
                ),
            )
        )

    return result


def _safe_not_found(
    query: str,
    reason: str,
    *,
    candidates: list[SecurityCandidate] | None = None,
) -> ResolvedSecurity:
    candidates = candidates or []

    status = (
        "ambiguous"
        if candidates
        else "not_found"
    )

    return ResolvedSecurity(
        status=status,
        company_name="",
        ticker="",
        exchange="",
        country="",
        currency="",
        share_class="",
        confidence=0.0,
        candidates=candidates,
        notes=(
            f"未能验证输入为唯一上市证券：{query}. "
            f"{reason}"
        ),
    )


def _merge_candidates(
    first: list[SecurityCandidate],
    second: list[SecurityCandidate],
) -> list[SecurityCandidate]:
    result = []
    seen = set()

    for candidate in list(first or []) + list(second or []):
        ticker = _ticker_key(
            candidate.ticker
            or ""
        )

        if not ticker or ticker in seen:
            continue

        seen.add(ticker)
        result.append(candidate)

    return result[:8]


def _validate_resolved_result(
    query: str,
    result: ResolvedSecurity,
    nearby_candidates: list[SecurityCandidate],
) -> ResolvedSecurity:
    """Prevent malformed or silently corrected model output entering the graph."""

    if result.status != "resolved":
        merged = _merge_candidates(
            result.candidates,
            nearby_candidates,
        )

        if merged:
            result.status = "ambiguous"
            result.candidates = merged

        return result

    ticker = (
        result.ticker
        or ""
    ).strip()

    company_name = (
        result.company_name
        or ""
    ).strip()

    if not ticker or not company_name:
        return _safe_not_found(
            query,
            "解析结果缺少经过验证的 ticker 或公司名称。",
            candidates=nearby_candidates,
        )

    # If the user typed something ticker-like and the resolver returns a
    # different ticker, do not silently autocorrect it. Ask the user to choose.
    if (
        looks_like_ticker(query)
        and _ticker_key(query) != _ticker_key(ticker)
    ):
        corrected = SecurityCandidate(
            company_name=result.company_name,
            ticker=result.ticker,
            exchange=result.exchange,
            country=result.country,
            currency=result.currency,
            share_class=result.share_class,
            notes=(
                "搜索结果认为这是可能的目标证券，但与用户输入代码不同；"
                "需要用户确认后才能继续。"
            ),
        )

        return _safe_not_found(
            query,
            "输入代码与搜索到的真实 ticker 不一致，系统不会自动替换。",
            candidates=_merge_candidates(
                [corrected],
                nearby_candidates,
            ),
        )

    return result


def resolve_security(
    user_input: str,
) -> ResolvedSecurity:
    query = (
        user_input
        or ""
    ).strip()

    if not query:
        return _safe_not_found(
            "",
            "输入为空。",
        )

    explicit_ticker = looks_like_ticker(
        query
    )

    nearby_candidates = _sec_ticker_candidates(
        query
    )

    # Security identity resolution is a user-input boundary. An unknown ticker,
    # a failed web search, or malformed structured output must never crash the
    # research graph.
    try:
        research = resolver_search_llm.invoke(
            f"""
Resolve the listed-security identity for: {query}

Find the exact company name, ticker(s), exchange, country, currency,
share class, and relationship among multiple tickers.

Important:
- Verify that the exact security is currently listed/tradable.
- Distinguish a real ticker from a typo or an unrelated acronym.
- If the exact ticker is not verified, say so explicitly.
- You may identify plausible nearby ticker candidates, but never silently
  substitute one ticker for another.
- Distinguish same-company share classes from ADR/local listings and
  materially different companies.
"""
        )

    except Exception as exc:
        return _safe_not_found(
            query,
            (
                "证券身份搜索暂时失败；系统已安全停止，"
                f"未进入研究流程。原因：{exc.__class__.__name__}"
            ),
            candidates=nearby_candidates,
        )

    try:
        resolved = resolver_llm.invoke(
            f"""
Resolve one canonical listed security from the user input and research.

USER INPUT:
{query}

EXPLICIT TICKER-LIKE INPUT:
{explicit_ticker}

RESEARCH:
{response_text(research)}

Rules:
- status=resolved ONLY when the exact listed security is verified.
- If an exact ticker-like input does not exist, do not silently fix it.
- Similar symbols may be returned only as candidates.
- Respect an explicitly typed verified ticker; never silently change GOOG
  to GOOGL.
- A company/brand name with multiple ordinary share classes is not
  automatically ambiguous. If they are the same issuer, choose a reasonable
  canonical common class, preferring voting common shares, and keep
  alternatives in candidates. Example: Google -> GOOGL, candidate GOOG.
- ADR vs local primary listing, preferred vs common, different companies,
  or materially distinct instruments remain ambiguous unless user intent
  is clear.
- Never invent company, ticker, exchange, country, currency, or share class.
"""
        )

    except Exception as exc:
        return _safe_not_found(
            query,
            (
                "证券身份结构化解析失败；系统已安全停止，"
                f"未进入研究流程。原因：{exc.__class__.__name__}"
            ),
            candidates=nearby_candidates,
        )

    return _validate_resolved_result(
        query,
        resolved,
        nearby_candidates,
    )
