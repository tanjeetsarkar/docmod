# DocPipeline — SSE-Based LLM Documentation System

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  shared/contracts.py  ←  single source of truth for ALL data shapes         │
└──────────────────────────────────────────┬──────────────────────────────────┘
                                           │ imported by both apps
          ┌────────────────────────────────┴───────────────────────────────────────┐
          ▼                                                                        ▼
┌─────────────────────────────┐    POST /pipeline/start            ┌──────────────────────────────────────────┐
│   APP A  :8000              │ ──────────────────────────────────►│   APP B  :8001                           │
│   Documentation App         │                                    │   LLM Pipeline Gateway                    │
│                             │    GET /pipeline/{job_id}/stream   │                                          │
│  POST /analyze              │ ◄──────────────────────────────────│   PipelineEngine                         │
│  GET  /stream/{job_id}      │       (SSE relay)                  │     ↓                                    │
│  GET  /jobs/{job_id}        │                                    │   Node₁ (CommentaryNode)                 │
│  GET  /presets              │                                    │     ↓  output fed into Node₂             │
│                             │                                    │   Node₂ (ValidationNode)                 │
│  ┌─── per user ───────────┐ │                                    │     ↓                                    │
│  │ asyncio.Queue          │ │                                    │   Node₃ (SummaryNode)   ← optional       │
│  │ (isolated per job_id)  │ │                                    │     ↓                                    │
│  └────────────────────────┘ │                                    │   NodeN  ← extend freely                 │
│           ↓                 │                                    │                                          │
│  GET /stream/{job_id}       │                                    │   NodeRegistry                           │
│  (browser SSE connection)   │                                    │   (NodeType → class mapping)             │
└─────────────────────────────┘                                    └──────────────────────────────────────────┘
```

## Event Flow

```
User (browser)              App A                      App B                    Anthropic API
     │                        │                          │                           │
     │ POST /analyze          │                          │                           │
     │───────────────────────►│                          │                           │
     │ {job_id, stream_url}   │                          │                           │
     │◄───────────────────────│                          │                           │
     │                        │ POST /pipeline/start     │                           │
     │                        │─────────────────────────►│                           │
     │                        │ {job_id: accepted}       │                           │
     │                        │◄─────────────────────────│                           │
     │ GET /stream/{job_id}   │                          │                           │
     │───────────────────────►│                          │                           │
     │                        │ GET /pipeline/{id}/stream│                           │
     │                        │─────────────────────────►│                           │
     │                        │                          │ streaming POST (claude)   │
     │                        │                          │──────────────────────────►│
     │ event: pipeline.started│◄─── relay ───────────────│◄── token ── token ──...  │
     │ event: node.started    │                          │                           │
     │ event: node.token ×N   │                          │ node₁ done → node₂ starts│
     │ event: node.completed  │                          │──────────────────────────►│
     │ event: node.started    │◄─── relay ───────────────│◄── token ── token ──...  │
     │ event: node.token ×N   │                          │                           │
     │ event: node.completed  │                          │                           │
     │ event: pipeline.done   │◄─────────────────────────│                           │
```

## Project Layout

```
docpipeline/
├── shared/
│   └── contracts.py          ← ALL Pydantic models. Both apps import from here only.
│
├── app_a/
│   └── main.py               ← Documentation App (port 8000). Multi-user SSE relay.
│
├── app_b/
│   ├── main.py               ← LLM Gateway (port 8001). Pipeline API.
│   └── pipeline/
│       ├── engine.py         ← PipelineEngine: runs nodes in sequence.
│       ├── registry.py       ← NodeRegistry: maps NodeType → class.
│       └── nodes/
│           ├── base.py       ← BaseNode ABC. All nodes inherit this.
│           └── builtin.py    ← CommentaryNode, ValidationNode, SummaryNode, CritiqueNode
│
├── requirements.txt
└── README.md
```

## Quickstart

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Start App B (LLM Gateway) — terminal 1
uvicorn app_b.main:app --port 8001 --reload

# 4. Start App A (Documentation App) — terminal 2
uvicorn app_a.main:app --port 8000 --reload

# 5. Open the test UI
open http://localhost:8000
```

## Stage 1: Commentary → App A → App B → LLM → SSE back

POST to App A:
```json
{
  "user_id": "user-001",
  "preset":  "commentary_only",
  "document": {
    "title": "Q1 2026 Sales",
    "tables": [
      {
        "title": "Revenue by Region",
        "columns": ["Region", "Q1 Revenue (₹ Cr)", "Growth"],
        "rows": [["North", 56.8, "+34%"], ["West", 49.1, "-4.5%"]]
      }
    ]
  }
}
```

Subscribe to stream:
```javascript
const es = new EventSource('/stream/' + job_id);
es.addEventListener('node.token', e => {
  const { payload } = JSON.parse(e.data);
  process.stdout.write(payload.token);   // live LLM output
});
es.addEventListener('pipeline.completed', () => es.close());
```

## Stage 2: Add Validation (just change the preset)

```json
{ "preset": "default" }   // commentary → validation (2 LLM calls, chained)
```

The validation node automatically receives the commentary as `{{ previous_outputs }}`.

## Adding a New Pipeline Node

### Step 1 — Add the type to the enum (shared/contracts.py)
```python
class NodeType(str, Enum):
    COMMENTARY  = "commentary"
    VALIDATION  = "validation"
    TRANSLATION = "translation"   # ← new
```

### Step 2 — Create the node class (app_b/pipeline/nodes/builtin.py)
```python
class TranslationNode(BaseNode):
    @property
    def default_system_prompt(self) -> str:
        return "You are a professional technical translator. Translate the analysis to the target language."
```

### Step 3 — Register it (app_b/pipeline/registry.py)
```python
registry.register(NodeType.TRANSLATION, TranslationNode)
```

### Step 4 — Use it in a pipeline config sent from App A
```python
NodeConfig(
    node_id="translate_to_hindi",
    node_type=NodeType.TRANSLATION,
    prompt_template=(
        "Translate the following to Hindi:\n\n{{ previous_outputs }}"
    ),
    params={"target_language": "Hindi"},
)
```

**That's it. No other changes needed.**

## Multi-User Design

Each call to `POST /analyze` creates an isolated `asyncio.Queue` keyed by `job_id`.
The relay background task fills that queue; the user's SSE connection drains it.
Users never share queues — concurrent users are fully isolated.

```
User 1 → job-abc → Queue-abc → /stream/job-abc
User 2 → job-def → Queue-def → /stream/job-def   (independent)
User 3 → job-ghi → Queue-ghi → /stream/job-ghi   (independent)
```

## Available Presets (App A)

| Preset                | Nodes                                    |
|-----------------------|------------------------------------------|
| `commentary_only`     | commentary_1                             |
| `default`             | commentary_1 → validation_1              |
| `full_with_summary`   | commentary_1 → validation_1 → summary_1  |
| custom                | pass your own `pipeline_config` object   |

## Event Reference

| Event Type              | Payload fields                                              |
|-------------------------|-------------------------------------------------------------|
| `pipeline.started`      | pipeline_id, node_count, node_ids, user_id                  |
| `node.started`          | node_type, model                                            |
| `node.token`            | token (string)                                              |
| `node.completed`        | result: {node_id, node_type, output_text, duration_ms, ...} |
| `pipeline.completed`    | result, total_duration_ms, nodes_completed, error           |
| `pipeline.error`        | error (string), node_id (if applicable)                     |
