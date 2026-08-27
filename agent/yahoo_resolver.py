from __future__ import annotations

import json
import re

import yfinance as yf

from agent.config import llm
from agent.schemas import ResolvedSecurity, SecurityCandidate


resolver_llm = llm.with_structured_output(
    ResolvedSecurity,
    method="json_schema",
)


def _ticker_key(value: str) -> str:
    return value.strip().upper().replace(".", "-").replace("/", "-")


def _quote_name(row: dict) -> str:
    return str(
        row.get("longname")
        or row.get("shortname")
        or row.get("displayName")
        or row.get("name")
        or ""
    )


def _quote_exchange(row: dict) -> str:
    return str(row.get("exchDisp") or row.get("exchange") or "")


def _quote_is_equity(row: dict) -> bool:
    quote_type = str(row.get("quoteType") or row.get("typeDisp") or "").upper()
    return quote_type in {"EQUITY", "STOCK"} or "EQUITY" in quote_type


def _candidate(row: dict, note: str = "") -> SecurityCandidate:
    return SecurityCandidate(
        company_name=_quote_name(row),
        ticker=str(row.get("symbol") or "").upper(),
        exchange=_quote_exchange(row),
        country=str(row.get("region") or ""),
        currency=str(row.get("currency") or "USD"),
        share_class="",
        notes=note or "Yahoo Finance search result.",
    )


def _search_quotes(query: str) -> list[dict]:
    try:
        search = yf.Search(
            query,
            max_results=8,
            news_count=0,
            lists_count=0,
            include_cb=False,
            include_nav_links=False,
            include_research=False,
            enable_fuzzy_query=True,
            raise_errors=False,
        )
        rows = list(search.quotes or [])
    except Exception:
        rows = []

    return [row for row in rows if isinstance(row, dict) and row.get("symbol") and _quote_is_equity(row)]


def _safe_not_found(query: str, reason: str, candidates: list[SecurityCandidate] | None = None) -> ResolvedSecurity:
    candidates = candidates or []
    return ResolvedSecurity(
        status="ambiguous" if candidates else "not_found",
        input_kind="unknown",
        listing_status="unknown",
        company_name="",
        ticker="",
        exchange="",
        country="",
        currency="",
        share_class="",
        confidence=0.0,
        candidates=candidates,
        notes=f"未能确定唯一上市证券：{query}。{reason}",
    )


def resolve_security(user_input: str) -> ResolvedSecurity:
    query = (user_input or "").strip()
    if not query:
        return _safe_not_found("", "输入为空。")

    rows = _search_quotes(query)
    candidates = [_candidate(row) for row in rows]

    if not rows:
        return _safe_not_found(query, "Yahoo Finance 未返回可验证股票候选。")

    wanted = _ticker_key(query)
    exact = [row for row in rows if _ticker_key(str(row.get("symbol") or "")) == wanted]
    if exact:
        row = exact[0]
        return ResolvedSecurity(
            status="resolved",
            input_kind="ticker",
            listing_status="listed",
            company_name=_quote_name(row),
            ticker=str(row.get("symbol") or "").upper(),
            exchange=_quote_exchange(row),
            country=str(row.get("region") or ""),
            currency=str(row.get("currency") or "USD"),
            share_class="",
            confidence=0.99,
            candidates=[],
            notes="Exact Yahoo Finance ticker match.",
        )

    # A single Yahoo equity candidate is safe enough for natural-language names.
    if len(rows) == 1:
        row = rows[0]
        return ResolvedSecurity(
            status="resolved",
            input_kind="company_name",
            listing_status="listed",
            company_name=_quote_name(row),
            ticker=str(row.get("symbol") or "").upper(),
            exchange=_quote_exchange(row),
            country=str(row.get("region") or ""),
            currency=str(row.get("currency") or "USD"),
            share_class="",
            confidence=0.95,
            candidates=[],
            notes="Single Yahoo Finance equity candidate.",
        )

    candidate_payload = [candidate.model_dump() for candidate in candidates]

    try:
        result = resolver_llm.invoke(
            f"""
用户输入：{query}

Yahoo Finance 返回了以下股票候选：
{json.dumps(candidate_payload, ensure_ascii=False)}

只允许从这些 Yahoo 候选中选择，不得创造新的 ticker。
目标是尽量容忍自然语言公司名、品牌名、简称和轻微拼写错误。

规则：
- 如果用户明显指向其中一家上市公司，status=resolved。
- company_name/ticker/exchange/country/currency 必须来自候选。
- 用户输入公司名、品牌或别名时，可以自动映射到 canonical ticker。
- 如果是轻微 ticker 拼写错误，但一个候选明显最合理，也可以 resolved，input_kind=ticker_typo。
- 只有两个或更多候选都同样合理时才 ambiguous。
- 不要因为大小写、空格、Inc/Corp 等格式差异制造歧义。
"""
        )
    except Exception as exc:
        return _safe_not_found(
            query,
            f"Yahoo 候选已找到，但结构化解析失败：{exc.__class__.__name__}",
            candidates,
        )

    allowed = {_ticker_key(candidate.ticker): candidate for candidate in candidates}
    selected = allowed.get(_ticker_key(result.ticker or ""))

    if result.status == "resolved" and selected:
        result.company_name = selected.company_name
        result.ticker = selected.ticker
        result.exchange = selected.exchange
        result.country = selected.country
        result.currency = selected.currency or "USD"
        result.listing_status = "listed"
        result.candidates = []
        return result

    return _safe_not_found(
        query,
        "Yahoo Finance 返回多个合理股票候选，需要进一步确认。",
        candidates,
    )
