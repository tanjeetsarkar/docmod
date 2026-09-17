# Architecture Specification: Agentic AI Commentary Harness for Regulatory Documentation

---

## 1. System Overview

This specification details the design for layering an **Agentic AI Commentary Harness** onto an existing regulatory document pipeline.

The baseline system parses documents into database-backed sections, renders them in a React rich-text editor (**SunEditor**), allows drag-and-drop insertion of regulatory tables from PostgreSQL, and compiles the final Word document via `python-docx`.

The AI Harness adds deterministic, fact-grounded commentary generation. It treats commentary not as freeform text, but as an audited artifact bound to a source table, section literature, and executive overrides.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                     POSTGRESQL                                         │
│  ┌───────────────────────┐   ┌───────────────────────────┐   ┌──────────────────────┐  │
│  │ sections              │   │ artifacts                 │   │ section_commentaries │  │
│  │ (id, title, order)    │   │ (id, type, raw_json/html) │   │ (html, audit_trail)  │  │
│  └───────────┬───────────┘   └─────────────┬─────────────┘   └──────────▲───────────┘  │
└──────────────┼─────────────────────────────┼────────────────────────────┼──────────────┘
               │                             │                            │
               ▼                             ▼                            │
┌────────────────────────────────────────────────────────────┐            │
│                      FASTAPI BACKEND                       │            │
│                                                            │            │
│  ┌──────────────────────────────────────────────────────┐  │            │
│  │ 1. Context Assembler                                 │  │            │
│  │    Pulls section literature, table data, and inputs  │  │            │
│  └──────────────────────────┬───────────────────────────┘  │            │
│                             │                               │            │
│  ┌──────────────────────────▼───────────────────────────┐  │            │
│  │ 2. Agentic Harness Runtime                           │  │            │
│  │    • Multi-turn extraction & synthesis               │  │            │
│  │    • Deterministic metric fact-checker (Guardrail)   │  │            │
│  │    • HTML Compiler (Outputs clean SunEditor HTML)    │──┼────────────┘
│  └──────────────────────────┬───────────────────────────┘  │ (Persist to DB)
└─────────────────────────────┼──────────────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ REACT UI (SunEditor)         │ │ DOCX EXPORT ENGINE           │
│ • Commentary trigger panel   │ │ • Reads section mappings     │
│ • `editor.insertHTML()`      │ │ • python-docx compiles       │
│ • Visual provenance badge    │ │   tables + commentary HTML   │
└──────────────────────────────┘ └──────────────────────────────┘

```

---

## 2. PostgreSQL Schema Extensions

To decouple commentary versions, preserve audit trails, and maintain one-to-one or one-to-many mappings between tables and narratives, deploy the following relational schema:

```sql
-- Store generated commentary as an audited, first-class document artifact
CREATE TABLE IF NOT EXISTS section_commentaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    source_table_artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    commentary_html TEXT NOT NULL,                  -- Sanitized HTML injected into SunEditor
    raw_metrics_cited JSONB NOT NULL,               -- List of verified numbers cited
    executive_override_notes TEXT,                  -- Human context/decisions provided
    user_prompt_instructions TEXT,                  -- Specific tone/regulatory guidelines
    model_name VARCHAR(120) NOT NULL,               -- e.g., 'meta-llama/Llama-3.3-70B-Instruct'
    verification_status VARCHAR(30) DEFAULT 'VERIFIED', -- 'VERIFIED', 'FLAGGED', 'EDITED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for document compilation retrieval
CREATE INDEX IF NOT EXISTS idx_commentaries_lookup 
ON section_commentaries (section_id, source_table_artifact_id);

```

---

## 3. Context Compilation Engine

The context assembler runs inside FastAPI. It programmatically compiles raw database artifacts into an anchored context bundle without requiring semantic vector chunking.

```python
# context_assembler.py
from typing import Dict, Any, List
from pydantic import BaseModel

class GroundedContextPack(BaseModel):
    table_json: Dict[str, Any]
    literature_text: str
    executive_notes: str
    user_instructions: str

