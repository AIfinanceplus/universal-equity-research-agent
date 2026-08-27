# Universal Equity Research Agent

Canonical GitHub version of a LangGraph-based equity research agent with direct SEC financial data, verifiable market provenance, deterministic investor-style screening, deterministic valuation math, independent verification, bounded targeted retries, and a local web UI.

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
Strategy Metrics (shared SEC history)
   ↓
Graham ─────────────┐
Buffett ─────────────┤
Lynch ───────────────┤
Fisher ──────────────┤
Greenblatt ──────────┤
Hohn / TCI ──────────┼─→ Strategy Screening Hub
Druckenmiller ───────┤
Tepper ──────────────┤
Klarman ─────────────┤
Ackman / Smith ──────┘
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

## Ten-investor strategy screening

The screening rules are the user-defined criteria for:

- Benjamin Graham (defensive)
- Warren Buffett
- Peter Lynch
- Philip Fisher (quant proxy)
- Joel Greenblatt (Magic Formula)
- Chris Hohn / TCI
- Stanley Druckenmiller
- David Tepper
- Seth Klarman
- Bill Ackman / Terry Smith

The system builds one shared SEC historical metric profile, then runs all ten rule modules as pure-Python nodes in parallel.

Every rule returns one of:

```text
PASS     reliable data exists and the threshold is met
FAIL     reliable data exists and the threshold is violated
UNKNOWN  required history, cross-sectional ranking, dynamic market data,
         or qualitative evidence is not available reliably
```

The strategy layer is diagnostic. A Druckenmiller or Klarman screen can be `INSUFFICIENT_DATA` without failing the main equity-research workflow.

Current deterministic/proxy metrics include, when SEC data supports them:

- Current Ratio
- Debt / Equity
- Net Margin
- Operating Margin / Gross Margin
- 5-year average ROE
- 5-year Revenue / EPS / FCF CAGR
- multi-year positive Net Income / FCF / dividend history
- P/E, P/B, PEG
- Graham Number
- P/FCF and FCF Yield
- R&D / Revenue
- CapEx / Revenue
- FCF conversion proxies
- Interest Coverage
- Net Debt / FCF
- Greenblatt ROC / Earnings Yield accounting proxies
- ROCE proxy

Fields that need historical price distributions, analyst estimates, market-wide rankings, catalysts, liquidation/SOTP valuation, relative strength, or qualitative management/moat judgments remain `UNKNOWN` rather than being guessed.

## Evidence Hub / loop fix

The initial four research branches use one true fan-in barrier, so Evidence Hub runs once after all four complete. Targeted retries use separate retry aliases and can re-enter Evidence Hub without retriggering the original four-way join.

After Evidence Hub, the shared Strategy Metrics node and ten screening nodes are deterministic/SEC-based and do not add ten separate LLM research calls.

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
- pure competition taxonomy/definition disputes do not block the whole workflow unless explicitly linked to a core valuation input

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

This prevents obsolete XBRL tags from outranking current filings.

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

## UI observability

The local UI shows:

- node-level execution graph
- information flow / logic flow / decision flow
- animated edge transfers
- Node Inspector
- Decision Trace
- Execution Timeline + replay
- graph zoom range 25%–100%
- ten-investor strategy screening matrix with rule-level PASS / FAIL / UNKNOWN

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
python ui_protocol_smoke_test.py
python strategy_screening_smoke_test.py
node --check frontend/vnext.js
node --check frontend/runtime_patch.js
node --check frontend/strategy_screening.js
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

Open `http://127.0.0.1:8765` and test `AAPL`, `TSLA`, `META`, or `GOOGL`.
