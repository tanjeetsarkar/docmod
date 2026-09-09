Starting with PostgreSQL as the unified semantic, relational, and vector store simplifies the infrastructure: Superset already requires PostgreSQL for its application metadata, so enabling pgvector and an adjacency-list schema eliminates two stateful distributed databases (Neo4j and Qdrant) without changing the core query resolution flow.
Phase Progression Matrix
| Capability | Phase 1: Consolidated Postgres (MVP) | Phase 2: Hybrid Decoupling | Phase 3: Enterprise Scale |
|---|---|---|---|
| Semantic Vectors | PostgreSQL + pgvector (HNSW Index) | Dedicated Qdrant instance (if vector count > 2M) | Qdrant Cluster / Distributed HNSW |
| Lineage & Graph | PostgreSQL Relational Schema + Recursive CTEs | Dedicated Graph DB (Neo4j) if hop depth > 4 | Neo4j Enterprise + Graph Data Science |
| Profiling Engine | Celery + In-database SQL Pushdown | Celery + Ray / DuckDB Worker Pool | Distributed Spark / DuckDB Engine |
| Visualization UX | Docked Superset Copilot Extension (.supx) | Embedded Dynamic Chart Injector | Multi-tenant Autonomous Canvas |
| New Infrastructure | Zero (re-uses existing Postgres + Redis) | Adds Neo4j + Qdrant | Full distributed cluster |
Phase 1 Architecture: Consolidated PostgreSQL Semantic Layer
In Phase 1, PostgreSQL stores Superset's metadata, vector embeddings, and relational graph topology in a dedicated schema (semantic_store).
┌────────────────────────────────────────────────────────────────────────┐
│                        APACHE SUPERSET WORKSPACE                       │
│  ┌───────────────────────┐   ┌──────────────────────────────────────┐  │
│  │ DOCKED COPILOT PANEL  │   │      DASHBOARD & EXPLORE VIEWS       │  │
│  │ (chat.registerChat)   │───┼─► Slices generated via               │  │
│  │ Natural Language Q&A  │   │   native CreateChartCommand          │  │
│  └───────────┬───────────┘   └──────────────────────────────────────┘  │
└──────────────┼─────────────────────────────────────────────────────────┘
               │ JSON-RPC / SSE
               ▼
┌────────────────────────────────────────────────────────────────────────┐
│              SUPERSET MCP SERVICE & AGENT ORCHESTRATOR                 │
│  - Runs within Superset worker context with current FAB user (g.user)  │
│  - Single DB session: queries both Superset core and `semantic_store`  │
└──────────────┬──────────────────────────────┬──────────────────────────┘
               │ SQLAlchemy Session           │ Celery Profiling Tasks
               ▼                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   POSTGRESQL INSTANCE (Unified Store)                  │
│                                                                        │
│  ┌─────────────────────────────────┐ ┌──────────────────────────────┐  │
│  │ Core Superset Tables            │ │ Celery Broker / Result Store │  │
│  │ (dbs, slices, tables, columns)  │ │ (or separate Redis instance) │  │
│  └─────────────────────────────────┘ └──────────────────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Schema: `semantic_store`                                         │  │
│  │                                                                  │  │
│  │ 1. `semantic_nodes`: Metrics, Dimensions, Model Entities         │  │
│  │ 2. `semantic_edges`: Relational lineage & entity joins           │  │
│  │ 3. `semantic_embeddings`: `pgvector` column with HNSW index      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘

1. Unified Postgres DDL (schema: semantic_store)
Run the following migration inside the existing Superset PostgreSQL database:
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS semantic_store;

-- 1. Structural Nodes (Entities, Certified Metrics, Dimensions)
CREATE TABLE semantic_store.nodes (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES public.tables(id) ON DELETE CASCADE,
    node_type VARCHAR(32) NOT NULL, -- 'metric', 'dimension', 'model_entity', 'time_grain'
    node_key VARCHAR(128) NOT NULL, -- e.g., 'cumulative_default_rate', 'model_id'
    display_name VARCHAR(255),
    expression TEXT,                -- SQL formula (e.g. SUM(bad)/SUM(total))
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (dataset_id, node_type, node_key)
);

-- 2. Topological Graph Edges (Lineage & Joins via Adjacency List)
CREATE TABLE semantic_store.edges (
    id SERIAL PRIMARY KEY,
    source_node_id INT NOT NULL REFERENCES semantic_store.nodes(id) ON DELETE CASCADE,
    target_node_id INT NOT NULL REFERENCES semantic_store.nodes(id) ON DELETE CASCADE,
    relationship_type VARCHAR(64) NOT NULL, -- 'HAS_METRIC', 'GRAIN_OF', 'PERTAINS_TO_MODEL'
    properties JSONB DEFAULT '{}'::jsonb,
    UNIQUE (source_node_id, target_node_id, relationship_type)
);