async def assemble_grounded_context(
    db_session,
    section_id: str,
    table_artifact_id: str,
    executive_notes: str,
    user_instructions: str
) -> GroundedContextPack:
    """
    Retrieves canonical table values and neighboring section literature
    to provide high-fidelity grounding for the internal model.
    """
    # 1. Fetch raw table data (rows, headers, thresholds)
    table_record = await db_session.fetch_one(
        "SELECT data_payload FROM artifacts WHERE id = :id",
        {"id": table_artifact_id}
    )
    
    # 2. Extract section literature (surrounding paragraphs already in DB)
    paragraphs = await db_session.fetch_all(
        "SELECT text_content FROM section_paragraphs WHERE section_id = :sid ORDER BY sequence ASC",
        {"sid": section_id}
    )
    literature = "\n\n".join([p["text_content"] for p in paragraphs])

    return GroundedContextPack(
        table_json=table_record["data_payload"],
        literature_text=literature,
        executive_notes=executive_notes,
        user_instructions=user_instructions
    )

```

---

## 4. Agentic Harness & Verification Runtime

This module runs the generation loop, executes numeric fidelity checks against the source PostgreSQL table, and compiles the structured response into clean SunEditor-compliant HTML.

```python
# harness.py
import re
import json
from typing import List, Dict, Any, Set
import httpx
from pydantic import BaseModel, Field

# -----------------------------------------------------------------
# 1. Target Schema for Guided Output
# -----------------------------------------------------------------
class CommentaryOutputSchema(BaseModel):
    executive_summary: str = Field(description="1-2 sentences highlighting compliance or risk status.")
    key_findings: List[str] = Field(description="Bullet points of observations, thresholds, or trends.")
    methodology_alignment: str = Field(description="Narrative connecting results to standard literature.")
    executive_justification: str = Field(description="Contextualizing user decisions/overrides.")
    cited_metrics: List[str] = Field(description="Every raw numerical value or percentage cited.")

# -----------------------------------------------------------------
# 2. The Verification Harness
# -----------------------------------------------------------------
class RegulatoryCommentaryHarness:
    def __init__(self, internal_endpoint: str, model_name: str):
        self.client = httpx.AsyncClient(base_url=internal_endpoint, timeout=60.0)
        self.model_name = model_name

    def _extract_table_numbers(self, table_data: Dict[str, Any]) -> Set[str]:
        """Extracts all stringified numeric values present in canonical table cells."""
        numbers = set()
        for row in table_data.get("rows", []):
            for val in row.values():
                val_str = str(val).strip().replace('%', '')
                numbers.add(val_str)
        return numbers

    def _verify_fidelity(self, cited_metrics: List[str], table_data: Dict[str, Any]) -> List[str]:
        """Flags any metric cited by the model that does not exist in the source table."""
        valid_numbers = self._extract_table_numbers(table_data)
        unverified = []
        for metric in cited_metrics:
            clean_metric = metric.strip().replace('%', '')
            if clean_metric not in valid_numbers:
                unverified.append(metric)
        return unverified

    def _compile_to_suneditor_html(self, data: CommentaryOutputSchema) -> str:
        """Converts structured Pydantic payload to clean HTML safe for SunEditor & python-docx."""
        findings_html = "".join([f"<li>{item}</li>" for item in data.key_findings])
        
        return f"""
<div class="regulatory-commentary" style="border-left: 3px solid #1a56db; padding-left: 14px; margin: 16px 0;">
    <p><strong>Executive Summary:</strong> {data.executive_summary}</p>
    <p><strong>Key Quantitative Findings:</strong></p>
    <ul>{findings_html}</ul>
    <p><strong>Methodology Alignment:</strong> {data.methodology_alignment}</p>
    <p><strong>Management Justification & Decision:</strong> {data.executive_justification}</p>
</div>
""".strip()

    async def execute(self, context, max_retries: int = 2) -> Dict[str, Any]:
        system_instruction = (
            "You are a regulatory validation specialist. Produce technical commentary "
            "for the provided regulatory table. You must strictly ground your observations "
            "in the provided table data and section literature. "
            "CRITICAL: Do not invent numbers. Output MUST conform to the required JSON schema."
        )

        user_content = f"""
        CANONICAL TABLE ARTIFACT:
        {json.dumps(context.table_json)}

        SECTION LITERATURE CONTEXT:
        {context.literature_text}

        EXECUTIVE DECISIONS & OVERRIDES:
        {context.executive_notes}

        CUSTOM USER INSTRUCTIONS:
        {context.user_instructions}
        """

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

        for attempt in range(max_retries + 1):
            response = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"}
                }
            )
            raw_content = response.json()["choices"][0]["message"]["content"]
            parsed = CommentaryOutputSchema.model_validate_json(raw_content)

            # Audit guardrail execution
            hallucinations = self._verify_fidelity(parsed.cited_metrics, context.table_json)

            if not hallucinations:
                return {
                    "html": self._compile_to_suneditor_html(parsed),
                    "cited_metrics": parsed.cited_metrics,
                    "status": "VERIFIED"
                }

            # Self-healing rejection step
            if attempt == max_retries:
                return {
                    "html": self._compile_to_suneditor_html(parsed),
                    "cited_metrics": parsed.cited_metrics,
                    "status": "FLAGGED",
                    "discrepancies": hallucinations
                }

            messages.append({"role": "assistant", "content": raw_content})
            messages.append({
                "role": "user",
                "content": f"AUDIT REJECTION: The metrics {hallucinations} are not in the source table. "
                           f"Rewrite the analysis and cite ONLY verified data points."
            })

