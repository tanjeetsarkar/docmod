"""
app_a/prompt_library.py
────────────────────────
App A is the SOLE owner of every prompt that goes to the LLM.
Users submit tables + context. App A injects the prompt.

To add a new preset:
  1. Add prompt strings as class constants
  2. Add a branch in build_pipeline_config()
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from shared.contracts import (
    DocumentTable,
    NodeConfig,
    NodeType,
    PipelineConfig,
)


class PromptLibrary:
    """
    All prompt templates live here as class-level constants.
    build_pipeline_config() assembles the right NodeConfig list
    for a given preset and document context.

    Variables available in every template (interpolated by BaseNode):
      {{ document_title }}   — the table title
      {{ tables_markdown }}  — the table rendered as Markdown
      {{ previous_outputs }} — outputs from upstream nodes
      {{ description }}      — document_context passed by the user
    """

    # ── Commentary prompts ─────────────────────────────────────────────────

    COMMENTARY_SYSTEM = (
        "You are an expert technical documentation writer. "
        "Produce clear, insightful commentary on data tables. "
        "Use specific numbers. Highlight trends, anomalies, and implications. "
        "Write in a professional but accessible style."
    )

    COMMENTARY_USER = """\
Analyse the following table and write a detailed commentary.

**Report context:** {{ description }}
**Table:** {{ document_title }}

{{ tables_markdown }}

Cover:
1. What the data shows overall
2. Key trends and patterns in the numbers
3. Notable outliers or anomalies
4. Implications or recommended actions for the reader

Be specific — cite exact values where they strengthen the insight.\
"""

    # ── Validation prompts ─────────────────────────────────────────────────

    VALIDATION_SYSTEM = (
        "You are a rigorous senior technical editor. "
        "You receive a commentary alongside the source table it describes. "
        "Your job is to check factual accuracy, completeness, and clarity."
    )

    VALIDATION_USER = """\
Validate the commentary below against the source table.

**Table:** {{ document_title }}
{{ tables_markdown }}

**Commentary to validate:**
{{ previous_outputs }}

Respond with exactly two sections:

**Issues Found:**
- List every factual inconsistency, missed insight, or unclear phrase.
- Cite specific cells or values when flagging an error.
- Write "None" if the commentary is accurate and complete.

**Improved Commentary:**
- Full rewrite incorporating your corrections.
- Must be grounded in the table data above.\
"""

    # ── Summary prompts ────────────────────────────────────────────────────

    SUMMARY_SYSTEM = (
        "You are an executive communications specialist. "
        "Synthesise analysis into crisp, decision-focused summaries."
    )

    SUMMARY_USER = """\
Produce an executive summary for the following analysis.

**Table:** {{ document_title }}

**Full analysis:**
{{ previous_outputs }}

Format:
• 3–5 bullet points (key findings, max 15 words each)
• One short paragraph (2–3 sentences) with the single most important takeaway.\
"""

    # ── Build helpers ──────────────────────────────────────────────────────

    @classmethod
    def build_pipeline_config(
        cls,
        preset: str,
        table: DocumentTable,
        document_context: str | None = None,
    ) -> PipelineConfig:
        """
        Returns a fully-populated PipelineConfig for a single table.
        The caller (batch orchestrator) should not know or care what the prompts say.
        """
        ctx = document_context or "No additional context provided."

        commentary_node = NodeConfig(
            node_id="commentary_1",
            node_type=NodeType.COMMENTARY,
            system_prompt=cls.COMMENTARY_SYSTEM,
            prompt_template=cls.COMMENTARY_USER.replace("{{ description }}", ctx),
            max_tokens=1024,
            temperature=0.7,
        )

        validation_node = NodeConfig(
            node_id="validation_1",
            node_type=NodeType.VALIDATION,
            system_prompt=cls.VALIDATION_SYSTEM,
            prompt_template=cls.VALIDATION_USER,
            max_tokens=1500,
            temperature=0.3,   # lower temp for fact-checking
        )

        summary_node = NodeConfig(
            node_id="summary_1",
            node_type=NodeType.SUMMARY,
            system_prompt=cls.SUMMARY_SYSTEM,
            prompt_template=cls.SUMMARY_USER,
            max_tokens=512,
            temperature=0.5,
        )

        if preset == "commentary_only":
            nodes = [commentary_node]
        elif preset == "full_with_summary":
            nodes = [commentary_node, validation_node, summary_node]
        else:
            # default: commentary → validation
            nodes = [commentary_node, validation_node]

        return PipelineConfig(nodes=nodes)

    @classmethod
    def available_presets(cls) -> list[str]:
        return ["default", "commentary_only", "full_with_summary"]
