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
    """Syntactic shape only. This does NOT mean the user intended a ticker."""

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


def _sec_exact_ticker(query: str) -> dict | None:
    """Return the exact SEC ticker row when the input is a real ticker.

    A plain alphabetic word like 'spacex' is NOT considered an explicit ticker
    unless it actually appears in the official SEC ticker mapping.
    """

    if not looks_like_ticker(query):
        return None

    wanted = _ticker_key(query)

    try:
        mapping = get_company_tickers()
    except Exception:
        return None

    for row in mapping.values():
        if _ticker_key(str(row.get("ticker", ""))) == wanted:
            return row

    return None


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
    """Return close US-listed ticker suggestions without forcing a correction."""

    if not looks_like_ticker(query):
        return []

    wanted = _ticker_key(query)

    try:
        mapping = get_company_tickers()
    except Exception:
        return []

    ranked = []

    for row in mapping.values():
        ticker = _ticker_key(str(row.get("ticker", "")))

        if not ticker:
            continue

        distance = _damerau_levenshtein(
            wanted,
            ticker,
        )

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
                company_name=str(row.get("title", "")),
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
    company_name: str = "",
    input_kind: str = "unknown",
    listing_status: str = "unknown",
) -> ResolvedSecurity:
    candidates = candidates or []

    status = (
        "ambiguous"
        if candidates
        else "not_found"
    )

    return ResolvedSecurity(
        status=status,
        input_kind=input_kind,
        listing_status=listing_status,
        company_name=company_name,
        ticker="",
        exchange="",
        country="",
        currency="",
        share_class="",
        confidence=0.0,
        candidates=candidates,
        notes=(
            f"未能确定唯一可研究上市证券：{query}. "
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
        ticker = _ticker_key(candidate.ticker or "")

        if not ticker or ticker in seen:
            continue

        seen.add(ticker)
        result.append(candidate)

    return result[:8]


def _validate_resolved_result(
    query: str,
    result: ResolvedSecurity,
    nearby_candidates: list[SecurityCandidate],
    *,
    explicit_ticker: bool,
) -> ResolvedSecurity:
    """Guard the resolver while preserving natural-language input flexibility."""

    if result.status != "resolved":
        merged = _merge_candidates(
            result.candidates,
            nearby_candidates,
        )

        if merged and result.listing_status != "not_listed":
            result.status = "ambiguous"
            result.candidates = merged

        return result

    ticker = (result.ticker or "").strip()
    company_name = (result.company_name or "").strip()

    if result.listing_status == "not_listed":
        return _safe_not_found(
            query,
            "已识别到公司实体，但当前不是可直接研究的上市证券。",
            company_name=company_name,
            input_kind=result.input_kind,
            listing_status="not_listed",
        )

    if not ticker or not company_name:
        return _safe_not_found(
            query,
            "解析结果缺少经过验证的 ticker 或公司名称。",
            candidates=nearby_candidates,
            company_name=company_name,
            input_kind=result.input_kind,
            listing_status=result.listing_status,
        )

    # Only an ACTUAL exact ticker input gets strict ticker-preservation rules.
    # Natural-language company/brand names are allowed to resolve to a different
    # canonical ticker, e.g. SpaceX -> SPCX, Tesla -> TSLA, Google -> GOOGL.
    if explicit_ticker and _ticker_key(query) != _ticker_key(ticker):
        corrected = SecurityCandidate(
            company_name=result.company_name,
            ticker=result.ticker,
            exchange=result.exchange,
            country=result.country,
            currency=result.currency,
            share_class=result.share_class,
            notes=(
                "用户输入本身是一个真实 ticker，因此系统不会静默替换成其他代码。"
            ),
        )

        return _safe_not_found(
            query,
            "输入是已验证 ticker，但搜索结果指向不同证券，需要确认。",
            candidates=_merge_candidates(
                [corrected],
                nearby_candidates,
            ),
            input_kind="ticker",
            listing_status="listed",
        )

    if result.input_kind == "ticker_typo" and _ticker_key(query) != _ticker_key(ticker):
        candidate_tickers = {
            _ticker_key(candidate.ticker)
            for candidate in nearby_candidates
            if candidate.ticker
        }

        # Auto-correct only when there is exactly one deterministic nearby
        # candidate AND the semantic resolver is highly confident in the same
        # security. Otherwise ask the user to choose.
        if not (
            len(candidate_tickers) == 1
            and _ticker_key(ticker) in candidate_tickers
            and result.confidence >= 0.90
        ):
            corrected = SecurityCandidate(
                company_name=result.company_name,
                ticker=result.ticker,
                exchange=result.exchange,
                country=result.country,
                currency=result.currency,
                share_class=result.share_class,
                notes="可能的拼写修正；存在歧义，需要用户确认。",
            )

            return _safe_not_found(
                query,
                "输入看起来像拼错的 ticker，且存在多个合理候选。",
                candidates=_merge_candidates(
                    [corrected],
                    nearby_candidates,
                ),
                input_kind="ticker_typo",
                listing_status="listed",
            )

    result.listing_status = "listed"
    return result


def resolve_security(
    user_input: str,
) -> ResolvedSecurity:
    query = (user_input or "").strip()

    if not query:
        return _safe_not_found(
            "",
            "输入为空。",
        )

    exact_ticker_row = _sec_exact_ticker(query)
    explicit_ticker = exact_ticker_row is not None

    nearby_candidates = (
        []
        if explicit_ticker
        else _sec_ticker_candidates(query)
    )

    try:
        research = resolver_search_llm.invoke(
            f"""
Resolve the investable company/security identity for this user input:
{query}

The user may enter ANY of these forms:
- exact ticker, in any letter case
- company legal name
- common company name
- consumer brand name
- product/company nickname or common alias
- a mildly misspelled ticker

EXACT SEC TICKER MATCH:
{bool(exact_ticker_row)}

Important:
- First identify what entity the user means. Do not assume a plain word is a ticker.
- Then determine whether that entity is currently publicly listed.
- If it is listed, identify the canonical ticker, exchange, country, currency and share class.
- Company/brand/alias inputs MAY resolve to a different ticker string. Examples:
  SpaceX -> SPCX; Tesla -> TSLA; Apple -> AAPL; Google -> GOOGL.
- If the input is truly a ticker typo, label it ticker_typo.
- If the company is private/not listed, say so explicitly.
- If several genuinely plausible securities remain, report the ambiguity.
- Verify current listing status; never guess.
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
            input_kind="ticker" if explicit_ticker else "unknown",
        )

    try:
        resolved = resolver_llm.invoke(
            f"""
Resolve ONE canonical investable security from the user input and research.

USER INPUT:
{query}

EXACT VERIFIED TICKER INPUT:
{explicit_ticker}

RESEARCH:
{response_text(research)}

Required classification:
- input_kind=ticker only when the user's exact input is itself a verified ticker.
- input_kind=company_name when the user typed a company/legal name.
- input_kind=brand when the user typed a commonly known brand/company brand.
- input_kind=alias for common nicknames/abbreviations.
- input_kind=ticker_typo only when evidence shows the input is a ticker misspelling.
- listing_status=listed only for a currently listed security.
- listing_status=not_listed for a known private/delisted/non-public company.

Resolution rules:
- A verified company/brand/alias may automatically map to its canonical listed ticker.
- Do NOT treat every alphabetic word as a ticker.
- If exact ticker input is verified, preserve it exactly; never silently switch share classes.
- If a ticker typo has one clear intended security, return that security with high confidence;
  deterministic code will decide whether auto-correction is safe.
- Same-company ordinary share classes are not automatically ambiguous; choose the reasonable
  canonical voting/common class and keep alternatives in candidates.
- ADR vs local primary listing, preferred vs common, different companies, or materially distinct
  instruments remain ambiguous unless user intent is clear.
- status=resolved only with a verified identity.
- Never invent fields.
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
            input_kind="ticker" if explicit_ticker else "unknown",
        )

    return _validate_resolved_result(
        query,
        resolved,
        nearby_candidates,
        explicit_ticker=explicit_ticker,
    )
