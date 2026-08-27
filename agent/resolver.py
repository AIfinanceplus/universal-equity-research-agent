import re

from agent.config import llm, search_llm
from agent.schemas import ResolvedSecurity
from agent.search import response_text


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


def _safe_not_found(
    query: str,
    reason: str,
) -> ResolvedSecurity:
    return ResolvedSecurity(
        status="not_found",
        company_name="",
        ticker="",
        exchange="",
        country="",
        currency="",
        share_class="",
        confidence=0.0,
        candidates=[],
        notes=(
            f"未能验证为可研究的上市证券：{query}. "
            f"{reason}"
        ),
    )


def _validate_resolved_result(
    query: str,
    result: ResolvedSecurity,
) -> ResolvedSecurity:
    """Prevent malformed model output from entering the research graph."""

    if result.status != "resolved":
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

    # Security identity resolution is a user-input boundary. An unknown ticker,
    # a failed web search, or a malformed structured-output response must never
    # crash the research graph. These cases resolve to not_found instead.
    try:
        research = resolver_search_llm.invoke(
            f"""
Resolve the listed-security identity for: {query}

Find the exact company name, ticker(s), exchange, country, currency,
share class, and relationship among multiple tickers.

Important:
- Verify that the security is currently listed/tradable.
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
- If the exact ticker-like input does not exist, return status=not_found.
- Never silently correct an unknown ticker to a similar ticker.
- Similar symbols may be returned only as candidates, with notes explaining
  that the user's exact input was not verified.
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
        )

    return _validate_resolved_result(
        query,
        resolved,
    )
