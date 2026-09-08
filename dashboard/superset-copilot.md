# Engineering Proposal: AI-Native Analytical Copilot & Dynamic Visualization Engine for Apache Superset

## 1. Executive Summary

This proposal outlines the technical architecture, data flow, and implementation plan for transforming **Apache Superset** into an autonomous, natural-language-driven Business Intelligence platform.

Instead of building and maintaining a decoupled external frontend, this design embeds capabilities directly inside Superset using the **Superset Extension Framework (`.supx`)**, the **Superset MCP (Model Context Protocol) Service**, and **Celery Async Task Queues**.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        APACHE SUPERSET WORKSPACE                           │
│                                                                            │
│  ┌───────────────────────┐   ┌──────────────────────────────────────────┐  │
│  │ DOCKED COPILOT PANEL  │   │        ACTIVE DASHBOARD / EXPLORE        │  │
│  │ (chat.registerChat)   │   │                                          │  │
│  │ - Natural Query Input │   │  ┌────────────────────┐ ┌─────────────┐  │  │
│  │ - Context Commentary  │───┼─►│ Auto-Generated     │ │ Custom Viz  │  │  │
│  │ - Follow-up Actions   │   │  │ Slice (Chart)      │ │ Plugins     │  │  │
│  └───────────┬───────────┘   │  └────────────────────┘ └─────────────┘  │  │
│              │               └──────────────────────────────────────────┘  │
└──────────────┼─────────────────────────────────────────────────────────────┘
               │ JSON-RPC / SSE
               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                  SUPERSET MCP SERVICE & AGENT RUNTIME                      │
│  - Session propagation: FAB RBAC Context & g.user tenant metadata          │
│  - Deterministic Tool Suite: semantic_match, traverse_graph, create_slice  │
└──────────────┬──────────────────────────────┬──────────────────────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐ ┌───────────────────────────────────────────┐
│     SEMANTIC STORE LAYER     │ │        DATA PROCESSING & EXECUTION        │
│ ┌──────────────────────────┐ │ │                                           │
│ │ Graph DB (Neo4j)         │ │ │  ┌─────────────────────────────────────┐  │
│ │ - Relational topologies  │ │ │  │ Native Analytical Engine            │  │
│ │ - Entity-to-table lineage│ │ │  │ (Trino / ClickHouse / DuckDB)       │  │
│ └──────────────────────────┘ │ │  └──────────────────▲──────────────────┘  │
│ ┌──────────────────────────┐ │ │                     │ Direct SQL Pushdown │
│ │ Vector DB (Qdrant)       │ │ │  ┌──────────────────┴──────────────────┐  │
│ │ - Column token embeddings│ │ │  │ Celery Asynchronous Workers         │  │
│ │ - Certified metric specs │ │ │  │ - Background dataset profiling      │  │
│ └──────────────────────────┘ │ │  │ - Statistical sketch computation    │  │
└──────────────────────────────┘ │  └─────────────────────────────────────┘  │
                                 └───────────────────────────────────────────┘

