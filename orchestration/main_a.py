"""
app_a/main.py
─────────────
App A — Documentation Application.

Responsibilities:
  • Accept document data (tables, images) + pipeline config from users
  • Submit jobs to App B and relay the SSE stream back to each user
  • Support multiple concurrent users — each gets their own isolated SSE stream
  • Provide sensible default pipeline configs so users don't have to specify them

Run:
    uvicorn app_a.main:app --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import json
import sys
import pathlib
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from shared.contracts import (
    DocumentData,
    DocumentImage,
    DocumentTable,
    JobRecord,
    JobStatus,
    NodeConfig,
    NodeType,
    PipelineConfig,
    PipelineEvent,
    PipelineEventType,
    PipelineRequest,
)

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

APP_B_BASE_URL = "http://localhost:8001"

# ─────────────────────────────────────────────
# In-memory stores
# ─────────────────────────────────────────────

# job_id → asyncio.Queue[str]  (SSE frame strings, ready to send)
_user_queues: dict[str, asyncio.Queue] = {}
# job_id → JobRecord
_jobs: dict[str, JobRecord] = {}


# ─────────────────────────────────────────────
# Default pipeline presets
# (users can override these or supply their own)
# ─────────────────────────────────────────────

DEFAULT_PIPELINE = PipelineConfig(
    nodes=[
        NodeConfig(
            node_id="commentary_1",
            node_type=NodeType.COMMENTARY,
            prompt_template=(
                "You are analysing the following document.\n\n"
                "**Title:** {{ document_title }}\n"
                "**Description:** {{ description }}\n\n"
                "**Tables:**\n{{ tables_markdown }}\n\n"
                "**Additional context:**\n{{ raw_text }}\n\n"
                "Write a detailed commentary covering:\n"
                "1. What the data shows overall\n"
                "2. Key trends and patterns\n"
                "3. Notable outliers or anomalies\n"
                "4. Implications for the reader\n"
            ),
        ),
        NodeConfig(
            node_id="validation_1",
            node_type=NodeType.VALIDATION,
            prompt_template=(
                "You are validating a commentary against the source data.\n\n"
                "**Original document title:** {{ document_title }}\n\n"
                "**Source tables:**\n{{ tables_markdown }}\n\n"
                "**Commentary to validate:**\n{{ previous_outputs }}\n\n"
                "Review the commentary strictly and provide your structured feedback."
            ),
        ),
    ]
)

PIPELINE_PRESETS: dict[str, PipelineConfig] = {
    "default":              DEFAULT_PIPELINE,
    "commentary_only":      PipelineConfig(
        nodes=[DEFAULT_PIPELINE.nodes[0]]
    ),
    "full_with_summary":    PipelineConfig(
        nodes=[
            DEFAULT_PIPELINE.nodes[0],
            DEFAULT_PIPELINE.nodes[1],
            NodeConfig(
                node_id="summary_1",
                node_type=NodeType.SUMMARY,
                prompt_template=(
                    "Summarise the following analysis for an executive audience.\n\n"
                    "**Document:** {{ document_title }}\n\n"
                    "**Full analysis:**\n{{ previous_outputs }}"
                ),
            ),
        ]
    ),
}


# ─────────────────────────────────────────────
# API request models
# ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """What the App A user sends."""
    user_id: str = Field(..., description="Client-assigned user identifier")
    document: DocumentData
    preset: str = Field(
        default="default",
        description="One of: default | commentary_only | full_with_summary",
    )
    # Optional: override the entire pipeline config
    pipeline_config: Optional[PipelineConfig] = None


# ─────────────────────────────────────────────
# SSE relay: App A → App B → App A → browser
# ─────────────────────────────────────────────

async def _relay_pipeline(job_id: str, pipeline_request: PipelineRequest) -> None:
    """
    Background task:
      1. POST to App B /pipeline/start
      2. Stream GET from App B /pipeline/{job_id}/stream
      3. Parse each SSE frame, update job status, forward to user's queue
    """
    queue = _user_queues[job_id]

    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)) as client:
        # Step 1 — submit job to App B
        try:
            resp = await client.post(
                f"{APP_B_BASE_URL}/pipeline/start",
                json=pipeline_request.model_dump(mode="json"),
            )
            resp.raise_for_status()
        except Exception as exc:
            err_frame = (
                "event: pipeline.error\n"
                f"data: {{\"error\": \"App B unreachable: {exc}\"}}\n\n"
            )
            await queue.put(err_frame)
            await queue.put(None)
            _jobs[job_id].status = JobStatus.FAILED
            return

        _jobs[job_id].status = JobStatus.RUNNING

        # Step 2 — stream events from App B
        try:
            async with client.stream(
                "GET",
                f"{APP_B_BASE_URL}/pipeline/{job_id}/stream",
            ) as stream:
                async for raw_line in stream.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        # Blank line ends a frame; forward the buffered frame
                        continue

                    if line.startswith(": done"):
                        _jobs[job_id].status = JobStatus.COMPLETED
                        await queue.put(None)  # sentinel
                        return

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()

                    elif line.startswith("data:"):
                        data_json = line[5:].strip()
                        try:
                            payload = json.loads(data_json)
                        except json.JSONDecodeError:
                            payload = {}

                        # Build SSE frame and forward
                        frame = f"event: {current_event_type}\ndata: {data_json}\n\n"
                        await queue.put(frame)

                        # Update job status on key events
                        if current_event_type == PipelineEventType.PIPELINE_COMPLETED:
                            _jobs[job_id].status = JobStatus.COMPLETED
                        elif current_event_type == PipelineEventType.PIPELINE_ERROR:
                            _jobs[job_id].status = JobStatus.FAILED

        except Exception as exc:
            err_frame = (
                "event: pipeline.error\n"
                f"data: {{\"error\": \"Stream interrupted: {exc}\"}}\n\n"
            )
            await queue.put(err_frame)
            _jobs[job_id].status = JobStatus.FAILED

        finally:
            await queue.put(None)


async def _user_sse_generator(job_id: str) -> AsyncGenerator[str, None]:
    """Reads from the user's queue and yields SSE frames to the browser."""
    queue = _user_queues.get(job_id)
    if queue is None:
        yield "event: pipeline.error\ndata: {\"error\": \"Job not found\"}\n\n"
        return

    while True:
        frame = await queue.get()
        if frame is None:
            yield ": stream-complete\n\n"
            break
        yield frame


# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(
    title="Documentation App (App A)",
    version="1.0.0",
    description="Documentation analysis frontend — submits jobs to the LLM pipeline gateway.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/analyze",
    status_code=202,
    summary="Submit a document for pipeline analysis",
)
async def analyze(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Accepts a document + user preference, picks/builds a pipeline config,
    creates a job, and kicks off the relay task.
    Returns the job_id immediately; user then subscribes to /stream/{job_id}.
    """
    # Resolve pipeline config
    if request.pipeline_config:
        pipeline_cfg = request.pipeline_config
    else:
        pipeline_cfg = PIPELINE_PRESETS.get(request.preset, DEFAULT_PIPELINE)

    job_id = f"job-{uuid.uuid4().hex[:12]}"

    pipeline_request = PipelineRequest(
        job_id=job_id,
        user_id=request.user_id,
        document_data=request.document,
        pipeline_config=pipeline_cfg,
    )

    # Set up isolated queue for this user's job
    _user_queues[job_id] = asyncio.Queue(maxsize=2000)
    _jobs[job_id] = JobRecord(
        job_id=job_id,
        user_id=request.user_id,
        pipeline_config=pipeline_cfg,
    )

    background_tasks.add_task(_relay_pipeline, job_id, pipeline_request)

    return {
        "job_id":      job_id,
        "user_id":     request.user_id,
        "preset":      request.preset,
        "pipeline_id": pipeline_cfg.pipeline_id,
        "node_ids":    [n.node_id for n in pipeline_cfg.nodes],
        "stream_url":  f"/stream/{job_id}",
        "status_url":  f"/jobs/{job_id}",
    }


@app.get(
    "/stream/{job_id}",
    summary="SSE stream for a specific job",
)
async def stream_job(job_id: str) -> StreamingResponse:
    """
    Browser / client connects here to receive the live SSE event stream
    for their job.  Multiple users can connect simultaneously — each gets
    their own isolated queue.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return StreamingResponse(
        _user_sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.get("/jobs/{job_id}", summary="Get job status")
async def get_job(job_id: str) -> JobRecord:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/jobs", summary="List all jobs (for debugging)")
async def list_jobs() -> dict:
    return {
        "total": len(_jobs),
        "jobs": [
            {"job_id": j.job_id, "user_id": j.user_id, "status": j.status}
            for j in _jobs.values()
        ],
    }


@app.get("/presets", summary="List available pipeline presets")
async def list_presets() -> dict:
    return {
        name: {
            "pipeline_id": cfg.pipeline_id,
            "nodes": [{"node_id": n.node_id, "node_type": n.node_type} for n in cfg.nodes],
        }
        for name, cfg in PIPELINE_PRESETS.items()
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "active_jobs": len(_jobs)}


# ─────────────────────────────────────────────
# Quick test UI  (open in browser to try it live)
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def test_ui():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DocPipeline — Test UI</title>
<style>
  body { font-family: 'Courier New', monospace; background: #0d0d0d; color: #ccc;
         max-width: 900px; margin: 40px auto; padding: 0 20px; }
  h1   { color: #fff; letter-spacing: 2px; }
  textarea, select, input { width: 100%; background: #1a1a1a; color: #0f0;
         border: 1px solid #333; padding: 10px; margin: 6px 0 14px;
         font-family: monospace; font-size: 13px; border-radius: 4px; }
  button { background: #0f0; color: #000; border: none; padding: 12px 28px;
           font-weight: bold; cursor: pointer; border-radius: 4px; font-size: 14px; }
  button:disabled { background: #444; color: #888; }
  #log { background: #111; border: 1px solid #333; padding: 14px;
         height: 420px; overflow-y: auto; font-size: 12px; line-height: 1.7;
         border-radius: 4px; white-space: pre-wrap; }
  .node-start { color: #4af; font-weight: bold; }
  .token      { color: #0f0; }
  .node-done  { color: #fa4; font-weight: bold; }
  .pipe-done  { color: #f4f; font-weight: bold; }
  .error      { color: #f44; }
</style>
</head>
<body>
<h1>📄 DocPipeline Test UI</h1>

<label>User ID</label>
<input id="userId" value="user-demo-001" />

<label>Preset</label>
<select id="preset">
  <option value="default">default (commentary → validation)</option>
  <option value="commentary_only">commentary_only</option>
  <option value="full_with_summary">full_with_summary (→ summary)</option>
</select>

<label>Document JSON (tables + metadata)</label>
<textarea id="docJson" rows="10">{
  "title": "Q1 2026 Sales Report",
  "description": "Regional sales performance for Q1 2026",
  "tables": [
    {
      "title": "Revenue by Region",
      "columns": ["Region", "Q1 2025 (₹ Cr)", "Q1 2026 (₹ Cr)", "YoY Growth"],
      "rows": [
        ["North", 42.1, 56.8, "+34.9%"],
        ["South", 38.7, 41.2, "+6.5%"],
        ["East",  29.3, 38.9, "+32.8%"],
        ["West",  51.4, 49.1, "-4.5%"]
      ]
    }
  ],
  "raw_text": "West region decline attributed to supply chain disruptions in Rajasthan."
}</textarea>

<button id="runBtn" onclick="runPipeline()">▶ Run Pipeline</button>

<div style="margin-top:20px;font-size:12px;color:#555;">Job ID: <span id="jobId">—</span></div>
<div id="log" style="margin-top:10px;"></div>

<script>
let evtSource = null;

async function runPipeline() {
  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Running…';
  const log = document.getElementById('log');
  log.innerHTML = '';

  let doc;
  try { doc = JSON.parse(document.getElementById('docJson').value); }
  catch(e) { log.innerHTML = '<span class="error">Invalid JSON: ' + e + '</span>'; btn.disabled=false; btn.textContent='▶ Run Pipeline'; return; }

  const payload = {
    user_id:  document.getElementById('userId').value,
    document: doc,
    preset:   document.getElementById('preset').value,
  };

  const resp = await fetch('/analyze', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const job = await resp.json();
  document.getElementById('jobId').textContent = job.job_id;
  log.innerHTML += '<span class="node-start">✓ Job created: ' + job.job_id + '\\nNodes: ' + job.node_ids.join(' → ') + '\\n\\n</span>';

  if (evtSource) evtSource.close();
  evtSource = new EventSource('/stream/' + job.job_id);

  evtSource.addEventListener('node.started', e => {
    const d = JSON.parse(e.data);
    log.innerHTML += '<span class="node-start">▶ [' + d.node_id + '] started (' + (d.payload.node_type||'') + ')\\n</span>';
    log.scrollTop = log.scrollHeight;
  });

  evtSource.addEventListener('node.token', e => {
    const d = JSON.parse(e.data);
    log.innerHTML += '<span class="token">' + d.payload.token.replace(/</g,'&lt;') + '</span>';
    log.scrollTop = log.scrollHeight;
  });

  evtSource.addEventListener('node.completed', e => {
    const d = JSON.parse(e.data);
    log.innerHTML += '\\n<span class="node-done">✓ [' + d.node_id + '] done (' + Math.round(d.payload.result.duration_ms) + 'ms)\\n\\n</span>';
    log.scrollTop = log.scrollHeight;
  });

  evtSource.addEventListener('pipeline.completed', e => {
    const d = JSON.parse(e.data);
    log.innerHTML += '<span class="pipe-done">\\n🏁 PIPELINE COMPLETE — ' + d.payload.nodes_completed + ' nodes, ' + Math.round(d.payload.total_duration_ms) + 'ms\\n</span>';
    evtSource.close();
    btn.disabled = false;
    btn.textContent = '▶ Run Pipeline';
  });

  evtSource.addEventListener('pipeline.error', e => {
    const d = JSON.parse(e.data);
    log.innerHTML += '\\n<span class="error">✗ ERROR: ' + (d.payload.error||'unknown') + '\\n</span>';
    evtSource.close();
    btn.disabled = false;
    btn.textContent = '▶ Run Pipeline';
  });
}
</script>
</body>
</html>
"""
