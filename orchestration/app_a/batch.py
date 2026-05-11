"""
app_a/batch.py
──────────────
BatchOrchestrator: processes N tables concurrently (semaphore-controlled),
routes ALL events from ALL tables into ONE session-level asyncio.Queue.

The session queue is the only connection point with App A's SSE layer.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import pathlib
import uuid
from datetime import datetime

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from shared.contracts import (
    BatchRecord,
    DocumentData,
    PipelineEvent,
    PipelineEventType,
    PipelineRequest,
    PipelineResult,
    SessionEvent,
    TableJob,
    TableJobStatus,
)
from app_a.prompt_library import PromptLibrary

logger = logging.getLogger(__name__)

APP_B_BASE_URL = "http://localhost:8001"

# ─────────────────────────────────────────────────────────────────
# Module-level session store
# session_id → asyncio.Queue[str | None]
#   str  = SSE frame ready to send
#   None = sentinel (stream closed)
# ─────────────────────────────────────────────────────────────────
_session_queues: dict[str, asyncio.Queue] = {}
_batch_records:  dict[str, BatchRecord]   = {}


def get_or_create_session_queue(session_id: str) -> asyncio.Queue:
    """
    Sessions are long-lived (one per browser tab).
    Calling this multiple times for the same session_id is safe.
    """
    if session_id not in _session_queues:
        _session_queues[session_id] = asyncio.Queue(maxsize=10_000)
    return _session_queues[session_id]


def get_batch(batch_id: str) -> BatchRecord | None:
    return _batch_records.get(batch_id)


def list_batches_for_session(session_id: str) -> list[BatchRecord]:
    return [b for b in _batch_records.values() if b.session_id == session_id]


# ─────────────────────────────────────────────────────────────────
# Core orchestrator
# ─────────────────────────────────────────────────────────────────

class BatchOrchestrator:
    """
    submit_batch()  — public entry point, call from App A's POST /batch/analyze
    """

    async def submit_batch(
        self,
        session_id: str,
        user_id: str,
        tables: list,            # list[DocumentTable]
        document_context: str | None,
        preset: str,
        concurrency: int,
    ) -> BatchRecord:
        """
        Creates a BatchRecord, registers it, and starts async processing.
        Returns immediately — caller gets batch_id and can subscribe to the stream.
        """
        batch_id = f"batch-{uuid.uuid4().hex[:10]}"

        # Build per-table job stubs
        table_jobs = [
            TableJob(
                table_index=i,
                table_title=table.title,
                job_id=f"job-{uuid.uuid4().hex[:10]}",
                status=TableJobStatus.PENDING,
            )
            for i, table in enumerate(tables)
        ]

        record = BatchRecord(
            batch_id=batch_id,
            session_id=session_id,
            user_id=user_id,
            preset=preset,
            table_jobs=table_jobs,
        )
        _batch_records[batch_id] = record

        # Ensure session queue exists
        get_or_create_session_queue(session_id)

        # Fire-and-forget — caller subscribes to the stream separately
        asyncio.create_task(
            self._run_batch(record, tables, document_context, concurrency)
        )

        return record

    # ── Private batch runner ───────────────────────────────────────────────

    async def _run_batch(
        self,
        record: BatchRecord,
        tables: list,
        document_context: str | None,
        concurrency: int,
    ) -> None:
        semaphore = asyncio.Semaphore(concurrency)

        tasks = [
            self._process_table(
                semaphore=semaphore,
                record=record,
                table_job=record.table_jobs[i],
                table=tables[i],
                document_context=document_context,
            )
            for i in range(len(tables))
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        record.completed_at = datetime.utcnow()

        # Push a batch-level completion sentinel to the session queue
        await self._push_batch_done(record)

    async def _process_table(
        self,
        semaphore: asyncio.Semaphore,
        record: BatchRecord,
        table_job: TableJob,
        table,               # DocumentTable
        document_context: str | None,
    ) -> None:
        """Process one table: acquire semaphore → call App B → relay events."""
        async with semaphore:
            table_job.status = TableJobStatus.RUNNING
            queue = _session_queues[record.session_id]

            # Build document and pipeline config (App A owns the prompts)
            doc_data = DocumentData(
                title=table.title,
                description=document_context,
                tables=[table],
            )
            pipeline_cfg = PromptLibrary.build_pipeline_config(
                preset=record.preset,
                table=table,
                document_context=document_context,
            )
            pipeline_request = PipelineRequest(
                job_id=table_job.job_id,
                user_id=record.user_id,
                document_data=doc_data,
                pipeline_config=pipeline_cfg,
            )

            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)
                ) as client:
                    # 1. Submit job to App B
                    resp = await client.post(
                        f"{APP_B_BASE_URL}/pipeline/start",
                        json=pipeline_request.model_dump(mode="json"),
                    )
                    resp.raise_for_status()

                    # 2. Stream events from App B, wrap them, push to session queue
                    current_event_type: str = ""

                    async with client.stream(
                        "GET",
                        f"{APP_B_BASE_URL}/pipeline/{table_job.job_id}/stream",
                    ) as stream:
                        async for raw_line in stream.aiter_lines():
                            line = raw_line.strip()
                            if not line:
                                continue

                            if line.startswith(": done"):
                                break

                            elif line.startswith("event:"):
                                current_event_type = line[6:].strip()

                            elif line.startswith("data:") and current_event_type:
                                data_json = line[5:].strip()
                                try:
                                    raw = json.loads(data_json)
                                    pipeline_event = PipelineEvent(**raw)
                                except Exception:
                                    continue

                                # Capture the final result
                                if pipeline_event.event_type == PipelineEventType.PIPELINE_COMPLETED:
                                    result_data = pipeline_event.payload.get("result", {})
                                    if result_data:
                                        table_job.result = PipelineResult(**result_data)
                                    table_job.status = TableJobStatus.COMPLETED

                                elif pipeline_event.event_type == PipelineEventType.PIPELINE_ERROR:
                                    table_job.status = TableJobStatus.FAILED
                                    table_job.error = pipeline_event.payload.get("error", "unknown")

                                # Wrap and push to session queue
                                session_event = SessionEvent.from_pipeline_event(
                                    event=pipeline_event,
                                    session_id=record.session_id,
                                    batch_id=record.batch_id,
                                    table_index=table_job.table_index,
                                    table_title=table_job.table_title,
                                    batch_progress=record.progress(),
                                )
                                try:
                                    queue.put_nowait(session_event.to_sse_frame())
                                except asyncio.QueueFull:
                                    logger.warning(
                                        "Session queue full for %s — dropping event for table %d",
                                        record.session_id, table_job.table_index,
                                    )

            except Exception as exc:
                logger.exception(
                    "Error processing table %d (%s) in batch %s",
                    table_job.table_index, table_job.table_title, record.batch_id,
                )
                table_job.status = TableJobStatus.FAILED
                table_job.error = str(exc)

                # Push an error event so the client knows this table failed
                error_frame = (
                    f"event: pipeline.error\n"
                    f"data: {{"
                    f'"session_id":"{record.session_id}",'
                    f'"batch_id":"{record.batch_id}",'
                    f'"table_index":{table_job.table_index},'
                    f'"table_title":"{table_job.table_title}",'
                    f'"error":"{exc}",'
                    f'"batch_progress":{record.progress().model_dump_json()}'
                    f"}}\n\n"
                )
                try:
                    _session_queues[record.session_id].put_nowait(error_frame)
                except asyncio.QueueFull:
                    pass

    async def _push_batch_done(self, record: BatchRecord) -> None:
        """Push a synthetic batch-level completion frame to the session queue."""
        progress = record.progress()
        frame = (
            f"event: batch.completed\n"
            f"data: {{"
            f'"session_id":"{record.session_id}",'
            f'"batch_id":"{record.batch_id}",'
            f'"batch_progress":{progress.model_dump_json()},'
            f'"completed_at":"{record.completed_at.isoformat() if record.completed_at else ""}"'
            f"}}\n\n"
        )
        try:
            _session_queues[record.session_id].put_nowait(frame)
        except asyncio.QueueFull:
            logger.warning("Session queue full when pushing batch.completed for %s", record.batch_id)


# Module-level singleton
orchestrator = BatchOrchestrator()
