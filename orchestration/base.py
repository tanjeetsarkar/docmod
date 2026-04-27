"""
app_b/pipeline/nodes/base.py
────────────────────────────
Abstract base for every pipeline node.

To add a new node type:
  1. Create a subclass of BaseNode
  2. Implement `default_system_prompt` property
  3. Register it in app_b/pipeline/registry.py
  That's it.
"""
from __future__ import annotations

import sys
import pathlib
import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent.parent))

from shared.contracts import (
    DocumentData, NodeConfig, NodeResult, NodeType,
    PipelineEvent, PipelineEventType,
)


def _table_to_markdown(table) -> str:
    """Render a DocumentTable as a Markdown table string."""
    header = "| " + " | ".join(str(c) for c in table.columns) + " |"
    sep    = "| " + " | ".join("---" for _ in table.columns) + " |"
    rows   = "\n".join(
        "| " + " | ".join(str(cell) for cell in row) + " |"
        for row in table.rows
    )
    note = f"\n*{table.notes}*" if table.notes else ""
    return f"### {table.title}\n{header}\n{sep}\n{rows}{note}"


class BaseNode(ABC):
    """
    Every pipeline node follows this contract.

    App B's PipelineEngine calls:
        async for event in node.execute(doc, prev_results, job_id, seq_start):
            yield event
    """

    def __init__(self, config: NodeConfig) -> None:
        self.config = config
        self.node_id = config.node_id

    # ── Subclasses must provide ────────────────────────────────────────────

    @property
    @abstractmethod
    def default_system_prompt(self) -> str:
        """Fallback system prompt when the NodeConfig doesn't supply one."""

    # ── Public execution entry point ───────────────────────────────────────

    async def execute(
        self,
        document_data: DocumentData,
        previous_results: dict[str, NodeResult],
        job_id: str,
        seq: int = 0,
    ) -> AsyncGenerator[PipelineEvent, None]:
        """
        Run this node.  Yields PipelineEvents:
          NODE_STARTED → TOKEN_RECEIVED (×N) → NODE_COMPLETED
        """
        t0 = time.monotonic()

        yield self._event(PipelineEventType.NODE_STARTED, job_id, seq, {
            "node_type": self.config.node_type,
            "model":     self.config.model,
        })
        seq += 1

        # Build the prompt by interpolating the template
        prompt = self._render_prompt(document_data, previous_results)
        system = self.config.system_prompt or self.default_system_prompt
        messages = [{"role": "user", "content": prompt}]

        # Add image content if present and this node should see them
        if document_data.images and self._include_images():
            messages = self._inject_images(messages, document_data)

        # Stream from LLM
        full_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            import anthropic
            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

            with client.messages.stream(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=messages,
                temperature=self.config.temperature,
            ) as stream:
                for text_chunk in stream.text_stream:
                    full_text += text_chunk
                    yield self._event(PipelineEventType.TOKEN_RECEIVED, job_id, seq, {
                        "token": text_chunk,
                    })
                    seq += 1

                # Final usage stats from the stream
                final_msg = stream.get_final_message()
                input_tokens  = final_msg.usage.input_tokens
                output_tokens = final_msg.usage.output_tokens

        except Exception as exc:
            yield self._event(PipelineEventType.PIPELINE_ERROR, job_id, seq, {
                "node_id": self.node_id,
                "error":   str(exc),
            })
            return

        duration_ms = (time.monotonic() - t0) * 1000
        result = NodeResult(
            node_id=self.node_id,
            node_type=self.config.node_type,
            output_text=full_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )

        yield self._event(PipelineEventType.NODE_COMPLETED, job_id, seq, {
            "result": result.model_dump(),
        })

    # ── Helpers ────────────────────────────────────────────────────────────

    def _render_prompt(
        self,
        document_data: DocumentData,
        previous_results: dict[str, NodeResult],
    ) -> str:
        """
        Interpolate the prompt_template with document context.
        Uses simple .replace() — swap for Jinja2 if you need logic.
        """
        tables_md = "\n\n".join(
            _table_to_markdown(t) for t in document_data.tables
        ) or "*(no tables)*"

        prev_outputs_text = "\n\n".join(
            f"--- Output from [{nid}] ---\n{r.output_text}"
            for nid, r in previous_results.items()
        ) or "*(this is the first node — no prior outputs)*"

        return (
            self.config.prompt_template
            .replace("{{ document_title }}",   document_data.title)
            .replace("{{ tables_markdown }}",  tables_md)
            .replace("{{ previous_outputs }}", prev_outputs_text)
            .replace("{{ raw_text }}",         document_data.raw_text or "")
            .replace("{{ description }}",      document_data.description or "")
        )

    def _include_images(self) -> bool:
        """Override to False in nodes that should not process images."""
        return True

    def _inject_images(self, messages: list[dict], doc: DocumentData) -> list[dict]:
        """Prepend image content blocks to the user message."""
        content: list[dict] = []
        for img in doc.images:
            content.append({
                "type": "image",
                "source": {
                    "type":       "base64",
                    "media_type": img.media_type,
                    "data":       img.base64_data,
                },
            })
            if img.caption:
                content.append({"type": "text", "text": f"Image caption: {img.caption}"})

        # Merge with the original text message
        original_text = messages[0]["content"]
        content.append({"type": "text", "text": original_text})
        return [{"role": "user", "content": content}]

    def _event(
        self,
        event_type: PipelineEventType,
        job_id: str,
        seq: int,
        payload: dict,
    ) -> PipelineEvent:
        return PipelineEvent(
            event_type=event_type,
            job_id=job_id,
            node_id=self.node_id,
            sequence=seq,
            payload=payload,
        )
