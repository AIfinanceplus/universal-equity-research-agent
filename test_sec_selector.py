from agent.sec_data import (
    _registration_annual_target,
    _select_metric,
)


def fact(*, val, start, end, filed, form, accn):
    return {
        "val": val,
        "start": start,
        "end": end,
        "filed": filed,
        "form": form,
        "accn": accn,
    }


def test_period_first_stale_guard():
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
        concepts=[
            ("us-gaap", "Revenues"),
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ],
        cik_int=1326801,
        annual_target={
            "report_date": "2025-12-31",
            "accession": "new-k",
        },
        quarterly_target={
            "report_date": "2026-06-30",
            "accession": "new-q",
        },
    )

    assert selected["annual"]["end"] == "2025-12-31"
    assert selected["current_ytd"]["end"] == "2026-06-30"
    assert selected["prior_ytd"]["end"] == "2025-06-30"


def test_newly_public_registration_fallback():
    companyfacts = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            fact(val=20_000_000_000, start="2025-01-01", end="2025-12-31", filed="2026-06-01", form="S-1/A", accn="ipo-s1a"),
            fact(val=13_000_000_000, start="2026-01-01", end="2026-06-30", filed="2026-08-04", form="10-Q", accn="ipo-q2"),
            fact(val=8_000_000_000, start="2025-01-01", end="2025-06-30", filed="2026-08-04", form="10-Q", accn="ipo-q2"),
        ]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
            fact(val=5_000_000_000, start="2025-01-01", end="2025-12-31", filed="2026-06-01", form="S-1/A", accn="ipo-s1a"),
            fact(val=3_200_000_000, start="2026-01-01", end="2026-06-30", filed="2026-08-04", form="10-Q", accn="ipo-q2"),
            fact(val=2_000_000_000, start="2025-01-01", end="2025-06-30", filed="2026-08-04", form="10-Q", accn="ipo-q2"),
        ]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            fact(val=3_000_000_000, start="2025-01-01", end="2025-12-31", filed="2026-06-01", form="S-1/A", accn="ipo-s1a"),
            fact(val=2_400_000_000, start="2026-01-01", end="2026-06-30", filed="2026-08-04", form="10-Q", accn="ipo-q2"),
            fact(val=1_400_000_000, start="2025-01-01", end="2025-06-30", filed="2026-08-04", form="10-Q", accn="ipo-q2"),
        ]}},
    }}}

    quarterly_target = {
        "form": "10-Q",
        "report_date": "2026-06-30",
        "filing_date": "2026-08-04",
        "accession": "ipo-q2",
        "primary_document": "spcx-20260630.htm",
    }

    annual_target = _registration_annual_target(
        companyfacts,
        quarterly_target,
    )

    assert annual_target is not None
    assert annual_target["report_date"] == "2025-12-31"
    assert annual_target["source"] == "registration_statement"
    assert annual_target["form"] == "S-1/A"

    revenue = _select_metric(
        companyfacts,
        concepts=[
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ],
        cik_int=1181412,
        annual_target=annual_target,
        quarterly_target=quarterly_target,
    )

    ocf = _select_metric(
        companyfacts,
        concepts=[
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ],
        cik_int=1181412,
        annual_target=annual_target,
        quarterly_target=quarterly_target,
    )

    capex = _select_metric(
        companyfacts,
        concepts=[
            ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ],
        cik_int=1181412,
        annual_target=annual_target,
        quarterly_target=quarterly_target,
        normalize_abs=True,
    )

    for selected in (revenue, ocf, capex):
        assert selected["annual"]["end"] == "2025-12-31"
        assert selected["annual"]["form"] == "S-1/A"
        assert selected["current_ytd"]["end"] == "2026-06-30"
        assert selected["prior_ytd"]["end"] == "2025-06-30"


def main():
    test_period_first_stale_guard()
    print("PASS: stale 2018 concept cannot outrank current SEC filing periods.")

    test_newly_public_registration_fallback()
    print("PASS: newly public issuer can use S-1/A annual baseline before first 10-K.")


if __name__ == "__main__":
    main()
