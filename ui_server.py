import asyncio
import json
import sqlite3
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.graph import build_graph
from agent.nodes import route_after_critic
from agent.resolver import resolve_security
from agent.state_factory import make_initial_state
from agent.ui_protocol import (
    compact_state_patch,
    decision_snapshot,
    graph_metadata,
    node_meta,
    snapshot_keys,
    summarize_node,
)


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

INITIAL_RESEARCH_NODES = {
    "fundamentals",
    "market_data",
    "competition",
    "risk",
}

RETRY_TO_OWNER = {
    "retry_fundamentals": "fundamentals",
    "retry_market_data": "market_data",
    "retry_competition": "competition",
    "retry_risk": "risk",
}


app = FastAPI(
    title="Universal Equity Research Agent"
)

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/graph/meta")
def api_graph_meta():
    return graph_metadata()


def sse(payload: dict) -> str:
    return (
        "data: "
        + json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )
        + "\n\n"
    )


@app.get("/api/resolve")
async def api_resolve(
    query: str = Query(..., min_length=1)
):
    resolved = await asyncio.to_thread(
        resolve_security,
        query,
    )
    return resolved.model_dump()


@app.get("/api/research/stream")
async def research_stream(
    query: str = Query(..., min_length=1)
):
    async def event_generator():
        connection = None
        run_started = time.monotonic()
        node_started_at = {}
        node_attempts = defaultdict(int)
        initial_completed = set()

        def event(event_type: str, **payload):
            return {
                "type": event_type,
                "elapsed_ms": round(
                    (time.monotonic() - run_started) * 1000
                ),
                **payload,
            }

        def mark_started(node: str):
            node_attempts[node] += 1
            node_started_at[node] = time.monotonic()
            return event(
                "node_start",
                node=node,
                attempt=node_attempts[node],
                detail="running",
            )

        def mark_queued(node: str):
            if node not in node_started_at:
                node_started_at[node] = time.monotonic()
            return event(
                "node_queued",
                node=node,
                attempt=max(1, node_attempts[node] + 1),
                detail="scheduled in parallel (runtime concurrency applies)",
            )

        try:
            yield sse(mark_started("resolver"))
            resolver_input = {"user_query": query}

            resolved = await asyncio.to_thread(
                resolve_security,
                query,
            )

            resolver_duration = round(
                (time.monotonic() - node_started_at["resolver"]) * 1000
            )

            yield sse(event("identity", data=resolved.model_dump()))
            yield sse(
                event(
                    "node_complete",
                    node="resolver",
                    attempt=node_attempts["resolver"],
                    duration_ms=resolver_duration,
                    summary={
                        "status": resolved.status,
                        "company": resolved.company_name,
                        "ticker": resolved.ticker,
                        "exchange": resolved.exchange,
                        "confidence": resolved.confidence,
                    },
                    input_snapshot=resolver_input,
                    output_snapshot={
                        "company": resolved.company_name,
                        "ticker": resolved.ticker,
                        "exchange": resolved.exchange,
                        "currency": resolved.currency,
                        "country": resolved.country,
                    },
                    output_keys=[
                        "company",
                        "ticker",
                        "exchange",
                        "currency",
                        "country",
                    ],
                )
            )

            if resolved.status != "resolved":
                message = (
                    "Security resolution is ambiguous. Please choose a more specific ticker."
                    if resolved.status == "ambiguous"
                    else "Security could not be resolved."
                )
                yield sse(
                    event(
                        "error",
                        node="resolver",
                        message=message,
                        resolution=resolved.model_dump(),
                    )
                )
                return

            yield sse(
                event(
                    "edge_transfer",
                    source="resolver",
                    target="planner",
                    channel="information",
                    payload_keys=[
                        "company",
                        "ticker",
                        "exchange",
                        "currency",
                        "country",
                    ],
                    label="canonical security",
                )
            )
            yield sse(mark_started("planner"))

            connection = sqlite3.connect(
                str(BASE_DIR / "checkpoints.sqlite"),
                check_same_thread=False,
            )
            checkpointer = SqliteSaver(connection)
            graph = build_graph(checkpointer=checkpointer)

            thread_id = (
                f"{resolved.ticker.lower()}-ui-"
                f"{uuid.uuid4().hex[:10]}"
            )

            config = {
                "recursion_limit": 60,
                "configurable": {
                    "thread_id": thread_id,
                    "max_concurrency": 2,
                },
            }

            state = make_initial_state(
                company=resolved.company_name,
                ticker=resolved.ticker,
                exchange=resolved.exchange,
                currency=resolved.currency or "USD",
                country=resolved.country,
            )

            queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def run_graph():
                try:
                    for chunk in graph.stream(
                        state,
                        config=config,
                        stream_mode="updates",
                    ):
                        asyncio.run_coroutine_threadsafe(
                            queue.put(("chunk", chunk)),
                            loop,
                        ).result()
                except Exception as exc:
                    asyncio.run_coroutine_threadsafe(
                        queue.put(("error", str(exc))),
                        loop,
                    ).result()
                finally:
                    asyncio.run_coroutine_threadsafe(
                        queue.put(("done", None)),
                        loop,
                    ).result()

            task = asyncio.create_task(
                asyncio.to_thread(run_graph)
            )

            last_state = dict(state)

            while True:
                kind, payload = await queue.get()

                if kind == "done":
                    break

                if kind == "error":
                    yield sse(event("error", message=payload))
                    break

                chunk = payload or {}

                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        update = {}

                    meta = node_meta(node_name)

                    if node_name not in node_started_at:
                        yield sse(mark_started(node_name))

                    input_snapshot = snapshot_keys(
                        last_state,
                        meta.get("inputs", []),
                    )

                    last_state.update(update)

                    duration_ms = round(
                        (
                            time.monotonic()
                            - node_started_at.get(node_name, time.monotonic())
                        )
                        * 1000
                    )

                    output_snapshot = snapshot_keys(
                        update,
                        meta.get("outputs", []),
                    )

                    summary = summarize_node(
                        node_name,
                        last_state,
                        update,
                    )

                    yield sse(
                        event(
                            "node_complete",
                            node=node_name,
                            attempt=max(1, node_attempts[node_name]),
                            duration_ms=duration_ms,
                            summary=summary,
                            input_snapshot=input_snapshot,
                            output_snapshot=output_snapshot,
                            output_keys=sorted(update.keys()),
                            state_patch=compact_state_patch(update),
                        )
                    )

                    if node_name == "planner":
                        yield sse(
                            event(
                                "edge_transfer",
                                source="planner",
                                target="research_dispatch",
                                channel="information",
                                payload_keys=["plan"],
                                label="research plan",
                            )
                        )
                        yield sse(mark_started("research_dispatch"))

                    elif node_name == "research_dispatch":
                        for branch in (
                            "fundamentals",
                            "market_data",
                            "competition",
                            "risk",
                        ):
                            yield sse(
                                event(
                                    "edge_transfer",
                                    source="research_dispatch",
                                    target=branch,
                                    channel="logic",
                                    payload_keys=["plan", "attempt_count"],
                                    label="parallel fan-out",
                                )
                            )
                            yield sse(mark_queued(branch))

                    elif node_name in INITIAL_RESEARCH_NODES:
                        initial_completed.add(node_name)
                        yield sse(
                            event(
                                "edge_transfer",
                                source=node_name,
                                target="merge",
                                channel="information",
                                payload_keys=sorted(update.keys()),
                                label="evidence payload",
                            )
                        )
                        if initial_completed == INITIAL_RESEARCH_NODES:
                            yield sse(mark_started("merge"))

                    elif node_name in RETRY_TO_OWNER:
                        yield sse(
                            event(
                                "edge_transfer",
                                source=node_name,
                                target="merge",
                                channel="information",
                                payload_keys=sorted(update.keys()),
                                label="targeted correction",
                            )
                        )
                        yield sse(mark_started("merge"))

                    elif node_name == "merge":
                        yield sse(
                            event(
                                "edge_transfer",
                                source="merge",
                                target="assumption_builder",
                                channel="information",
                                payload_keys=[
                                    "evidence_summary",
                                    "evidence_completeness",
                                    "market_cap",
                                    "market_snapshot",
                                ],
                                label="merged evidence",
                            )
                        )
                        yield sse(mark_started("assumption_builder"))

                    elif node_name == "assumption_builder":
                        yield sse(
                            event(
                                "edge_transfer",
                                source="assumption_builder",
                                target="valuation",
                                channel="information",
                                payload_keys=["valuation_assumptions"],
                                label="scenario assumptions",
                            )
                        )
                        yield sse(mark_started("valuation"))

                    elif node_name == "valuation":
                        yield sse(
                            event(
                                "edge_transfer",
                                source="valuation",
                                target="verification",
                                channel="information",
                                payload_keys=["valuation_result"],
                                label="valuation outputs",
                            )
                        )
                        yield sse(mark_started("verification"))

                    elif node_name == "verification":
                        yield sse(
                            event(
                                "edge_transfer",
                                source="verification",
                                target="critic",
                                channel="information",
                                payload_keys=["deterministic_verification"],
                                label="deterministic verdict",
                            )
                        )
                        yield sse(mark_started("critic"))

                    elif node_name == "critic":
                        yield sse(
                            event(
                                "edge_transfer",
                                source="critic",
                                target="typed_router",
                                channel="decision",
                                payload_keys=[
                                    "research_issues",
                                    "revision_count",
                                    "issue_attempts",
                                    "stagnant_revision_count",
                                ],
                                label="typed issues",
                            )
                        )
                        yield sse(mark_started("typed_router"))

                        route = route_after_critic(last_state)
                        decision = decision_snapshot(last_state, route)

                        yield sse(
                            event(
                                "decision_evaluated",
                                node="typed_router",
                                decision=decision,
                            )
                        )
                        yield sse(
                            event(
                                "route_selected",
                                source="typed_router",
                                target=route,
                                channel="decision",
                                label=route,
                                decision=decision,
                            )
                        )
                        yield sse(
                            event(
                                "node_complete",
                                node="typed_router",
                                attempt=max(1, node_attempts["typed_router"]),
                                duration_ms=round(
                                    (
                                        time.monotonic()
                                        - node_started_at["typed_router"]
                                    )
                                    * 1000
                                ),
                                summary=decision,
                                input_snapshot=snapshot_keys(
                                    last_state,
                                    node_meta("typed_router").get("inputs", []),
                                ),
                                output_snapshot={"route": route},
                                output_keys=["route"],
                                state_patch={},
                            )
                        )

                        if route not in node_started_at or route == "assumption_builder":
                            yield sse(mark_started(route))

            await task

            snapshot = graph.get_state(config)
            final_state = snapshot.values if snapshot else last_state

            yield sse(
                event(
                    "final",
                    state=compact_state_patch(dict(final_state)),
                    thread_id=thread_id,
                )
            )

        except Exception as exc:
            yield sse(event("error", message=str(exc)))

        finally:
            if connection is not None:
                connection.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