```

---

## 2. Core System Architecture

### 2.1 The Host Integration Principle

The platform utilizes pre-existing datasets registered within Superset (`SqlaTable`, `TableColumn`, and `SqlMetric`). Superset already manages analytical database connectivity, dialect compilation, access controls, and connection pooling.

The architecture adds three core capabilities around this baseline:

1. **Asynchronous Semantic Extraction**: A Celery worker pipeline introspects datasets, calculates low-overhead data profiles, and loads structural topologies into a Graph DB and semantic embeddings into a Vector DB.
2. **Context-Aware Semantic Agent**: An agent orchestration engine exposed via the Model Context Protocol (MCP) coordinates fuzzy intent resolution and graph-based relational traversal.
3. **Automated Provisioning via Command Bus**: The system generates first-class charts (`Slice` models) programmatically using Superset internal commands, executing queries with full Row-Level Security (RLS) enforcement.

---

## 3. Information Architecture & Dual-Store Semantic Modeling

Natural language queries often lack the precision required for direct SQL generation. Colloquial requests like *"How did my model perform last quarter?"* present multiple ambiguities:

* Target model identity ($M_{\text{target}}$)
* Definition of "performance" (AUC, Gini, or Default Rate)
* Correct analytical table and time-grain join keys

To eliminate hallucination, semantic disambiguation is divided into two distinct responsibilities:

```
                  USER QUERY: "How did my model perform last quarter?"
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
     ┌─────────────────────────────┐               ┌─────────────────────────────┐
     │    VECTOR STORE (Qdrant)    │               │      GRAPH DB (Neo4j)       │
     │   Fuzzy Semantic Search     │               │   Deterministic Lineage     │
     ├─────────────────────────────┤               ├─────────────────────────────┤
     │ "model"   ──► col: model_id │               │ Dataset(42)                 │
     │ "perform" ──► metric:       │               │   ├──[:HAS_METRIC]──► Metric│
     │               default_rate  │               │   └──[:GRAIN]───────► MOB   │
     └──────────────┬──────────────┘               └──────────────┬──────────────┘
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           ▼
                       UNAMBIGUOUS RESOLUTION CONTEXT
                       - Target Dataset ID: 42
                       - Primary Metric: "cumulative_default_rate"
                       - Filtering Slice: model_id = 'credit_risk_v2'
                       - Time Window: 2025-10-01 to 2025-12-31

```

### 3.1 Vector Database Schema (Qdrant)

Embeddings capture descriptions of registered metrics, column names, column labels, and sampled distinct categorical values.

```json
{
  "id": "8f1a4e52-19c2-488f-9a72-7634f1e5a012",
  "vector": [0.0124, -0.0431, 0.0892, "..."],
  "payload": {
    "dataset_id": 42,
    "target_type": "entity_value",
    "column_name": "model_id",
    "token_value": "credit_risk_v2",
    "display_alias": "Credit Risk XGBoost Prime",
    "description": "Production underwriting model for prime consumer loans"
  }
}

```

### 3.2 Graph Database Topology (Neo4j)

The Graph tracks entity-to-table relationships, dataset join paths, temporal grain expectations, and metric dependencies.

```cypher
(:Dataset {id: 42, table_name: "fact_vintage_performance", schema: "risk_analytics"})
  -[:HAS_TIME_COL]->(:TimeDimension {name: "origination_month", default_grain: "P1M"})
  -[:HAS_METRIC]->(:Metric {name: "cumulative_default_rate", sql: "SUM(bad_loans)/SUM(total_loans)"})
  -[:HAS_DIMENSION]->(:Dimension {name: "mob", label: "Months On Book"})
  -[:CONTAINS_ENTITY {type: "ML_MODEL"}]->(:EntityInstance {id: "credit_risk_v2", name: "Credit Risk XGBoost Prime"})

```

---

## 4. Asynchronous Profiling & Indexing Pipeline

Indexing runs asynchronously via Celery workers to keep metadata sync operations isolated from user-facing transactions.

```
┌──────────────────────────────────────┐
│       SUPERSET DATASET VIEW          │
│   (User / Admin clicks Sync Hook)    │
└──────────────────┬───────────────────┘
                   │ POST /api/v1/dataset/{id}/sync_knowledge_base
                   ▼
┌──────────────────────────────────────┐
│       SUPERSET FLASK APP             │
│   - Validates `can_write on Dataset` │
│   - Emits task to Celery Broker      │
└──────────────────┬───────────────────┘
                   │ tasks.index_superset_dataset.delay(dataset_id)
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CELERY ASYNC WORKER                             │
│                                                                        │
│  1. Load SqlaTable definitions (SqlMetric, TableColumn)                │
│  2. Compute SQL pushdown profiling (distinct sketches, boundary spans) │
│  3. Upsert structural lineage into Neo4j                               │
│  4. Generate and upsert dense vector embeddings into Qdrant            │
└────────────────────────────────────────────────────────────────────────┘

```

### 4.1 Indexing Implementation (`tasks/semantic_indexer.py`)

```python
import logging
from celery import shared_task
from sqlalchemy import text
from superset.extensions import db
from superset.connectors.sqla.models import SqlaTable
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from neo4j import GraphDatabase
import openai

