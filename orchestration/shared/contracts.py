"""
shared/contracts.py
───────────────────
Single source of truth for ALL data shapes that cross App A ↔ App B.
Both applications import only from here — no duplicated models.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Document data  (what the user submits in App A)
# ─────────────────────────────────────────────

class DocumentTable(BaseModel):
    """A single table from the documentation."""
    title: str
    columns: list[str]
    rows: list[list[Any]]           # each row = list of cell values
    notes: Optional[str] = None


class DocumentImage(BaseModel):
    """A base-64 encoded image with optional caption."""
    caption: str
    base64_data: str                # raw base64, no data-URI prefix
    media_type: Literal["image/png", "image/jpeg", "image/gif", "image/webp"] = "image/png"


class DocumentData(BaseModel):
    """Everything a user uploads from App A."""
    title: str
    description: Optional[str] = None
    tables: list[DocumentTable] = Field(default_factory=list)
    images: list[DocumentImage] = Field(default_factory=list)
    raw_text: Optional[str] = None  # any free-form text to include
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────
# Pipeline configuration
# ─────────────────────────────────────────────

class NodeType(str, Enum):
    """
    Registry of known node types.
    Add a new value here + register the class in app_b/pipeline/registry.py
    to extend the pipeline with a new capability.
    """
    COMMENTARY  = "commentary"   # Stage 1 — generate narrative commentary
    VALIDATION  = "validation"   # Stage 2 — validate/critique the commentary
    SUMMARY     = "summary"      # Optional — condense the whole output
    CRITIQUE    = "critique"     # Optional — adversarial quality check
    TRANSLATION = "translation"  # Optional — translate to another language
    # ← add more here freely; no other file needs to change


class NodeConfig(BaseModel):
    """
    Configuration for a single node in the pipeline.
    Stored in the pipeline request so App A fully controls the pipeline shape.
    """
    node_id: str = Field(..., description="Unique label for this node in the run, e.g. 'commentary_1'")
    node_type: NodeType
    prompt_template: str = Field(
        ...,
        description=(
            "Jinja2-style template. Available variables:\n"
            "  {{ document_title }}\n"
            "  {{ tables_markdown }}  — all tables rendered as Markdown\n"
            "  {{ previous_outputs }} — dict of node_id → output_text from earlier nodes\n"
            "  {{ raw_text }}        — user's raw text if any"
        ),
    )
    system_prompt: Optional[str] = None    # overrides default system prompt for this node
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1024
    temperature: float = 0.7
    params: dict[str, Any] = Field(default_factory=dict)  # node-specific extras


class PipelineConfig(BaseModel):
    """Ordered list of nodes that define the pipeline."""
    pipeline_id: str = Field(default_factory=lambda: f"pipe-{uuid4().hex[:8]}")
    nodes: list[NodeConfig] = Field(..., min_length=1)


# ─────────────────────────────────────────────
# Job request  (App A → App B)
# ─────────────────────────────────────────────

class PipelineRequest(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job-{uuid4().hex[:12]}")
    user_id: str = Field(..., description="Opaque user identifier from App A")
    document_data: DocumentData
    pipeline_config: PipelineConfig
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# SSE events  (App B → App A → browser)
# ─────────────────────────────────────────────

class PipelineEventType(str, Enum):
    PIPELINE_STARTED   = "pipeline.started"
    NODE_STARTED       = "node.started"
    TOKEN_RECEIVED     = "node.token"       # streaming LLM token
    NODE_COMPLETED     = "node.completed"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_ERROR     = "pipeline.error"


class PipelineEvent(BaseModel):
    """Every SSE frame is one of these."""
    event_type: PipelineEventType
    job_id: str
    node_id: Optional[str] = None           # None for pipeline-level events
    sequence: int = 0                        # monotonic counter per job
    payload: dict[str, Any] = Field(default_factory=dict)
    emitted_at: datetime = Field(default_factory=datetime.utcnow)

    def to_sse_frame(self) -> str:
        """Serialise to an SSE text frame."""
        return (
            f"event: {self.event_type.value}\n"
            f"data: {self.model_dump_json()}\n\n"
        )


# ─────────────────────────────────────────────
# Node & pipeline results  (stored, not streamed)
# ─────────────────────────────────────────────

class NodeResult(BaseModel):
    node_id: str
    node_type: NodeType
    output_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineResult(BaseModel):
    job_id: str
    user_id: str
    node_results: list[NodeResult] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def final_output(self) -> Optional[str]:
        """Convenience: the last node's output text."""
        return self.node_results[-1].output_text if self.node_results else None