-- 3. Vector Embeddings (Fuzzy Matching Engine)
CREATE TABLE semantic_store.embeddings (
    id SERIAL PRIMARY KEY,
    node_id INT NOT NULL REFERENCES semantic_store.nodes(id) ON DELETE CASCADE,
    dataset_id INT NOT NULL,
    chunk_type VARCHAR(32) NOT NULL, -- 'metric_description', 'dimension_sample', 'col_alias'
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL, -- text-embedding-3-small dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for sub-millisecond cosine vector lookup
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw 
ON semantic_store.embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_nodes_lookup ON semantic_store.nodes (dataset_id, node_type);
CREATE INDEX idx_edges_lookup ON semantic_store.edges (source_node_id, relationship_type);

2. Phase 1 Celery Indexing Task (Pushdown to Postgres)
The Celery worker reads Superset's metadata, samples categorical values via light SQL pushdown, and writes both embeddings and topology into PostgreSQL in a single database transaction.
# superset/tasks/semantic_indexer_pg.py
import logging
from celery import shared_task
from sqlalchemy import text
from superset.extensions import db
from superset.connectors.sqla.models import SqlaTable
import openai

logger = logging.getLogger(__name__)

def get_embedding(payload_text: str) -> list[float]:
    response = openai.embeddings.create(
        input=payload_text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

@shared_task(name="tasks.index_superset_dataset_pg", bind=True, max_retries=3)
def index_superset_dataset_pg(self, dataset_id: int):
    dataset = db.session.query(SqlaTable).filter_by(id=dataset_id).one_or_none()
    if not dataset:
        return {"status": "error", "message": f"Dataset {dataset_id} not found"}

    engine = dataset.database.get_sqla_engine()

    try:
        # 1. Upsert Certified Metrics as Nodes + Embeddings
        for metric in dataset.metrics:
            metric_node_id = db.session.execute(
                text("""
                    INSERT INTO semantic_store.nodes 
                        (dataset_id, node_type, node_key, display_name, expression, description)
                    VALUES 
                        (:ds_id, 'metric', :key, :name, :expr, :desc)
                    ON CONFLICT (dataset_id, node_type, node_key) 
                    DO UPDATE SET expression = EXCLUDED.expression, description = EXCLUDED.description
                    RETURNING id;
                """),
                {
                    "ds_id": dataset.id,
                    "key": metric.metric_name,
                    "name": metric.verbose_name or metric.metric_name,
                    "expr": metric.expression,
                    "desc": metric.description or ""
                }
            ).scalar()

            # Embed metric definition
            metric_text = f"Metric: {metric.metric_name}. Details: {metric.description}. Formula: {metric.expression}"
            embedding_vec = get_embedding(metric_text)

            db.session.execute(
                text("""
                    INSERT INTO semantic_store.embeddings 
                        (node_id, dataset_id, chunk_type, content, embedding)
                    VALUES 
                        (:node_id, :ds_id, 'metric_description', :content, :vec);
                """),
                {
                    "node_id": metric_node_id,
                    "ds_id": dataset.id,
                    "content": metric_text,
                    "vec": str(embedding_vec)
                }
            )

        # 2. Sample Dimension Values (Pushdown aggregation)
        for col in dataset.columns:
            col_node_id = db.session.execute(
                text("""
                    INSERT INTO semantic_store.nodes 
                        (dataset_id, node_type, node_key, display_name, metadata)
                    VALUES 
                        (:ds_id, 'dimension', :key, :name, :meta)
                    ON CONFLICT (dataset_id, node_type, node_key) 
                    DO UPDATE SET metadata = EXCLUDED.metadata
                    RETURNING id;
                """),
                {
                    "ds_id": dataset.id,
                    "key": col.column_name,
                    "name": col.verbose_name or col.column_name,
                    "meta": f'{{"is_date": {str(col.is_dttm).lower()}}}'
                }
            ).scalar()

            # Sample categorical tokens if text column
            if not col.is_dttm and col.type in ["VARCHAR", "STRING", "TEXT"]:
                sample_sql = f"""
                    SELECT {col.column_name} AS val 
                    FROM {dataset.table_name} 
                    WHERE {col.column_name} IS NOT NULL 
                    GROUP BY {col.column_name} 
                    ORDER BY count(*) DESC 
                    LIMIT 20
                """
                with engine.connect() as conn:
                    sample_rows = conn.execute(text(sample_sql)).fetchall()

                for row in sample_rows:
                    val_str = str(row[0])
                    val_text = f"Entity '{val_str}' in column '{col.column_name}' of dataset '{dataset.table_name}'"
                    val_vec = get_embedding(val_text)

                    db.session.execute(
                        text("""
                            INSERT INTO semantic_store.embeddings 
                                (node_id, dataset_id, chunk_type, content, embedding)
                            VALUES 
                                (:node_id, :ds_id, 'dimension_sample', :content, :vec);
                        """),
                        {
                            "node_id": col_node_id,
                            "ds_id": dataset.id,
                            "content": val_text,
                            "vec": str(val_vec)
                        }
                    )

        db.session.commit()
        return {"status": "success", "dataset_id": dataset.id}

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to index dataset {dataset_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)

3. Query Resolution via Single-Engine SQL
When a user asks: "How did my model perform last quarter?", the agent executes a hybrid vector-similarity and lineage query in PostgreSQL in one round-trip.
                  USER PROMPT: "How did my model perform last quarter?"
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID POSTGRESQL RESOLUTION QUERY                              │
│                                                                                    │
│ 1. Compute embedding of prompt vector: $query_vec                                  │
│ 2. Find nearest semantic match in `semantic_store.embeddings`                      │
│ 3. Join with `semantic_store.nodes` to retrieve dataset_id and formulas            │
│ 4. Traverse `semantic_store.edges` (CTE) to find dimensions, time grains, filters  │
└──────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ DETERMINISTIC CONTEXT RETURNED TO AGENT                                            │
│ - Target Dataset: `fact_vintage_performance` (id: 42)                              │
│ - Target Metric: `cumulative_default_rate`                                         │
│ - Target Filter: `model_id = 'credit_risk_v2'`                                     │
│ - Temporal Range: `origination_month >= '2025-10-01'`                              │
└────────────────────────────────────────────────────────────────────────────────────┘

SQL Implementation (Replaces both Qdrant API + Neo4j Cypher)
WITH vector_matches AS (
    -- Vector Match: Identify closest metric and dimension values
    SELECT 
        e.dataset_id,
        e.node_id,
        n.node_type,
        n.node_key,
        n.expression,
        (e.embedding <=> :query_vec::vector) AS distance
    FROM semantic_store.embeddings e
    JOIN semantic_store.nodes n ON e.node_id = n.id
    ORDER BY distance ASC
    LIMIT 5
),
lineage_traversal AS (
    -- Relational Lineage: Find related grains or join relationships
    SELECT 
        vm.dataset_id,
        vm.node_key AS primary_metric,
        vm.expression AS metric_expression,
        target_n.node_key AS associated_dimension,
        target_n.node_type AS dimension_type
    FROM vector_matches vm
    LEFT JOIN semantic_store.edges ed ON vm.node_id = ed.source_node_id
    LEFT JOIN semantic_store.nodes target_n ON ed.target_node_id = target_n.id
    WHERE vm.node_type = 'metric'
    LIMIT 1
)
SELECT * FROM lineage_traversal;

4. Phase 1 Docker Compose Footprint
The infrastructure matches the standard Superset footprint without introducing external stateful containers.
# docker-compose.phase1.yml
services:
  superset-web:
    image: apache/superset:6.0.0
    environment:
      - SUPERSET_FEATURE_DYNAMIC_PLUGINS=True
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://superset:superset@postgres:5432/superset
    volumes:
      - ./extensions:/app/superset/extensions
    ports:
      - "8088:8088"
    depends_on:
      - postgres
      - redis

  superset-worker:
    image: apache/superset:6.0.0
    command: ["celery", "-A", "superset.tasks.celery_app:app", "worker", "-Q", "default,semantic_indexing", "-l", "INFO"]
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://superset:superset@postgres:5432/superset
    depends_on:
      - postgres
      - redis

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=superset
      - POSTGRES_USER=superset
      - POSTGRES_PASSWORD=superset
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

5. Architectural Transition Strategy (Phase 1 \rightarrow Phase 2)
By encapsulating access behind Python repository classes, upgrading to dedicated databases later requires changing only the store implementations:
┌─────────────────────────────────────────────────────────────┐
│                 SemanticRepository (Interface)              │
│  - find_nearest_metric(query_vec, limit)                    │
│  - get_dataset_lineage(dataset_id)                          │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
    [Phase 1 Implementation]        [Phase 2 Implementation]
               │                               │
               ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│ PostgresSemanticRepository  │ │ HybridSemanticRepository    │
│ - Runs pgvector SQL         │ │ - Vectors: QdrantClient     │
│ - Runs Postgres CTEs        │ │ - Lineage: Neo4j GraphDriver│
└─────────────────────────────┘ └─────────────────────────────┘

Metrics Triggering Phase 2 Migration
 * Migrate to Qdrant: When embeddings exceed 2,000,000 vectors or embedding query latency exceeds 60ms during peak analytical loads.
 * Migrate to Neo4j: When cross-dataset join paths require graph traversals deeper than 4 hops (e.g., full enterprise data-mesh column-level provenance).
For initial deployment across hundreds of registered datasets, the single-PostgreSQL design avoids distributed sync overhead while providing identical NLQ-to-slice functionality.