logger = logging.getLogger(__name__)

qdrant = QdrantClient(url="http://qdrant:6333")
neo4j_driver = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "platform_token"))

def generate_embedding(content: str) -> list[float]:
    response = openai.embeddings.create(input=content, model="text-embedding-3-small")
    return response.data[0].embedding

@shared_task(name="tasks.index_superset_dataset", bind=True, max_retries=3)
def index_superset_dataset_task(self, dataset_id: int) -> dict:
    dataset = db.session.query(SqlaTable).filter_by(id=dataset_id).one_or_none()
    if not dataset:
        logger.error(f"Dataset {dataset_id} does not exist.")
        return {"status": "failed", "reason": "dataset_not_found"}

    points: list[PointStruct] = []
    engine = dataset.database.get_sqla_engine()

    with neo4j_driver.session() as session:
        # 1. Upsert Root Dataset Node
        session.run(
            """
            MERGE (d:Dataset {id: $id})
            SET d.name = $name, d.table_name = $table_name, d.schema = $schema
            """,
            id=dataset.id,
            name=dataset.table_name,
            table_name=dataset.table_name,
            schema=dataset.schema or ""
        )

        # 2. Extract Certified Metrics
        for metric in dataset.metrics:
            session.run(
                """
                MATCH (d:Dataset {id: $ds_id})
                MERGE (m:Metric {name: $name, dataset_id: $ds_id})
                SET m.expression = $expr, m.description = $desc
                MERGE (d)-[:HAS_METRIC]->(m)
                """,
                ds_id=dataset.id,
                name=metric.metric_name,
                expr=metric.expression,
                desc=metric.description or ""
            )

            metric_text = (
                f"Metric: {metric.metric_name}. "
                f"Description: {metric.description or 'No description'}. "
                f"Formula: {metric.expression}"
            )
            points.append(PointStruct(
                id=abs(hash(f"metric_{dataset.id}_{metric.metric_name}")) % (2**63),
                vector=generate_embedding(metric_text),
                payload={"dataset_id": dataset.id, "type": "metric", "name": metric.metric_name}
            ))

        # 3. Sample Categorical Entities (Pushdown profiling)
        for col in dataset.columns:
            if not col.is_dttm and col.type in ["VARCHAR", "STRING", "TEXT"]:
                sample_query = f"""
                    SELECT {col.column_name} AS val, COUNT(*) AS freq
                    FROM {dataset.table_name}
                    WHERE {col.column_name} IS NOT NULL
                    GROUP BY {col.column_name}
                    ORDER BY freq DESC
                    LIMIT 20
                """
                try:
                    with engine.connect() as conn:
                        rows = conn.execute(text(sample_query)).fetchall()
                        for row in rows:
                            val_str = str(row[0])
                            session.run(
                                """
                                MATCH (d:Dataset {id: $ds_id})
                                MERGE (c:Column {name: $col_name, dataset_id: $ds_id})
                                MERGE (e:EntityValue {value: $val})
                                MERGE (d)-[:HAS_COLUMN]->(c)
                                MERGE (c)-[:HAS_VALUE]->(e)
                                """,
                                ds_id=dataset.id,
                                col_name=col.column_name,
                                val=val_str
                            )

                            vector_text = f"Entity '{val_str}' in column '{col.column_name}' of table '{dataset.table_name}'"
                            points.append(PointStruct(
                                id=abs(hash(f"val_{dataset.id}_{col.column_name}_{val_str}")) % (2**63),
                                vector=generate_embedding(vector_text),
                                payload={
                                    "dataset_id": dataset.id,
                                    "type": "dimension_value",
                                    "column": col.column_name,
                                    "value": val_str
                                }
                            ))
                except Exception as ex:
                    logger.warning(f"Profiling failed for column {col.column_name}: {ex}")

    if points:
        qdrant.upsert(collection_name="superset_semantics", points=points)

    return {"status": "success", "indexed_nodes": len(points)}

