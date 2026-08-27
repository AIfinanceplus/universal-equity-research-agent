import asyncio
import json
import sqlite3
import uuid
from pathlib import Path

from fastapi import (
    FastAPI,
    Query,
)

from fastapi.responses import (
    FileResponse,
    StreamingResponse,
)

from fastapi.staticfiles import StaticFiles

from langgraph.checkpoint.sqlite import SqliteSaver

from agent.graph import build_graph
from agent.resolver import resolve_security
from agent.state_factory import make_initial_state


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

DISPLAY_NODE_MAP = {
    "retry_fundamentals": "fundamentals",
    "retry_market_data": "market_data",
    "retry_competition": "competition",
    "retry_risk": "risk",
}

NEXT_NODE_HINTS = {
    "merge": "assumption_builder",
    "assumption_builder": "valuation",
    "valuation": "verification",
    "verification": "critic",
}

FRONTEND_DIR = (
    BASE_DIR
    /
    "frontend"
)

app = FastAPI(
    title=
        "Universal Equity Research Agent"
)

app.mount(
    "/static",
    StaticFiles(
        directory=
            str(
                FRONTEND_DIR
            )
    ),
    name=
        "static",
)


@app.get("/")
def home():
    return FileResponse(
        FRONTEND_DIR
        /
        "index.html"
    )


def sse(
    payload: dict,
) -> str:
    return (
        "data: "
        +
        json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )
        +
        "\n\n"
    )


@app.get("/api/resolve")
async def api_resolve(
    query: str = Query(
        ...,
        min_length=1,
    )
):
    resolved = (
        await asyncio.to_thread(
            resolve_security,
            query,
        )
    )

    return resolved.model_dump()


@app.get("/api/research/stream")
async def research_stream(
    query: str = Query(
        ...,
        min_length=1,
    )
):
    async def event_generator():
        connection = None

        try:
            resolved = (
                await asyncio.to_thread(
                    resolve_security,
                    query,
                )
            )

            yield sse(
                {
                    "type":
                        "identity",

                    "data":
                        resolved.model_dump(),
                }
            )

            if (
                resolved.status
                !=
                "resolved"
            ):
                message = (
                    "Security resolution is ambiguous. "
                    "Please choose a more specific ticker."
                    if resolved.status
                    ==
                    "ambiguous"
                    else
                    "Security could not be resolved."
                )

                yield sse(
                    {
                        "type":
                            "error",

                        "message":
                            message,

                        "resolution":
                            resolved.model_dump(),
                    }
                )

                return

            connection = sqlite3.connect(
                str(
                    BASE_DIR
                    /
                    "checkpoints.sqlite"
                ),
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
                f"{resolved.ticker.lower()}-ui-"
                f"{uuid.uuid4().hex[:10]}"
            )

            config = {
                "recursion_limit":
                    60,

                "configurable": {
                    "thread_id":
                        thread_id,

                    "max_concurrency":
                        2,
                },
            }

            state = make_initial_state(
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

            queue = asyncio.Queue()
            loop = (
                asyncio.get_running_loop()
            )

            def run_graph():
                try:
                    for chunk in graph.stream(
                        state,
                        config=
                            config,
                        stream_mode=
                            "updates",
                    ):
                        asyncio.run_coroutine_threadsafe(
                            queue.put(
                                (
                                    "chunk",
                                    chunk,
                                )
                            ),
                            loop,
                        ).result()

                except Exception as exc:
                    asyncio.run_coroutine_threadsafe(
                        queue.put(
                            (
                                "error",
                                str(exc),
                            )
                        ),
                        loop,
                    ).result()

                finally:
                    asyncio.run_coroutine_threadsafe(
                        queue.put(
                            (
                                "done",
                                None,
                            )
                        ),
                        loop,
                    ).result()

            task = asyncio.create_task(
                asyncio.to_thread(
                    run_graph
                )
            )

            last_state = {}

            while True:
                kind, payload = (
                    await queue.get()
                )

                if kind == "done":
                    break

                if kind == "error":
                    yield sse(
                        {
                            "type":
                                "error",

                            "message":
                                payload,
                        }
                    )
                    break

                chunk = payload or {}

                for (
                    node_name,
                    update,
                ) in chunk.items():
                    if isinstance(
                        update,
                        dict,
                    ):
                        last_state.update(
                            update
                        )

                    display_node = DISPLAY_NODE_MAP.get(
                        node_name,
                        node_name,
                    )

                    yield sse(
                        {
                            "type":
                                "node",

                            "node":
                                display_node,

                            "detail":
                                "completed",

                            "state":
                                last_state,
                        }
                    )

                    next_node = NEXT_NODE_HINTS.get(
                        node_name
                    )

                    if next_node:
                        yield sse(
                            {
                                "type":
                                    "node_start",

                                "node":
                                    next_node,

                                "detail":
                                    "running",
                            }
                        )

                    if (
                        node_name
                        ==
                        "critic"
                    ):
                        issues = (
                            last_state.get(
                                "research_issues",
                                [],
                            )
                        )

                        if issues:
                            top = issues[0]

                            yield sse(
                                {
                                    "type":
                                        "router",

                                    "detail":
                                        (
                                            f"{top.get('type')} · "
                                            f"{top.get('severity')}"
                                        ),
                                }
                            )

            await task

            snapshot = graph.get_state(
                config
            )

            final_state = (
                snapshot.values
                if snapshot
                else
                last_state
            )

            yield sse(
                {
                    "type":
                        "final",

                    "state":
                        final_state,

                    "thread_id":
                        thread_id,
                }
            )

        except Exception as exc:
            yield sse(
                {
                    "type":
                        "error",

                    "message":
                        str(exc),
                }
            )

        finally:
            if (
                connection
                is not None
            ):
                connection.close()

    return StreamingResponse(
        event_generator(),
        media_type=
            "text/event-stream",
        headers={
            "Cache-Control":
                "no-cache",

            "X-Accel-Buffering":
                "no",
        },
    )
