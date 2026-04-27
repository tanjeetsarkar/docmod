"""
app_b/pipeline/engine.py
─────────────────────────
PipelineEngine — orchestrates nodes in order,
threads each node's output into the next node's context,
and yields a unified stream of PipelineEvents.
"""
from __future__ import annotations

import sys
import pathlib
import time
from typing import AsyncGenerator

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from shared.contracts import (
    NodeResult,
    PipelineEvent,
    PipelineEventType,
    PipelineRequest,
    PipelineResult,
)
from app_b.pipeline.registry import registry


class PipelineEngine:
    """
    Usage (in App B):
        async for event in engine.run(request):
            yield event.to_sse_frame()
    """

    async def run(
        self,
        request: PipelineRequest,
    ) -> AsyncGenerator[PipelineEvent, None]:

        job_id    = request.job_id
        doc_data  = request.document_data
        nodes_cfg = request.pipeline_config.nodes

        t_pipeline_start = time.monotonic()
        seq = 0

        # ── Pipeline started ───────────────────────────────────────────────
        yield PipelineEvent(
            event_type=PipelineEventType.PIPELINE_STARTED,
            job_id=job_id,
            sequence=seq,
            payload={
                "pipeline_id": request.pipeline_config.pipeline_id,
                "node_count":  len(nodes_cfg),
                "node_ids":    [n.node_id for n in nodes_cfg],
                "user_id":     request.user_id,
            },
        )
        seq += 1

        # ── Per-node execution ─────────────────────────────────────────────
        previous_results: dict[str, NodeResult] = {}
        all_results: list[NodeResult] = []
        error_occurred = False

        for node_cfg in nodes_cfg:
            node = registry.create(node_cfg)
            node_result: NodeResult | None = None

            try:
                async for event in node.execute(
                    document_data=doc_data,
                    previous_results=previous_results,
                    job_id=job_id,
                    seq=seq,
                ):
                    # Track sequence across nodes
                    seq = event.sequence + 1

                    if event.event_type == PipelineEventType.NODE_COMPLETED:
                        # Extract and cache the result for downstream nodes
                        node_result = NodeResult(**event.payload["result"])
                        previous_results[node_cfg.node_id] = node_result
                        all_results.append(node_result)

                    elif event.event_type == PipelineEventType.PIPELINE_ERROR:
                        error_occurred = True
                        yield event
                        break

                    yield event

            except Exception as exc:
                error_occurred = True
                yield PipelineEvent(
                    event_type=PipelineEventType.PIPELINE_ERROR,
                    job_id=job_id,
                    node_id=node_cfg.node_id,
                    sequence=seq,
                    payload={"error": str(exc), "node_id": node_cfg.node_id},
                )
                break

            if error_occurred:
                break

        # ── Pipeline completed ─────────────────────────────────────────────
        total_duration_ms = (time.monotonic() - t_pipeline_start) * 1000

        result = PipelineResult(
            job_id=job_id,
            user_id=request.user_id,
            node_results=all_results,
            total_duration_ms=total_duration_ms,
            error="pipeline aborted — see error events" if error_occurred else None,
        )
        result.completed_at = __import__("datetime").datetime.utcnow()

        yield PipelineEvent(
            event_type=PipelineEventType.PIPELINE_COMPLETED,
            job_id=job_id,
            sequence=seq,
            payload={
                "result":            result.model_dump(),
                "total_duration_ms": total_duration_ms,
                "nodes_completed":   len(all_results),
                "error":             result.error,
            },
        )