```

---

## 5. Natural Language Query Resolution & Slice Generation

When an analytical question enters the copilot panel, it executes across a four-stage resolution lifecycle:

```
[User Prompts Copilot] ──► "How did my model perform last quarter?"
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: SEMANTIC RESOLUTION                                           │
│ 1. Vector Search: Extract entity references & map colloquial terms     │
│ 2. Context Extraction: Bind authenticated tenant (`g.user`)            │
│ 3. Temporal Resolution: Compile relative dates into absolute boundaries│
└───────────────────────────────────────┬────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: GRAPH REASONING & INTENT VALIDATION                           │
│ 1. Traverse lineage: Map model reference to dataset and grain keys     │
│ 2. Identify required visualization archetype (e.g., vintage curve)    │
└───────────────────────────────────────┬────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: PROGRAMMATIC SLICE CREATION                                   │
│ 1. Construct typed Chart `params` JSON payload                         │
│ 2. Execute `CreateChartCommand` inside Superset Command Bus            │
│ 3. Execute `ChartDataCommand` to extract aggregated tabular matrix     │
└───────────────────────────────────────┬────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: SYNTHESIS & REAL-TIME CLIENT HYDRATION                        │
│ 1. Pass aggregated data matrix to LLM for analytical narrative         │
│ 2. Stream commentary tokens and slice metadata via Server-Sent Events  │
└────────────────────────────────────────────────────────────────────────┘

```

### 5.1 Dynamic Chart Generation Logic (`services/agent_analytics.py`)

```python
import json
from typing import Dict, Any
from superset.extensions import db
from superset.commands.chart.create import CreateChartCommand
from superset.charts.data.commands.get_data_command import ChartDataCommand
from superset.common.chart_data import ChartDataResultFormat, ChartDataResultType
import openai

