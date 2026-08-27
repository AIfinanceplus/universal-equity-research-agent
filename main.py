import sqlite3
import sys
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver

from agent.graph import build_graph
from agent.resolver import resolve_security
from agent.state_factory import make_initial_state


def main():
    if len(sys.argv) < 2:
        query = input(
            "Company / ticker: "
        ).strip()
    else:
        query = " ".join(
            sys.argv[1:]
        ).strip()

    resolved = resolve_security(
        query
    )

    print(
        "\n=== SECURITY RESOLVER ==="
    )

    print(
        "status:",
        resolved.status,
    )

    print(
        "company:",
        resolved.company_name,
    )

    print(
        "ticker:",
        resolved.ticker,
    )

    print(
        "exchange:",
        resolved.exchange,
    )

    print(
        "currency:",
        resolved.currency,
    )

    print(
        "confidence:",
        resolved.confidence,
    )

    if (
        resolved.status
        !=
        "resolved"
    ):
        if resolved.candidates:
            print(
                "\nCandidates:"
            )

            for candidate in (
                resolved.candidates
            ):
                print(
                    "-",
                    candidate,
                )

        raise SystemExit(
            "Security was not uniquely resolved. "
            "Please rerun with a more specific ticker."
        )

    connection = sqlite3.connect(
        "checkpoints.sqlite",
        check_same_thread=False,
    )

    checkpointer = SqliteSaver(
        connection
    )

    graph = build_graph(
        checkpointer=
            checkpointer
    )

    thread_id = (
        f"{resolved.ticker.lower()}-cli-"
        f"{uuid.uuid4().hex[:10]}"
    )

    config = {
        "recursion_limit": 60,
        "configurable": {
            "thread_id":
                thread_id,

            "max_concurrency":
                2,
        },
    }

    initial_state = make_initial_state(
        company=
            resolved.company_name,

        ticker=
            resolved.ticker,

        exchange=
            resolved.exchange,

        currency=
            resolved.currency
            or
            "USD",

        country=
            resolved.country,
    )

    try:
        result = graph.invoke(
            initial_state,
            config=
                config,
        )

    finally:
        connection.close()

    print(
        "\n======================"
    )

    print(
        "FINAL RESULT"
    )

    print(
        "======================"
    )

    print(
        "status:",
        result["status"],
    )

    print(
        "ticker:",
        result["ticker"],
    )

    print(
        "financial basis:",
        result["financial_basis"],
    )

    print(
        "revenue:",
        result["revenue"],
    )

    print(
        "free cash flow:",
        result["free_cash_flow"],
    )

    print(
        "market cap:",
        result["market_cap"],
    )

    print(
        "\nverification:\n",
        result[
            "verification_summary"
        ],
    )

    print(
        "\nanswer:\n",
        result[
            "final_answer"
        ],
    )


if __name__ == "__main__":
    main()
