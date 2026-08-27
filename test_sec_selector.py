from agent.sec_data import _select_metric


def fact(*, val, start, end, filed, form, accn):
    return {"val": val, "start": start, "end": end, "filed": filed, "form": form, "accn": accn}


def main():
    companyfacts = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            fact(val=55_000_000_000, start="2017-01-01", end="2017-12-31", filed="2018-02-01", form="10-K", accn="old-k"),
            fact(val=40_000_000_000, start="2018-01-01", end="2018-09-30", filed="2018-10-30", form="10-Q", accn="old-q"),
            fact(val=28_000_000_000, start="2017-01-01", end="2017-09-30", filed="2018-10-30", form="10-Q", accn="old-q"),
        ]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            fact(val=200_000_000_000, start="2025-01-01", end="2025-12-31", filed="2026-01-29", form="10-K", accn="new-k"),
            fact(val=117_111_000_000, start="2026-01-01", end="2026-06-30", filed="2026-07-30", form="10-Q", accn="new-q"),
            fact(val=89_830_000_000, start="2025-01-01", end="2025-06-30", filed="2026-07-30", form="10-Q", accn="new-q"),
        ]}},
    }}}
    selected = _select_metric(
        companyfacts,
        concepts=[("us-gaap", "Revenues"), ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax")],
        cik_int=1326801,
        annual_target={"report_date": "2025-12-31", "accession": "new-k"},
        quarterly_target={"report_date": "2026-06-30", "accession": "new-q"},
    )
    assert selected["annual"]["end"] == "2025-12-31"
    assert selected["current_ytd"]["end"] == "2026-06-30"
    assert selected["prior_ytd"]["end"] == "2025-06-30"
    print("PASS: stale 2018 concept cannot outrank current SEC filing periods.")


if __name__ == "__main__":
    main()
