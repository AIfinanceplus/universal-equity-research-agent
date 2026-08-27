from agent import sec_data
from agent.sec_data_runtime import _parse_registration_html_annual_companyfacts


def main():
    filing = {
        "form": "S-1/A",
        "filing_date": "2026-06-01",
        "accession": "0001628280-26-039276",
        "primary_document": "spaceexplorationtechnologi.htm",
    }
    quarterly = {
        "form": "10-Q",
        "report_date": "2026-06-30",
        "filing_date": "2026-08-04",
        "accession": "0001628280-26-052535",
        "primary_document": "spcx-20260630.htm",
    }

    # Shape mirrors the ordinary (non-iXBRL) tables in the SpaceX S-1/A,
    # including the explicit '(in millions)' unit rows shown by SEC.
    html = """
    <html><body>
      <h2>Consolidated Results of Operations</h2>
      <table>
        <tr><th>Year Ended December 31,</th><th colspan="2">2025 vs. 2024 Change</th></tr>
        <tr><th>(in millions)</th><th>2025</th><th>2024</th><th>$ Change</th><th>% Change</th></tr>
        <tr><td>Revenue</td><td>$18,674</td><td>$14,015</td><td>$4,659</td><td>33.2%</td></tr>
        <tr><td>Total costs and expenses</td><td>21,263</td><td>13,549</td><td>7,714</td><td>56.9%</td></tr>
        <tr><td>Net income (loss)</td><td>123</td><td>791</td></tr>
      </table>

      <h2>Statement of Cash Flows Data:</h2>
      <table>
        <tr><th>Three Months Ended March 31,</th><th colspan="3">Year Ended December 31,</th></tr>
        <tr><th>2026</th><th>2025</th><th>2025</th><th>2024</th><th>2023</th></tr>
        <tr><th colspan="5">(in millions)</th></tr>
        <tr><td>Net cash provided by operating activities</td><td>$1,047</td><td>$727</td><td>$6,785</td><td>$5,776</td><td>$4,520</td></tr>
      </table>

      <h2>Capital Expenditures:</h2>
      <table>
        <tr><th>Three Months Ended March 31,</th><th colspan="3">Year Ended December 31,</th></tr>
        <tr><th>2026</th><th>2025</th><th>2025</th><th>2024</th><th>2023</th></tr>
        <tr><th colspan="5">(in millions)</th></tr>
        <tr><td>Space</td><td>$1,052</td><td>$759</td><td>$3,832</td><td>$2,032</td><td>$1,497</td></tr>
        <tr><td>Connectivity</td><td>1,332</td><td>814</td><td>4,178</td><td>3,498</td><td>2,455</td></tr>
        <tr><td>AI</td><td>7,723</td><td>2,567</td><td>12,727</td><td>5,633</td><td>463</td></tr>
        <tr><td>Total Capital Expenditures</td><td>$10,107</td><td>$4,140</td><td>$20,737</td><td>$11,163</td><td>$4,415</td></tr>
      </table>
    </body></html>
    """

    parsed = _parse_registration_html_annual_companyfacts(
        html,
        filing,
        quarterly,
    )

    revenue = parsed["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"][0]
    ocf = parsed["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"][0]
    capex = parsed["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]["USD"][0]

    assert revenue["val"] == 18_674_000_000
    assert ocf["val"] == 6_785_000_000
    assert capex["val"] == 20_737_000_000
    assert revenue["end"] == "2025-12-31"

    # The package shim must make the direct user import use the runtime wrapper.
    assert sec_data.load_sec_financial_snapshot.__module__ == "agent.sec_data_runtime"

    print("PASS: SpaceX-style S-1 HTML tables produce the audited annual baseline.")


if __name__ == "__main__":
    main()
