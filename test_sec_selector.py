from agent.sec_data import (
    _parse_inline_registration_companyfacts,
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
        annual_target={"report_date": "2025-12-31", "accession": "new-k"},
        quarterly_target={"report_date": "2026-06-30", "accession": "new-q"},
    )

    assert selected["annual"]["end"] == "2025-12-31"
    assert selected["current_ytd"]["end"] == "2026-06-30"
    assert selected["prior_ytd"]["end"] == "2025-06-30"


def test_newly_public_registration_fallback_from_companyfacts():
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

    annual_target = _registration_annual_target(companyfacts, quarterly_target)
    assert annual_target is not None
    assert annual_target["report_date"] == "2025-12-31"
    assert annual_target["source"] == "registration_statement"


def test_inline_xbrl_registration_fallback():
    filing = {
        "form": "S-1/A",
        "filing_date": "2026-06-03",
        "accession": "ipo-s1a-inline",
    }

    html = """
    <html><body>
      <xbrli:context id="FY2025">
        <xbrli:entity><xbrli:identifier scheme="x">1181412</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2025-01-01</xbrli:startDate>
          <xbrli:endDate>2025-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:context id="SEGMENT2025">
        <xbrli:entity>
          <xbrli:identifier scheme="x">1181412</xbrli:identifier>
          <xbrli:segment><xbrldi:explicitMember dimension="spcx:SegmentAxis">spcx:SpaceMember</xbrldi:explicitMember></xbrli:segment>
        </xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2025-01-01</xbrli:startDate>
          <xbrli:endDate>2025-12-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>

      <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="FY2025" unitRef="USD" scale="6">20,000</ix:nonFraction>
      <ix:nonFraction name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="FY2025" unitRef="USD" scale="6">5,000</ix:nonFraction>
      <ix:nonFraction name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" contextRef="FY2025" unitRef="USD" scale="6">3,000</ix:nonFraction>

      <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="SEGMENT2025" unitRef="USD" scale="6">4,000</ix:nonFraction>
    </body></html>
    """

    parsed = _parse_inline_registration_companyfacts(html, filing)
    annual_target = _registration_annual_target(
        parsed,
        {"report_date": "2026-06-30"},
    )

    assert annual_target is not None
    assert annual_target["report_date"] == "2025-12-31"
    assert annual_target["form"] == "S-1/A"

    revenue = _select_metric(
        parsed,
        [("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax")],
        cik_int=1181412,
        annual_target=annual_target,
        quarterly_target=None,
    )
    ocf = _select_metric(
        parsed,
        [("us-gaap", "NetCashProvidedByUsedInOperatingActivities")],
        cik_int=1181412,
        annual_target=annual_target,
        quarterly_target=None,
    )
    capex = _select_metric(
        parsed,
        [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment")],
        cik_int=1181412,
        annual_target=annual_target,
        quarterly_target=None,
        normalize_abs=True,
    )

    assert revenue["annual"]["value_usd_b"] == 20.0
    assert ocf["annual"]["value_usd_b"] == 5.0
    assert capex["annual"]["value_usd_b"] == 3.0

    # Segment context must be excluded; otherwise revenue could be mis-selected.
    revenue_facts = parsed["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    assert len(revenue_facts) == 1


def main():
    test_period_first_stale_guard()
    print("PASS: stale 2018 concept cannot outrank current SEC filing periods.")

    test_newly_public_registration_fallback_from_companyfacts()
    print("PASS: newly public issuer can use S-1/A annual baseline when present in Company Facts.")

    test_inline_xbrl_registration_fallback()
    print("PASS: inline XBRL S-1/A fallback provides consolidated annual baseline.")


if __name__ == "__main__":
    main()