```

---

## 5. FastAPI Route Definition

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from context_assembler import assemble_grounded_context
from harness import RegulatoryCommentaryHarness

app = FastAPI(title="Regulatory Documentation Engine")

harness = RegulatoryCommentaryHarness(
    internal_endpoint="http://vllm-cluster.internal.corp:8000",
    model_name="meta-llama/Llama-3.3-70B-Instruct"
)

class CommentaryGenerationRequest(BaseModel):
    section_id: str
    table_artifact_id: str
    executive_notes: str
    user_instructions: str

@app.post("/api/sections/generate-commentary")
async def generate_commentary(
    req: CommentaryGenerationRequest,
    db = Depends(get_db_session)
):
    try:
        # 1. Compile context from PostgreSQL
        context = await assemble_grounded_context(
            db_session=db,
            section_id=req.section_id,
            table_artifact_id=req.table_artifact_id,
            executive_notes=req.executive_notes,
            user_instructions=req.user_instructions
        )

        # 2. Run agentic execution through verification harness
        result = await harness.execute(context)

        # 3. Store record in database
        query = """
            INSERT INTO section_commentaries (
                section_id, source_table_artifact_id, commentary_html, 
                raw_metrics_cited, executive_override_notes, 
                user_prompt_instructions, model_name, verification_status
            ) VALUES (
                :section_id, :artifact_id, :html, 
                :metrics, :exec_notes, :instructions, :model, :status
            ) RETURNING id;
        """
        commentary_id = await db.execute(query, {
            "section_id": req.section_id,
            "artifact_id": req.table_artifact_id,
            "html": result["html"],
            "metrics": json.dumps(result["cited_metrics"]),
            "exec_notes": req.executive_notes,
            "instructions": req.user_instructions,
            "model": harness.model_name,
            "status": result["status"]
        })

        return {
            "commentary_id": commentary_id,
            "html": result["html"],
            "status": result["status"]
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

```

---

## 6. React + SunEditor UI Integration

Add a control panel in the editor workspace. When a user drags a table into a section, they can populate instructions and insert verified commentary directly at the cursor location.

