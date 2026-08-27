from datetime import date
import re

from agent.config import search_llm

web_search_llm = search_llm.bind_tools([{"type": "web_search_preview"}])


def response_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block if isinstance(block, str) else str(block.get("text", ""))
            for block in content
            if isinstance(block, str) or isinstance(block, dict)
        )
    return ""


def _collect_urls(obj, out, title=""):
    if isinstance(obj, dict):
        title = obj.get("title") or obj.get("name") or title
        for key in ("url", "source_url", "href"):
            value = obj.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                out.append({"title": title or "", "url": value})
        for value in obj.values():
            _collect_urls(value, out, title)
    elif isinstance(obj, list):
        for value in obj:
            _collect_urls(value, out, title)


def extract_sources(response) -> list[dict]:
    raw = None
    for method_name in ("model_dump", "dict"):
        method = getattr(response, method_name, None)
        if callable(method):
            try:
                raw = method()
                break
            except Exception:
                pass
    if raw is None:
        raw = {
            "content": getattr(response, "content", None),
            "content_blocks": getattr(response, "content_blocks", None),
            "additional_kwargs": getattr(response, "additional_kwargs", None),
            "response_metadata": getattr(response, "response_metadata", None),
        }
    sources = []
    _collect_urls(raw, sources)
    for url in re.findall(r'https?://[^\s<>"\]\)]+', response_text(response)):
        sources.append({"title": "", "url": url.rstrip(".,;")})
    deduped = {}
    for source in sources:
        url = source.get("url", "")
        if not url:
            continue
        if url not in deduped or (not deduped[url].get("title") and source.get("title")):
            deduped[url] = source
    return list(deduped.values())


def run_research(prompt: str) -> dict:
    response = web_search_llm.invoke(prompt)
    return {"report": response_text(response), "sources": extract_sources(response)}


def search_market_data(company: str, ticker: str, attempt: int, revision_context: str = ""):
    return run_research(f"""
You are a market-data verification specialist.
Company: {company}
Ticker: {ticker}
Current date: {date.today().isoformat()}
Research attempt: {attempt}
Targeted correction: {revision_context}

Find ONLY current/latest trading-day stock price, Market Cap, as-of date/time/timezone,
provider, and public source URL. Market Cap must be USD billions (1T = 1000B).
Use at least one public verifiable webpage such as Nasdaq, Yahoo Finance, MarketWatch,
StockAnalysis or CompaniesMarketCap. Do not rely only on an internal feed without a URL.
Never use zero for missing data. Do not research financial statements, competition, or risk.
""")


def search_competition(company: str, ticker: str, attempt: int, revision_context: str = ""):
    return run_research(f"""
You are a competition-strategy equity researcher.
Company: {company} ({ticker})
Research attempt: {attempt}
Targeted correction: {revision_context}
Research major competitors, market position/share when verifiable, product competitiveness,
ecosystem, pricing power, switching costs, technology/AI changes, and recent competitive shifts.
Prioritize company/competitor filings, regulators and high-quality industry data.
Separate verified facts from analysis. Do not output valuation multiples or target prices.
""")


def search_risks(company: str, ticker: str, attempt: int, revision_context: str = ""):
    return run_research(f"""
You are an investment risk researcher.
Company: {company} ({ticker})
Research attempt: {attempt}
Targeted correction: {revision_context}
Find material risks that can affect Revenue, OCF, CapEx and FCF: competition, regulation,
trade/geography, supply chain, technology/AI substitution, demand, cybersecurity, litigation,
and capital allocation. Prioritize SEC/company disclosures and regulators. Separate facts from
inference; do not invent quantified impacts and do not output Market Cap.
""")


def search_fundamentals(*args, **kwargs):
    """Legacy compatibility. Canonical fundamentals come from SEC direct data."""
    return {"report": "SEC direct data is canonical.", "sources": []}
