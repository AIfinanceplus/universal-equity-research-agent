from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SecurityCandidate(StrictModel):
    company_name: str = ""
    ticker: str = ""
    exchange: str = ""
    country: str = ""
    currency: str = ""
    share_class: str = ""
    notes: str = ""


class ResolvedSecurity(StrictModel):
    status: Literal["resolved", "ambiguous", "not_found"]
    input_kind: Literal[
        "ticker",
        "ticker_typo",
        "company_name",
        "brand",
        "alias",
        "unknown",
    ] = "unknown"
    listing_status: Literal[
        "listed",
        "not_listed",
        "unknown",
    ] = "unknown"
    company_name: str = ""
    ticker: str = ""
    exchange: str = ""
    country: str = ""
    currency: str = ""
    share_class: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    candidates: list[SecurityCandidate] = Field(default_factory=list)
    notes: str = ""


class PlanTask(StrictModel):
    name: str
    objective: str


class InvestmentPlan(StrictModel):
    tasks: list[PlanTask]


class FinancialSnapshot(StrictModel):
    annual_revenue_usd_b: float | None = None
    annual_operating_cash_flow_usd_b: float | None = None
    annual_capex_usd_b: float | None = None
    annual_fiscal_year: str | None = None
    annual_source_url: str = ""
    latest_ytd_revenue_usd_b: float | None = None
    latest_ytd_operating_cash_flow_usd_b: float | None = None
    latest_ytd_capex_usd_b: float | None = None
    latest_ytd_period: str | None = None
    latest_ytd_months: int | None = Field(default=None, ge=3, le=12)
    latest_ytd_source_url: str = ""
    prior_ytd_revenue_usd_b: float | None = None
    prior_ytd_operating_cash_flow_usd_b: float | None = None
    prior_ytd_capex_usd_b: float | None = None
    prior_ytd_period: str | None = None
    prior_ytd_months: int | None = Field(default=None, ge=3, le=12)
    notes: str = ""


class MarketSnapshot(StrictModel):
    price_usd: float | None = None
    market_cap_usd_b: float | None = None
    as_of_date: str | None = None
    as_of_time: str | None = None
    timezone: str | None = None
    provider: str | None = None
    source_url: str = ""
    notes: str = ""


class ScenarioAssumption(StrictModel):
    fcf_growth_rate: float = Field(ge=-0.50, le=0.50)
    discount_rate: float = Field(ge=0.01, le=0.30)
    exit_multiple: float = Field(ge=1.0, le=100.0)
    rationale: str
    evidence: list[str]


class ValuationAssumptions(StrictModel):
    basis: Literal["TTM", "ANNUAL"]
    bear: ScenarioAssumption
    base: ScenarioAssumption
    bull: ScenarioAssumption
    notes: str = ""


class ResearchIssue(StrictModel):
    type: Literal[
        "financial_data",
        "market_data",
        "competition",
        "risk",
        "valuation_assumption",
        "math",
    ]
    severity: Literal["blocker", "major", "minor"]
    request: str


class InvestmentCritique(StrictModel):
    source_quality: Literal["strong", "mixed", "weak"]
    financial_consistency: Literal["consistent", "uncertain", "inconsistent"]
    valuation_assumptions: Literal["reasonable", "aggressive", "unsupported"]
    contradictory_evidence: list[str]
    thesis_weaknesses: list[str]
    issues: list[ResearchIssue]
    confidence: float = Field(ge=0.0, le=1.0)


class ResearchState(TypedDict):
    company: str
    ticker: str
    exchange: str
    currency: str
    country: str
    plan: list[dict]
    attempt_count: int
    revision_count: int
    issue_attempts: dict[str, int]
    last_issue_signature: str
    stagnant_revision_count: int
    fundamentals_report: str
    fundamentals_sources: list[dict]
    financial_snapshot: dict
    annual_revenue: float
    annual_operating_cash_flow: float
    annual_capex: float
    annual_free_cash_flow: float
    annual_fiscal_year: str
    latest_ytd_revenue: float
    latest_ytd_operating_cash_flow: float
    latest_ytd_capex: float
    latest_ytd_period: str
    latest_ytd_months: int
    prior_ytd_revenue: float
    prior_ytd_operating_cash_flow: float
    prior_ytd_capex: float
    prior_ytd_period: str
    prior_ytd_months: int
    ttm_revenue: float
    ttm_operating_cash_flow: float
    ttm_capex: float
    ttm_free_cash_flow: float
    ttm_period: str
    revenue: float
    operating_cash_flow: float
    capex: float
    free_cash_flow: float
    financial_basis: str
    financial_period: str
    market_report: str
    market_sources: list[dict]
    market_snapshot: dict
    market_price: float
    market_cap: float
    market_cap_date: str
    shares_outstanding: float
    competition_report: str
    competition_sources: list[dict]
    risk_report: str
    risk_sources: list[dict]
    merged_sources: list[dict]
    evidence_summary: str
    evidence_completeness: float
    valuation_assumptions: dict
    assumption_summary: str
    valuation_result: dict
    valuation_summary: str
    deterministic_verification: dict
    critic_result: dict
    research_issues: list[dict]
    verification_summary: str
    critique: str
    needs_revision: bool
    status: Literal["running", "success", "insufficient_evidence"]
    final_answer: str
