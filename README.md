# Universal Equity Research Agent

Canonical GitHub version of a LangGraph-based equity research agent with direct SEC financial data, verifiable market provenance, deterministic valuation math, independent verification, bounded targeted retries, and a local web UI.

## Architecture

```text
User Input
   ↓
Security Resolver
   ↓
Planner
   ↓
Financial Data ─┐
Market Data ────┼─→ Evidence Hub (single join)
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
   ├─ targeted retry (bounded)
   ├─ success
   └─ insufficient evidence
```

## Evidence Hub / loop fix

The initial four research branches now use one true fan-in barrier, so Evidence Hub runs once after all four complete. Targeted retries use separate retry aliases and can re-enter Evidence Hub without retriggering the original four-way join.

The UI also emits a `node_start` event immediately when moving from Evidence Hub to Assumption Builder, so a slow LLM call is shown as **Assumption Builder running** instead of making Evidence Hub look frozen.

Deterministic circuit breakers prevent infinite critique loops:

```text
financial_data       max 2 retries
market_data          max 2 retries
valuation_assumption max 1 retry
competition          max 1 retry
risk                 max 1 retry
math                 0 retries
```

Additional stops:
- global revision limit (`MAX_RESEARCH_ATTEMPTS`, default 3)
- repeated/stagnant actionable issue set exits after two repeats
- math failures go directly to insufficient evidence

## SEC data layer

For SEC filers, canonical financial data bypasses LLM extraction:

```text
Ticker
  ↓
SEC company_tickers.json
  ↓
CIK
  ↓
SEC Submissions + Company Facts
  ↓
latest 10-K / 10-Q periods become hard targets
  ↓
period-first XBRL concept selection
  ↓
Annual + Current YTD - Prior Comparable YTD
  ↓
TTM
  ↓
FCF = OCF - CapEx
```

This prevents obsolete XBRL tags (for example an old `Revenues` series) from outranking current filings.

For multi-class issuers, share count can fall back to parsing the latest SEC filing cover and summing common-stock classes.

## Market data

Market data must have a public verifiable URL. Provider-reported Market Cap is preferred. If it is unavailable but price and SEC shares are verified:

```text
Market Cap = Price × SEC Shares Outstanding
```

## Valuation

The deterministic 5-year FCF scenario engine exposes and independently verifies:
- starting FCF
- years 1–5 projected FCF
- discount factors
- PV of each annual FCF
- explicit-period PV
- terminal FCF and multiple
- terminal value and PV
- estimated equity value
- implied return

This is intentionally a simplified scenario valuation, not a standard WACC DCF.

## macOS setup

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

## Offline regression tests

```bash
python -m py_compile main.py ui_server.py agent/*.py
python router_smoke_test.py
python valuation_smoke_test.py
python test_sec_selector.py
python graph_structure_smoke_test.py
```

GitHub Actions runs these automatically on every push / pull request.

## Live data checks

```bash
python sec_smoke_test.py META
python sec_smoke_test.py GOOGL
```

## Start UI

```bash
python -m uvicorn ui_server:app --reload --port 8765
```

Open `http://127.0.0.1:8765` and test `TSLA`, `META`, or `GOOGL`.
