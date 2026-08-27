"""Universal Equity Research Agent."""

# Keep the mature SEC selector as the canonical implementation, but install a
# narrow compatibility wrapper for newly public issuers whose audited annual
# financials live in S-1/F-1 HTML rather than a first 10-K/20-F.
from . import sec_data as _sec_data
from .sec_data_runtime import load_sec_financial_snapshot as _runtime_load

_sec_data.load_sec_financial_snapshot = _runtime_load
