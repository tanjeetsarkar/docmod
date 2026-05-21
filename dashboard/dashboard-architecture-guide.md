# Dashboard Application — Architecture & Design Patterns Guide

**Stack:** FastAPI · Strawberry GraphQL · PostgreSQL/BigQuery · Redis · Vite + React  
**Application:** Regional Summary → Regional Details → Deep Dive (drill-down navigation)

---

## Table of Contents

1. [Overall Architecture](#1-overall-architecture)
2. [Backend Layered Architecture](#2-backend-layered-architecture)
3. [GraphQL Schema Design — Fragment-First](#3-graphql-schema-design--fragment-first)
4. [DataLoader — Batching & N+1 Prevention](#4-dataloader--batching--n1-prevention)
5. [URL as Single Source of Truth](#5-url-as-single-source-of-truth)
6. [Apollo Client — Normalized Cache](#6-apollo-client--normalized-cache)
7. [graphql-codegen in JavaScript](#7-graphql-codegen-in-javascript)
8. [Fragment Colocation — Components Own Their Data](#8-fragment-colocation--components-own-their-data)
9. [Caching Strategy — Two Layers](#9-caching-strategy--two-layers)
10. [End-to-End Data Flow](#10-end-to-end-data-flow)

---

## 1. Overall Architecture

```
React Component
    ↓  owns fragment
Apollo Client (InMemoryCache)
    ↓  normalized cache hit/miss
GraphQL Query → FastAPI / Strawberry
    ↓  thin resolver
Service Layer  (cache orchestration)
    ↓  Redis hit? → return
Repository Layer
    ↓  DataLoader (batch)
PostgreSQL / BigQuery
```

### The Five Key Principles

| # | Principle | What It Means |
|---|-----------|---------------|
| 1 | **Fragments per component** | Components declare exactly what data they need |
| 2 | **URL = filter state** | All drill-downs are URL param changes — no component state |
| 3 | **Services own cache logic** | Resolvers never touch Redis directly |
| 4 | **DataLoader everywhere** | Resolvers never call the DB directly |
| 5 | **Codegen** | Schema is the contract; types and hooks flow automatically |

---

## 2. Backend Layered Architecture

Each layer has one responsibility and one only. This makes the codebase maintainable as the application grows.

```
GraphQL Resolvers (Strawberry)   ← thin: just wire types to services
        ↓
   Service Layer                 ← business logic + cache orchestration
        ↓
  Repository Layer               ← all DB/BigQuery queries live here
        ↓
  PostgreSQL / BigQuery / Redis
```

### Directory Structure

```
backend/
  resolvers/
    regional.py         ← thin resolvers, call services only
    models.py
    metrics.py
  services/
    regional_service.py ← cache orchestration + business logic
    model_service.py
    metric_service.py
  repositories/
    regional_repo.py    ← SQL/BigQuery queries only
    model_repo.py
    metric_repo.py
  dataloaders/
    registry.py         ← one DataLoader per loader type, per request
    model_counts.py
    model_metrics.py
    metric_history.py
  db/
    bigquery.py         ← engine, session factory
  cache/
    redis.py            ← redis client + helpers
  types/
    regional.py         ← Strawberry type definitions
    model.py
    metric.py
  context.py            ← request context wiring
  main.py
```

### Resolver — Thin Layer

```python
# resolvers/regional.py

import strawberry
from services import regional_service

@strawberry.type
class Query:

    @strawberry.field
    async def regional_summary(
        self,
        info: strawberry.types.Info,
        region: str
    ) -> RegionalSummary:
        # Resolver does nothing except delegate to the service layer
        return await regional_service.get_summary(
            region=region,
            loaders=info.context["loaders"],
            redis=info.context["redis"],
        )

    @strawberry.field
    async def regional_details(
        self,
        info: strawberry.types.Info,
        region: str,
        country: str | None = None,
        status: RAGStatus | None = None,
    ) -> RegionalDetails:
        return await regional_service.get_details(
            region=region,
            country=country,
            status=status,
            loaders=info.context["loaders"],
            redis=info.context["redis"],
        )
```

### Service Layer — Cache Orchestration + Logic

```python
# services/regional_service.py

import asyncio
import json
from repositories import regional_repo

async def get_summary(region, loaders, redis) -> RegionalSummary:
    cache_key = f"regional:summary:{region}"

    # Layer 1: Redis cache
    cached = await redis.get(cache_key)
    if cached:
        return RegionalSummary(**json.loads(cached))

    # Layer 2: Repository + DataLoader (batched BigQuery)
    countries = await regional_repo.get_countries_for_region(region)

    # All loads fire concurrently — DataLoader batches into ONE query
    count_results = await asyncio.gather(*[
        loaders.model_counts.load(c.country_id)
        for c in countries
    ])

    summary = RegionalSummary(
        region=region,
        countries=build_country_summaries(countries, count_results)
    )

    # Persist to Redis for subsequent requests
    await redis.setex(cache_key, 300, json.dumps(summary.to_dict()))
    return summary


async def get_details(region, country, status, loaders, redis) -> RegionalDetails:
    cache_key = f"regional:details:{region}:{country}:{status}"

    cached = await redis.get(cache_key)
    if cached:
        return RegionalDetails(**json.loads(cached))

    models = await regional_repo.get_models(region, country, status)

    metric_results = await asyncio.gather(*[
        loaders.model_metrics.load(m.model_id)
        for m in models
    ])

    details = RegionalDetails(models=build_model_metrics(models, metric_results))
    await redis.setex(cache_key, 180, json.dumps(details.to_dict()))
    return details
```

### Repository Layer — Pure DB Logic

```python
# repositories/regional_repo.py

from sqlalchemy import text
from db.bigquery import get_session

async def get_countries_for_region(region: str) -> list[dict]:
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT country_id, country_name, region
                FROM dim_countries
                WHERE region = :region
                ORDER BY country_name
            """),
            {"region": region}
        )
        return result.fetchall()


async def get_models(
    region: str,
    country: str | None,
    status: str | None
) -> list[dict]:
    async with get_session() as session:
        # Build query dynamically — filters are optional
        filters = ["region = :region"]
        params = {"region": region}

        if country:
            filters.append("country_id = :country")
            params["country"] = country
        if status and status != "total":
            filters.append("rag_status = :status")
            params["status"] = status

        where_clause = " AND ".join(filters)
        result = await session.execute(
            text(f"SELECT * FROM models WHERE {where_clause}"),
            params
        )
        return result.fetchall()
```

### Context — Wiring Everything Together

```python
# context.py

from fastapi import Request
from dataloaders.registry import DataLoaderRegistry

async def get_context(request: Request):
    """
    Called once per HTTP request.
    DataLoaderRegistry is fresh every time — this is intentional.
    DataLoaders must NOT be shared across requests.
    """
    return {
        "request": request,
        "loaders": DataLoaderRegistry(),           # fresh per request
        "redis":   request.app.state.redis,
        "db":      request.app.state.db,
    }


# main.py
import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import FastAPI

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema, context_getter=get_context)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")
```

---

## 3. GraphQL Schema Design — Fragment-First

Design the schema to match your UI hierarchy. Each page level has a dedicated query. Metric types are first-class so they can have their own fragments.

### Schema Definition (Strawberry)

```python
# types/regional.py

import strawberry
from enum import Enum

@strawberry.enum
class RAGStatus(Enum):
    RED   = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"

@strawberry.type
class ModelCounts:
    red:   int
    amber: int
    green: int
    total: int

@strawberry.type
class CountrySummary:
    country_id:   str
    country_name: str
    model_counts: ModelCounts

@strawberry.type
class RegionalSummary:
    region:    str
    countries: list[CountrySummary]


@strawberry.type
class MetricScore:
    value:     float
    status:    RAGStatus
    threshold: float
    run_date:  str

@strawberry.type
class ModelMetric:
    model_id:   str
    model_name: str
    country:    str
    gini:       MetricScore
    psi:        MetricScore
    # Add new metrics here — fragment in the component picks it up

@strawberry.type
class RegionalDetails:
    models: list[ModelMetric]


@strawberry.type
class MetricDataPoint:
    date:  str
    value: float

@strawberry.type
class ModelDeepDive:
    model_id:   str
    model_name: str
    metric:     str
    current:    MetricScore
    history:    list[MetricDataPoint]
    benchmarks: dict[str, float]
```

### Query Definitions — One per Page

```graphql
# Page 1: Regional Summary
query GetRegionalSummary($region: String!) {
  regionalSummary(region: $region) {
    region
    countries {
      ...CountryRowFields
    }
  }
}

# Page 2: Regional Details — filters are optional
query GetRegionalDetails(
  $region:  String!
  $country: String
  $status:  RAGStatus
) {
  regionalDetails(region: $region, country: $country, status: $status) {
    models {
      ...ModelMetricRowFields
    }
  }
}

# Page 3: Deep Dive — single model, single metric
query GetModelDeepDive($modelId: ID!, $metric: String!) {
  modelDeepDive(modelId: $modelId, metric: $metric) {
    ...DeepDivePanelFields
  }
}
```

---

## 4. DataLoader — Batching & N+1 Prevention

### The N+1 Problem

Without DataLoader, GraphQL resolves list items independently:

```
Regional Summary loads 5 countries
  → "Singapore" model_counts resolves → BigQuery query #1
  → "India"     model_counts resolves → BigQuery query #2
  → "Japan"     model_counts resolves → BigQuery query #3
  → "Thailand"  model_counts resolves → BigQuery query #4
  → "Vietnam"   model_counts resolves → BigQuery query #5
= 5 separate BigQuery queries for ONE page load
```

DataLoader collapses all 5 into **one batched query**.

### How DataLoader Uses the Event Loop

DataLoader exploits the async event loop. `.load(key)` never executes immediately — it schedules the key and returns a Promise. When the current execution tick ends, all collected keys are sent to the batch function together.

```
Tick 1: Singapore resolver → loader.load("SG") → Promise A (pending)
Tick 1: India resolver     → loader.load("IN") → Promise B (pending)
Tick 1: Japan resolver     → loader.load("JP") → Promise C (pending)
         ↓ tick ends
Tick 2: DataLoader fires batch_fn(["SG", "IN", "JP"])
         ↓ ONE BigQuery query
Tick 3: Results return → Promise A resolves → Promise B resolves → Promise C resolves
```

### Batch Function — The Core Contract

```python
# dataloaders/model_counts.py

from collections import defaultdict
from db.bigquery import get_session
from sqlalchemy import text

async def batch_model_counts_by_country(country_ids: list[str]) -> list[dict]:
    """
    RULES:
    1. Input:  list of keys (country_ids)
    2. Output: list of results in EXACTLY THE SAME ORDER as input
    3. If a key has no result, return None at that index
    These rules are enforced by strawberry.dataloader.DataLoader
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    country_id,
                    rag_status,
                    COUNT(*) as model_count
                FROM models
                WHERE country_id IN UNNEST(:country_ids)
                GROUP BY country_id, rag_status
            """),
            {"country_ids": country_ids}
        )
        rows = result.fetchall()

    # Group by country_id into dict for O(1) lookup
    grouped = defaultdict(lambda: {"red": 0, "amber": 0, "green": 0, "total": 0})
    for row in rows:
        key = row.rag_status.lower()
        grouped[row.country_id][key]      += row.model_count
        grouped[row.country_id]["total"]  += row.model_count

    # Return in SAME ORDER as input — critical
    return [grouped.get(cid) for cid in country_ids]
```

### DataLoader Registry — One Per Request

```python
# dataloaders/registry.py

from strawberry.dataloader import DataLoader
from .model_counts  import batch_model_counts_by_country
from .model_metrics import batch_model_metrics_by_id
from .metric_history import batch_metric_history_by_model

class DataLoaderRegistry:
    """
    Instantiated fresh for every HTTP request.
    NEVER share a DataLoader across requests — it maintains
    a within-request cache that would serve stale data.
    """
    def __init__(self):
        self.model_counts = DataLoader(
            load_fn=batch_model_counts_by_country,
            max_batch_size=100,   # cap: never send more than 100 keys
            cache=True            # within-request deduplication
        )
        self.model_metrics = DataLoader(
            load_fn=batch_model_metrics_by_id,
            max_batch_size=50
        )
        self.metric_history = DataLoader(
            load_fn=batch_metric_history_by_model,
            max_batch_size=50
        )
```

### Within-Request Cache — Deduplication

```python
# If two resolvers in the same request need the same key:

result_1 = await loader.load("SG")   # adds "SG" to batch → Promise A
result_2 = await loader.load("SG")   # cache=True → returns same Promise A
# batch_fn receives ["SG"] only once
# Both result_1 and result_2 resolve with identical data
```

### Using DataLoader in Resolvers

```python
# types/regional.py

@strawberry.type
class CountrySummary:
    country_id:   str
    country_name: str

    @strawberry.field
    async def model_counts(self, info: strawberry.types.Info) -> ModelCounts:
        # Resolver just calls the loader — no SQL here
        result = await info.context["loaders"].model_counts.load(self.country_id)
        return ModelCounts(**result)

    @strawberry.field
    async def gini_summary(self, info: strawberry.types.Info) -> MetricScore | None:
        return await info.context["loaders"].model_metrics.load(self.country_id)
```

### BigQuery Async Session Setup

```python
# db/bigquery.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

DATABASE_URL = (
    "bigquery://your-project/your-dataset"
    "?credentials_path=/path/to/credentials.json"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,         # BigQuery connections are expensive — keep low
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

@asynccontextmanager
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### Cache Invalidation After ETL Load

BigQuery data is batch-loaded (daily/hourly). Match your Redis TTL to your pipeline schedule, and invalidate on pipeline completion:

```python
# etl/post_load_hook.py
# Call this from your data pipeline after each BigQuery refresh

async def invalidate_after_etl_load(region: str):
    """
    Forces next request to bypass Redis and re-read from BigQuery.
    Call this at the end of every ETL job.
    """
    # Targeted invalidation for the region that was updated
    await redis.delete(f"regional:summary:{region}")

    # Wildcard invalidation for all model metrics
    async for key in redis.scan_iter("model:metrics:*"):
        await redis.delete(key)

    async for key in redis.scan_iter("regional:details:*"):
        await redis.delete(key)

    print(f"[Cache] Invalidated all keys for region={region}")
```

---

## 5. URL as Single Source of Truth

### Why URL — Not Component State

Drill-down navigation is **filter accumulation**. Using URL params instead of React state means:

- Pages are **shareable** — paste the URL and get the exact same filtered view
- **Back button works correctly** — browser history is the navigation stack
- **No prop drilling** — any component can read filters from the URL
- **No context/Redux needed** — the URL IS the global state for filters

### URL Structure

```
Page 1 — Regional Summary
/regional-summary?region=APAC

Page 2 — Regional Details (filters accumulate from Page 1 click)
/regional-details?region=APAC&country=Singapore&status=total

Page 3 — Deep Dive (filters accumulate from Page 2 click)
/deep-dive?region=APAC&country=Singapore&modelId=m123&metric=gini
```

### The useFilterState Hook

```javascript
// src/hooks/useFilterState.js

import { useSearchParams, useNavigate } from 'react-router-dom'

/**
 * Single hook used across ALL pages.
 * Reads filter state from URL params.
 * drillDown() accumulates new filters without losing existing ones.
 */
export function useFilterState() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const filters = {
    region:  searchParams.get('region')  ?? '',
    country: searchParams.get('country') ?? undefined,
    status:  searchParams.get('status')  ?? undefined,
    modelId: searchParams.get('modelId') ?? undefined,
    metric:  searchParams.get('metric')  ?? undefined,
  }

  /**
   * Called when user clicks a cell.
   * Merges new filters into existing params and navigates.
   *
   * Example:
   *   Current URL: /regional-summary?region=APAC
   *   drillDown({ country: 'Singapore', status: 'total' }, '/regional-details')
   *   Result URL:  /regional-details?region=APAC&country=Singapore&status=total
   */
  function drillDown(newFilters, targetPath) {
    const params = new URLSearchParams(searchParams)
    Object.entries(newFilters).forEach(([key, value]) => {
      if (value !== undefined) params.set(key, value)
    })
    navigate(`${targetPath}?${params.toString()}`)
  }

  /**
   * Remove a specific filter (e.g., clear country filter)
   */
  function clearFilter(filterKey) {
    const params = new URLSearchParams(searchParams)
    params.delete(filterKey)
    setSearchParams(params)
  }

  return { filters, drillDown, clearFilter }
}
```

### Using drillDown in Components

```jsx
// src/components/CountryRow/CountryRow.jsx

import { useFilterState } from '../../hooks/useFilterState'

function CountryRow({ country }) {
  const { drillDown } = useFilterState()

  function handleCellClick(status) {
    // Accumulate: keep region from URL, add country + status
    drillDown(
      { country: country.countryId, status },
      '/regional-details'
    )
  }

  return (
    <tr>
      <td>{country.countryName}</td>
      <td className="cell-red"   onClick={() => handleCellClick('red')}>
        {country.modelCounts.red}
      </td>
      <td className="cell-amber" onClick={() => handleCellClick('amber')}>
        {country.modelCounts.amber}
      </td>
      <td className="cell-green" onClick={() => handleCellClick('green')}>
        {country.modelCounts.green}
      </td>
      <td onClick={() => handleCellClick('total')}>
        {country.modelCounts.total}
      </td>
    </tr>
  )
}
```

```jsx
// src/components/ModelMetricRow/ModelMetricRow.jsx

import { useFilterState } from '../../hooks/useFilterState'

function ModelMetricRow({ model }) {
  const { drillDown } = useFilterState()

  function handleMetricClick(metric) {
    // Accumulate: keep region + country + status, add modelId + metric
    drillDown(
      { modelId: model.