def execute_nlq_to_slice(user_prompt: str, resolution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates validated resolution parameters into an indexed Superset Slice,
    executes the underlying dataset query, and appends analytical commentary.
    """
    dataset_id = resolution["dataset_id"]
    viz_type = resolution.get("viz_type", "table")
    metric_name = resolution["metric_name"]
    entity_filter = resolution["filter_expression"]
    time_grain = resolution["time_range"]

    form_data = {
        "datasource": f"{dataset_id}__table",
        "viz_type": viz_type,
        "metrics": [metric_name],
        "time_range": time_grain,
        "adhoc_filters": [
            {
                "expressionType": "SQL",
                "clause": "WHERE",
                "sqlExpression": entity_filter
            }
        ]
    }

    # 1. Create Chart Slice via the Superset Command Bus
    chart_payload = {
        "slice_name": f"Auto Analysis: {metric_name} ({time_grain})",
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": viz_type,
        "params": json.dumps(form_data),
    }

    create_command = CreateChartCommand(chart_payload)
    new_slice = create_command.run()

    # 2. Fetch Aggregated Metrics Matrix to power the commentary
    query_context = new_slice.get_query_context()
    data_command = ChartDataCommand(query_context)
    query_payload = data_command.run(
        result_type=ChartDataResultType.FULL, 
        result_format=ChartDataResultFormat.JSON
    )
    aggregated_records = query_payload["queries"][0]["data"]

    # 3. Generate Analytical Commentary
    analysis_prompt = f"""
    User Query: "{user_prompt}"
    Evaluated Metric: {metric_name}
    Temporal Window: {time_grain}
    Tabular Result Matrix (first 25 rows):
    {json.dumps(aggregated_records[:25])}

    Provide a concise three-sentence executive commentary:
    1. Direct metric outcome compared to preceding trends.
    2. Primary drivers or seasoning variations across dimensions.
    3. Noteworthy risks, deviations, or confirmations.
    """

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": analysis_prompt}],
        max_tokens=220,
        temperature=0.2
    )
    narrative = completion.choices[0].message.content

    return {
        "slice_id": new_slice.id,
        "slice_name": new_slice.slice_name,
        "explore_url": f"/explore/?slice_id={new_slice.id}",
        "commentary": narrative
    }

```

---

## 6. Native Superset Frontend Extension (`.supx`)

The user interface uses Superset's Extension Framework to register a docked copilot panel in Explore and Dashboard layouts via `chat.registerChat`.

```tsx
// frontend/src/index.tsx
import React, { useState } from 'react';
import { chat } from '@apache-superset/core';
import { Button, Input, Card, Typography, Spin, Space } from 'antd';

const { Text, Paragraph } = Typography;

interface AssistantMessage {
  sender: 'user' | 'assistant';
  content: string;
  sliceId?: number;
  exploreUrl?: string;
}

const CopilotTrigger: React.FC = () => (
  <Button type="primary" shape="circle" style={{ fontWeight: 'bold' }}>
    AI
  </Button>
);

const CopilotPanel: React.FC = () => {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const submitPrompt = async () => {
    if (!inputPrompt.trim()) return;

    const userText = inputPrompt;
    setInputPrompt('');
    setMessages(prev => [...prev, { sender: 'user', content: userText }]);
    setIsProcessing(true);

    try {
      const response = await fetch('/extensions/platform/v1/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (window as any).bootstrapData?.csrf_token,
        },
        body: JSON.stringify({ prompt: userText }),
      });

      const responsePayload = await response.json();

      setMessages(prev => [
        ...prev,
        {
          sender: 'assistant',
          content: responsePayload.commentary,
          sliceId: responsePayload.slice_id,
          exploreUrl: responsePayload.explore_url,
        },
      ]);

      // If a chart was provisioned, dispatch a refresh event for the active dashboard
      if (responsePayload.slice_id) {
        window.dispatchEvent(
          new CustomEvent('superset:slice_created', {
            detail: { sliceId: responsePayload.slice_id },
          })
        );
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { sender: 'assistant', content: 'Execution error while resolving query.' },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '16px' }}>
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: '16px' }}>
        {messages.map((item, idx) => (
          <div
            key={idx}
            style={{
              marginBottom: '12px',
              textAlign: item.sender === 'user' ? 'right' : 'left',
            }}
          >
            <Card
              size="small"
              style={{
                display: 'inline-block',
                maxWidth: '85%',
                background: item.sender === 'user' ? '#1890ff' : '#f5f5f5',
                color: item.sender === 'user' ? '#ffffff' : '#000000',
                borderRadius: '8px',
              }}
            >
              <Paragraph style={{ margin: 0, color: 'inherit' }}>
                {item.content}
              </Paragraph>

              {item.sliceId && (
                <div style={{ marginTop: '8px' }}>
                  <Button
                    size="small"
                    type="default"
                    href={item.exploreUrl}
                    target="_blank"
                  >
                    Open Generated Slice #{item.sliceId}
                  </Button>
                </div>
              )}
            </Card>
          </div>
        ))}
        {isProcessing && <Spin tip="Analyzing lineage & calculating slices..." />}
      </div>

      <Space.Compact style={{ width: '100%' }}>
        <Input
          placeholder="Ask an analytical question..."
          value={inputPrompt}
          onChange={e => setInputPrompt(e.target.value)}
          onPressEnter={submitPrompt}
          disabled={isProcessing}
        />
        <Button type="primary" onClick={submitPrompt} loading={isProcessing}>
          Run
        </Button>
      </Space.Compact>
    </div>
  );
};

// Register the extension into native Superset chat namespace
chat.registerChat(
  { id: 'platform.copilot.core', name: 'Analytical Co-Pilot' },
  CopilotTrigger,
  CopilotPanel
);

```

---

## 7. Security, Multi-Tenancy & Governance Architecture

```
                      [ User Web Client / Copilot UI ]
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ Flask-AppBuilder Security   │
                      │ Extracts session context:   │
                      │ - Identity: g.user.id       │
                      │ - Tenant: tenant_id         │
                      └──────────────┬──────────────┘
                                     │
            ┌────────────────────────┴────────────────────────┐
            ▼                                                 ▼
┌─────────────────────────────────────┐     ┌───────────────────────────────────┐
│ MCP Agent Tool Boundary             │     │ Native Explore / Slice Engine     │
│ - Validates permissions for user    │     │ - Validates `datasource_access`   │
│ - Restricts target dataset scope    │     │ - Parses SQLAlchemy AST           │
└──────────────────┬──────────────────┘     └─────────────────┬─────────────────┘
                   │                                          │
                   └──────────────────┬───────────────────────┘
                                      ▼
                      ┌─────────────────────────────┐
                      │ Dynamic RLS Injection Engine│
                      │ Compiles Jinja SQL Clauses: │
                      │ WHERE tenant_id = '...'     │
                      └──────────────┬──────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ Analytical Query Engine     │
                      │ (Runs with least privilege) │
                      └─────────────────────────────┘

```

The system preserves complete multi-tenant isolation by evaluating all access against Superset's security model:

* **Session Identity Propagation**: The docked extension UI does not use independent API tokens. Requests include the active Flask-AppBuilder session cookie alongside standard `X-CSRFToken` headers. The backend agent runs tool calls under the authenticated user (`g.user`).
* **Deterministic Row-Level Security (RLS)**: Generated charts are not raw, arbitrary SQL queries. They compile through `SqlaTable.get_sqla_query()`, which evaluates all dynamic Jinja RLS templates:
```sql
WHERE tenant_id = '{{ current_user_metadata("tenant_id") }}'
  AND model_id IN (
    SELECT model_id FROM permitted_models WHERE user_id = {{ current_user_id() }}
  )

```


* **No Direct DB Access for the LLM**: The LLM agent cannot issue arbitrary `SELECT`, `UPDATE`, or `DROP` statements. It can only emit structured parameters (dataset ID, metric names, dimension filters) against certified Superset catalog objects.

---

## 8. Deployment & Service Topology

```yaml
# docker-compose.analytical-platform.yml
services:
  superset-web:
    image: apache/superset:6.0.0
    environment:
      - SUPERSET_FEATURE_DYNAMIC_PLUGINS=True
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    volumes:
      - ./dist/extensions:/app/superset/extensions
    ports:
      - "8088:8088"
    depends_on:
      - redis
      - postgres
      - qdrant
      - neo4j

  superset-worker:
    image: apache/superset:6.0.0
    command: ["celery", "-A", "superset.tasks.celery_app:app", "worker", "-Q", "default,semantic_indexing", "-l", "INFO"]
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
      - postgres

  superset-mcp:
    image: apache/superset:6.0.0
    command: ["superset", "mcp", "run", "--host", "0.0.0.0", "--port", "5008"]
    environment:
      - MCP_AUTH_ENABLED=True
    depends_on:
      - superset-web

  neo4j:
    image: neo4j:5.20-enterprise
    environment:
      - NEO4J_AUTH=neo4j/platform_token
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - ./data/neo4j:/data
    ports:
      - "7687:7687"

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - ./data/qdrant:/qdrant/storage
    ports:
      - "6333:6333"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=superset
      - POSTGRES_USER=superset
      - POSTGRES_PASSWORD=superset
    volumes:
      - ./data/postgres:/var/lib/postgresql/data

```

---

## 9. Implementation Roadmap & Milestones

The delivery schedule is organized into four sequential engineering phases over twelve weeks:

| Phase | Milestone Name | Key Engineering Deliverables | Validation Criteria |
| --- | --- | --- | --- |
| **1** | **Infrastructure & Semantic Store Setup** | Deploy Neo4j and Qdrant clusters; configure shared network topology; create database indices. | Read/write latency $< 15\text{ms}$ on vector k-NN; graph relational integrity checks pass. |
| **2** | **Celery Profiling Engine** | Implement pushdown sampling algorithms; hook into SQLAlchemy lifecycle events on `SqlaTable`; build indexer worker tasks. | Indexing runs across 500 catalog tables with zero memory degradation or connection pool exhaustion. |
| **3** | **MCP Agent & Chart Provisioning** | Implement `execute_nlq_to_slice`; expose Superset native `CreateChartCommand` to MCP endpoints; build multi-modal commentary generator. | Generated slices pass full Jinja RLS evaluation across distinct user tenant roles. |
| **4** | **Extension UI & Copilot Integration** | Develop docked Copilot React bundle using `@apache-superset/core`; register panel via `chat.registerChat`; package `.supx`. | Seamless interaction within Superset Explore & Dashboard interfaces with no UI performance regressions. |
