import re
from agent.config import llm, search_llm
from agent.schemas import ResolvedSecurity
from agent.search import response_text

resolver_llm = llm.with_structured_output(ResolvedSecurity, method="json_schema")
resolver_search_llm = search_llm.bind_tools([{"type": "web_search_preview"}])


def looks_like_ticker(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", value.strip()))


def resolve_security(user_input: str) -> ResolvedSecurity:
    query = user_input.strip()
    if not query:
        return ResolvedSecurity(status="not_found", notes="Empty query.")
    research = resolver_search_llm.invoke(f"""
Resolve the listed-security identity for: {query}
Find company name, ticker(s), exchange, country, currency, share class, and relationship among
multiple tickers. Distinguish same-company share classes from ADR/local listings and distinct
companies. Verify; never guess.
""")
    explicit_ticker = looks_like_ticker(query)
    return resolver_llm.invoke(f"""
Resolve one canonical listed security from the user input and research.
USER INPUT: {query}
EXPLICIT TICKER-LIKE INPUT: {explicit_ticker}
RESEARCH:
{response_text(research)}

Rules:
- Respect an explicitly typed verified ticker; never silently change GOOG to GOOGL.
- A company/brand name with multiple ordinary share classes is not automatically ambiguous.
  If they are the same issuer, choose a reasonable canonical common class, preferring voting
  common shares, and keep alternatives in candidates. Example: Google -> GOOGL, candidate GOOG.
- ADR vs local primary listing, preferred vs common, different companies, or materially distinct
  instruments remain ambiguous unless user intent is clear.
- status=resolved only with verified identity; never invent fields.
""")