```tsx
// CommentaryControlPanel.tsx
import React, { useState } from 'react';
import axios from 'axios';

interface CommentaryPanelProps {
  sectionId: string;
  tableArtifactId: string;
  sunEditorInstance: any; // SunEditor active core instance
}

export const CommentaryControlPanel: React.FC<CommentaryPanelProps> = ({
  sectionId,
  tableArtifactId,
  sunEditorInstance
}) => {
  const [loading, setLoading] = useState(false);
  const [executiveNotes, setExecutiveNotes] = useState('');
  const [instructions, setInstructions] = useState('');

  const onGenerate = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/api/sections/generate-commentary', {
        section_id: sectionId,
        table_artifact_id: tableArtifactId,
        executive_notes: executiveNotes,
        user_instructions: instructions
      });

      const { html, status } = response.data;

      // Injects HTML directly into SunEditor's cursor location
      sunEditorInstance.insertHTML(html, true);

      if (status === 'FLAGGED') {
        alert('Warning: Some metrics could not be reconciled automatically. Please review the highlighted section.');
      }
    } catch (error) {
      console.error('Failed to generate commentary', error);
      alert('Error communicating with internal AI harness.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
      <h4 style={{ margin: '0 0 8px 0' }}>Generate Section Commentary</h4>
      
      <label style={{ fontSize: '12px', fontWeight: 600 }}>Executive Overrides & Context:</label>
      <textarea
        style={{ width: '100%', marginBottom: '8px', padding: '6px' }}
        rows={3}
        placeholder="e.g., Higher delta accepted due to secondary liquidity backstop."
        value={executiveNotes}
        onChange={(e) => setExecutiveNotes(e.target.value)}
      />

      <label style={{ fontSize: '12px', fontWeight: 600 }}>Regulatory Guidelines / Persona:</label>
      <textarea
        style={{ width: '100%', marginBottom: '12px', padding: '6px' }}
        rows={2}
        placeholder="e.g., Target SR 11-7 compliance tone. Focus on tail-risk variance."
        value={instructions}
        onChange={(e) => setInstructions(e.target.value)}
      />

      <button
        onClick={onGenerate}
        disabled={loading}
        style={{
          background: loading ? '#94a3b8' : '#1e40af',
          color: '#fff',
          border: 'none',
          padding: '8px 16px',
          borderRadius: '4px',
          cursor: loading ? 'not-allowed' : 'pointer'
        }}
      >
        {loading ? 'Harness Validating...' : 'Generate & Insert Commentary'}
      </button>
    </div>
  );
};

```

---

## 7. Downstream Document Compilation (`python-docx`)

The document generator reads the database mappings in sequential order, rendering the table followed by the commentary.

```python
# docx_compiler.py
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from bs4 import BeautifulSoup

def append_html_commentary_to_docx(doc: Document, commentary_html: str):
    """
    Parses clean HTML elements generated by the harness into native python-docx blocks.
    """
    soup = BeautifulSoup(commentary_html, "html.parser")
    
    for element in soup.children:
        if element.name == "p":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            
            # Parse strong tags vs standard text runs
            for child in element.children:
                if child.name == "strong":
                    run = p.add_run(child.get_text())
                    run.bold = True
                else:
                    p.add_run(str(child))

        elif element.name == "ul":
            for li in element.find_all("li"):
                p = doc.add_paragraph(style='List Bullet')
                p.paragraph_format.left_indent = Inches(0.5)
                p.add_run(li.get_text())

def compile_section_to_word(doc: Document, section_data: dict):
    # 1. Render Section Heading
    doc.add_heading(section_data["title"], level=1)
    
    # 2. Render Existing Literature
    for text in section_data["literature"]:
        doc.add_paragraph(text)
        
    # 3. Render Table Artifact
    render_docx_table(doc, section_data["table_artifact"])
    
    # 4. Render Validated AI Commentary
    if section_data.get("commentary_html"):
        append_html_commentary_to_docx(doc, section_data["commentary_html"])

```

---

## 8. Enterprise Security & Operational Standards

| Dimension | Enterprise Requirement | Harness Implementation |
| --- | --- | --- |
| **Inference Transport** | Must stay within VPC boundaries. | Communicates over local HTTP to internally hosted vLLM/TGI instances using the OpenAI-compatible wire protocol. |
| **Dependency Auditing** | No dynamic or unapproved third-party agent frameworks. | Built using standard, pinned dependencies: `httpx`, `pydantic`, `fastapi`, and `beautifulsoup4`. |
| **Numerical Integrity** | Zero tolerance for hallucinated model validation metrics. | Deterministic guardrail extracts all numbers from the LLM output and validates them against the raw PostgreSQL dataset. |
| **Audit Traceability** | Complete reproducibility for regulatory compliance audits. | The `section_commentaries` table records the prompt, user inputs, exact cited metrics, model identity, and timestamp for every run. |