# ─────────────────────────────────────────────
# App A job tracking
# ─────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"


class JobRecord(BaseModel):
    job_id: str
    user_id: str
    status: JobStatus = JobStatus.PENDING
    pipeline_config: PipelineConfig
    result: Optional[PipelineResult] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# Batch processing  (many tables → one session stream)
# ─────────────────────────────────────────────

class TableJobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class TableJob(BaseModel):
    """Tracks a single table within a batch."""
    table_index: int
    table_title: str
    job_id: str
    status: TableJobStatus = TableJobStatus.PENDING
    result: Optional[PipelineResult] = None
    error: Optional[str] = None


class BatchProgress(BaseModel):
    """Snapshot of a batch's current state — embedded in every session event."""
    batch_id: str
    total: int
    pending: int
    running: int
    completed: int
    failed: int

    @property
    def done(self) -> bool:
        return self.completed + self.failed == self.total


class BatchRecord(BaseModel):
    """Tracks an entire batch submitted by a user."""
    batch_id: str
    session_id: str
    user_id: str
    preset: str
    table_jobs: list[TableJob] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def progress(self) -> BatchProgress:
        statuses = [tj.status for tj in self.table_jobs]
        return BatchProgress(
            batch_id=self.batch_id,
            total=len(self.table_jobs),
            pending=statuses.count(TableJobStatus.PENDING),
            running=statuses.count(TableJobStatus.RUNNING),
            completed=statuses.count(TableJobStatus.COMPLETED),
            failed=statuses.count(TableJobStatus.FAILED),
        )


class SessionEvent(BaseModel):
    """
    Every SSE frame sent to the browser.

    Wraps a PipelineEvent with batch + session context so the client
    only needs ONE stream and can route events to the right table UI.
    """
    # Routing context
    session_id: str
    batch_id: str
    table_index: int
    table_title: str
    batch_progress: BatchProgress

    # The underlying pipeline event
    event_type: str        # mirrors PipelineEventType.value
    job_id: str
    node_id: Optional[str]
    sequence: int
    payload: dict[str, Any]
    emitted_at: datetime

    @classmethod
    def from_pipeline_event(
        cls,
        event: "PipelineEvent",
        session_id: str,
        batch_id: str,
        table_index: int,
        table_title: str,
        batch_progress: "BatchProgress",
    ) -> "SessionEvent":
        return cls(
            session_id=session_id,
            batch_id=batch_id,
            table_index=table_index,
            table_title=table_title,
            batch_progress=batch_progress,
            event_type=event.event_type.value,
            job_id=event.job_id,
            node_id=event.node_id,
            sequence=event.sequence,
            payload=event.payload,
            emitted_at=event.emitted_at,
        )

    def to_sse_frame(self) -> str:
        return (
            f"event: {self.event_type}\n"
            f"data: {self.model_dump_json()}\n\n"
        )


# ─────────────────────────────────────────────
# Batch submission request  (user → App A)
# Note: no prompt_template here — App A owns all prompts.
# ─────────────────────────────────────────────

class BatchAnalyzeRequest(BaseModel):
    """
    What a user sends to App A's POST /batch/analyze.
    Prompts are never exposed here — App A's PromptLibrary fills them in.
    """
    session_id: str = Field(..., description="Client-generated session ID (one per browser tab)")
    user_id: str
    tables: list[DocumentTable] = Field(..., min_length=1)
    document_context: Optional[str] = Field(
        default=None,
        description="Shared context for all tables (e.g. company name, report type, fiscal year)",
    )
    preset: str = Field(
        default="default",
        description="Prompt preset to use: default | commentary_only | full_with_summary",
    )
    concurrency: int = Field(
        default=5, ge=1, le=20,
        description="How many tables to process in parallel",
    )
