"""
app_b/main.py
─────────────
App B — LLM Pipeline Gateway.

Responsibilities:
  • Receive pipeline jobs from App A
  • Run the PipelineEngine (sequential nodes, each calls the LLM)
  • Stream typed SSE events back to App A

Run:
    uvicorn app_b.main:app --port 8001 --reload
"""
from __future__ import annotations

import asyncio
import json
import sys
import pathlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from shared.contracts import (
    JobStatus,
    NodeType,
    PipelineEvent,
    PipelineEventType,
    PipelineRequest,
    PipelineResult,
)
from app_b.pipeline.engine import PipelineEngine
from app_b.pipeline.registry import registry

# ─────────────────────────────────────────────
# In-memory job store
# ─────────────────────────────────────────────

# job_id → asyncio.Queue[PipelineEvent | None]  (None = sentinel = done)
_job_queues: dict[str, asyncio.Queue] = {}
# job_id → PipelineResult (populated on completion)
_job_results: dict[str, PipelineResult] = {}

engine = PipelineEngine()


# ─────────────────────────────────────────────
# Background pipeline runner
# ─────────────────────────────────────────────

async def _run_pipeline(request: PipelineRequest) -> None:
    """
    Background task: runs the pipeline and pushes events into the job's queue.
    """
    job_id = request.job_id
    queue = _job_queues.setdefault(job_id, asyncio.Queue(maxsize=2000))

    try:
        async for event in engine.run(request):
            await queue.put(event)

            # Cache the final result for /jobs/{job_id}/result
            if event.event_type == PipelineEventType.PIPELINE_COMPLETED:
                payload = event.payload
                result_data = payload.get("result", {})
                _job_results[job_id] = PipelineResult(**result_data)

    except Exception as exc:
        await queue.put(PipelineEvent(
            event_type=PipelineEventType.PIPELINE_ERROR,
            job_id=job_id,
            sequence=999999,
            payload={"error": str(exc)},
        ))
    finally:
        await queue.put(None)  # sentinel — tells streaming generator to stop


# ─────────────────────────────────────────────
# SSE generator
# ─────────────────────────────────────────────

async def _sse_generator(job_id: str) -> AsyncGenerator[str, None]:
    queue = _job_queues.get(job_id)
    if queue is None:
        yield "event: pipeline.error\ndata: {\"error\": \"job not found\"}\n\n"
        return

    while True:
        event = await queue.get()
        if event is None:          # sentinel — pipeline finished
            yield ": done\n\n"
            break
        yield event.to_sse_frame()


# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────

app = FastAPI(
    title="LLM Pipeline Gateway (App B)",
    version="1.0.0",
    description="Receives pipeline jobs, runs LLM nodes sequentially, streams events.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # App A
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/pipeline/start",
    status_code=202,
    summary="Submit a pipeline job",
)
async def start_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Accepts a PipelineRequest, kicks off the pipeline as a background task,
    and returns the job_id immediately.  The caller should then subscribe to
    GET /pipeline/{job_id}/stream.
    """
    # Validate node types are registered
    for node_cfg in request.pipeline_config.nodes:
        if node_cfg.node_type.value not in registry.registered_types():
            raise HTTPException(
                status_code=422,
                detail=f"Unknown node type: '{node_cfg.node_type}'. "
                       f"Registered: {registry.registered_types()}",
            )

    # Pre-create the queue so the stream endpoint can attach before the task runs
    _job_queues[request.job_id] = asyncio.Queue(maxsize=2000)

    background_tasks.add_task(_run_pipeline, request)

    return {
        "job_id":       request.job_id,
        "status":       "accepted",
        "pipeline_id":  request.pipeline_config.pipeline_id,
        "node_ids":     [n.node_id for n in request.pipeline_config.nodes],
        "stream_url":   f"/pipeline/{request.job_id}/stream",
    }


@app.get(
    "/pipeline/{job_id}/stream",
    summary="SSE stream for a pipeline job",
)
async def stream_pipeline(job_id: str) -> StreamingResponse:
    """
    Returns a text/event-stream of PipelineEvents for the given job.
    Closes automatically when the pipeline completes or errors.
    """
    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.get(
    "/pipeline/{job_id}/result",
    summary="Fetch the completed pipeline result",
)
async def get_result(job_id: str) -> PipelineResult:
    result = _job_results.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not available yet or job not found.")
    return result


@app.get("/nodes", summary="List all registered node types")
async def list_nodes() -> dict:
    return {"registered_node_types": registry.registered_types()}


@app.get("/health")
async def health() -> dict:
    return {
        "status":      "ok",
        "active_jobs": len(_job_queues),
    }
