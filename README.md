# Universal Equity Research Agent

A LangGraph-based equity research agent with deterministic financial data, valuation math, verification, targeted retries, and a local web UI.

## Current baseline

This repository is the canonical baseline after the V8.5.1 data/valuation compatibility fixes plus deterministic loop protection.

### Core architecture

```text
User Input
   ↓
Company / Security Resolver
   ↓
Planner
   ↓
Financial Data ─┐
Market Data ────┼─→ Evidence Hub
Competition ────┤
Risk ───────────┘
   ↓
Assumption Builder
   ↓
Python Valuation
   ↓
Deterministic Verification
   ↓
LLM Critic
   ↓
Typed Issue Router
   ↓
Success / Targeted Retry / Insufficient Evidence
```

## Data layer

For SEC filers, canonical financial data is sourced directly from official SEC EDGAR APIs rather than LLM extraction.

```text
Ticker
  ↓
SEC company_tickers.json
  ↓
CIK
  ↓
SEC Submissions + Company Facts
  ↓
Period-first XBRL selection
  ↓
Latest Annual + Current YTD - Prior Comparable YTD
  ↓
TTM
  ↓
FCF = OCF - CapEx
```

The selector uses the latest 10-K/10-Q report periods as hard targets before choosing among XBRL concepts, preventing stale historical tags from outranking current facts.

## Market data

Market data requires a verifiable public source URL. If provider-reported market cap is unavailable but a valid price and SEC share count are available, the system can derive:

```text
Market Cap = Price × SEC Shares Outstanding
```

For multi-class issuers, the SEC filing-cover fallback can sum common-stock classes when Company Facts does not expose one consolidated share count.

## Valuation

The valuation engine is deterministic Python. Each Bear/Base/Bull scenario exposes:

- starting FCF
- years 1-5 projected FCF
- discount factor for each year
- PV of each annual FCF
- explicit-period PV
- terminal FCF
- terminal multiple
- terminal value
- PV of terminal value
- estimated equity value
- implied return

The verifier independently recomputes the scenario math.

## Loop protection

The Typed Issue Router is bounded by deterministic circuit breakers:

- global revision limit
- per-issue retry budgets
- repeated/stagnant issue-set detection
- math failures never loop back to research

Default retry budgets:

```text
financial_data       2
market_data          2
valuation_assumption 1
competition          1
risk                 1
math                 0
```

This prevents an LLM critic from keeping the graph alive indefinitely by rephrasing the same unresolved issue.

## Setup on macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set locally in `.env`:

```text
OPENAI_API_KEY=...
SEC_USER_AGENT=YourName your.email@example.com
```

Never commit `.env`.

Run syntax checks:

```bash
python -m py_compile main.py ui_server.py agent/*.py
```

Run regression smoke tests:

```bash
python test_sec_selector.py
python sec_node_compat_smoke_test.py
python valuation_smoke_test.py
python sec_smoke_test.py META
python market_smoke_test.py META
```

Start the UI:

```bash
python -m uvicorn ui_server:app --reload --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

## Design rules

- One canonical owner per important field.
- Missing retry output must not overwrite last-known-good verified data.
- SEC data and valuation math are deterministic Python responsibilities.
- LLMs handle planning, open-ended research, assumptions, critique, and narrative.
- Company identity and security identity are distinct.
- Latest public TTM plus a current market quote is normal equity-research alignment; exact same-day financial statements are not required.
- Critic output cannot override deterministic verification without an actual deterministic failure.
