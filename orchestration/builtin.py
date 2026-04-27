"""
app_b/pipeline/nodes/builtin.py
────────────────────────────────
All built-in node implementations live here.
Adding a new node = add a class below + register it in registry.py.
"""
from __future__ import annotations

from .base import BaseNode


# ─────────────────────────────────────────────
# Stage 1: Commentary
# ─────────────────────────────────────────────

class CommentaryNode(BaseNode):
    """
    Generates a narrative commentary for the document data.
    This is typically the first node in the pipeline.
    """

    @property
    def default_system_prompt(self) -> str:
        return (
            "You are an expert technical documentation writer. "
            "Your role is to produce clear, insightful, and well-structured "
            "commentary on data, tables, and charts. "
            "Write in a professional yet accessible style. "
            "Highlight key trends, anomalies, and actionable insights. "
            "Use specific numbers and comparisons where they add value."
        )


# ─────────────────────────────────────────────
# Stage 2: Validation
# ─────────────────────────────────────────────

class ValidationNode(BaseNode):
    """
    Validates and critiques the commentary produced by a prior node.
    Receives previous_outputs via the prompt template and checks for:
    - Factual consistency with the source data
    - Completeness
    - Clarity issues
    - Suggestions for improvement
    """

    @property
    def default_system_prompt(self) -> str:
        return (
            "You are a rigorous senior technical editor. "
            "You receive a commentary alongside the original data it describes. "
            "Your job is to:\n"
            "1. Identify any factual inconsistencies between the commentary and the data.\n"
            "2. Flag missing insights that should have been mentioned.\n"
            "3. Point out unclear or ambiguous phrasing.\n"
            "4. Provide a corrected/improved version of the commentary.\n"
            "Be specific — cite exact numbers, rows, or columns when flagging issues. "
            "Structure your response as:\n"
            "**Issues Found:** (bullet list)\n"
            "**Improved Commentary:** (full rewrite)\n"
        )

    def _include_images(self) -> bool:
        # Validation nodes work on text — images already interpreted by commentary
        return False


# ─────────────────────────────────────────────
# Stage 3: Summary  (optional — add to pipeline_config if needed)
# ─────────────────────────────────────────────

class SummaryNode(BaseNode):
    """
    Condenses all prior node outputs into an executive summary.
    """

    @property
    def default_system_prompt(self) -> str:
        return (
            "You are an executive communications specialist. "
            "Synthesise the analysis and validation you receive into a concise "
            "executive summary of 3–5 bullet points followed by one short paragraph. "
            "Use plain language. Avoid jargon. "
            "The summary must be actionable and decision-focused."
        )

    def _include_images(self) -> bool:
        return False


# ─────────────────────────────────────────────
# Stage N: Critique  (adversarial check)
# ─────────────────────────────────────────────

class CritiqueNode(BaseNode):
    """
    Adversarial quality gate.  Asks hard questions about the analysis.
    Great as a final node before delivery.
    """

    @property
    def default_system_prompt(self) -> str:
        return (
            "You are a sceptical analyst who challenges assumptions. "
            "Review all prior outputs and ask the hardest questions: "
            "What could be wrong? What alternative interpretations exist? "
            "What data is missing that would change the conclusion? "
            "What biases might the commentary reflect? "
            "Be constructive but unsparing."
        )

    def _include_images(self) -> bool:
        return False
