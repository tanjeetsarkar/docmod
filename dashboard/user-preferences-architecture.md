# User Preferences — Persistence Architecture Guide

**Scope:** Column visibility · Chart axis & color choices · Cross-session, cross-device persistence  
**Stack:** FastAPI · Strawberry GraphQL · PostgreSQL · Redis · Vite React · Apollo Client

---

## Table of Contents

1. [Mental Model — Three Layers](#1-mental-model--three-layers)
2. [State Taxonomy — What Goes Where](#2-state-taxonomy--what-goes-where)
3. [Database Schema](#3-database-schema)
4. [Preference Key Design](#4-preference-key-design)
5. [Backend Implementation](#5-backend-implementation)
6. [GraphQL Schema — Queries & Mutations](#6-graphql-schema--queries--mutations)
7. [Frontend — usePreference Hook](#7-frontend--usepreference-hook)
8. [Optimistic Updates — Instant Feedback](#8-optimistic-updates--instant-feedback)
9. [Component Integration](#9-component-integration)
10. [Codegen & Fragment Integration](#10-codegen--fragment-integration)
11. [Loading Strategy — Zero Layout Shift](#11-loading-strategy--zero-layout-shift)
12. [End-to-End Flow](#12-end-to-end-flow)
13. [Quick Reference](#13-quick-reference)

---

## 1. Mental Model — Three Layers

```
Layer 1: localStorage (L1 Cache)
  ↓ instant read on mount — no network wait
  ↓ write on every preference change — optimistic

Layer 2: Redis (L2 Cache)
  ↓ read on first server request after cold cache
  ↓ write after DB mutation confirms

Layer 3: PostgreSQL (Source of Truth)
  ↓ read when Redis misses
  ↓ write on every mutation — async, does not block UI
```

### Why This Layering

| Layer | Speed | Scope | Survives |
|-------|-------|-------|----------|
| localStorage | ~0ms | This browser only | Browser cache clear? No |
| Redis | ~2ms | Server-wide | Redis restart? No (TTL) |
| PostgreSQL | ~20ms | All devices, all sessions | Forever |

**User experience:** UI applies preference change instantly (localStorage). Server sync happens in background. On next session: localStorage renders immediately, server confirms. On new device: localStorage is empty, PostgreSQL is the fallback — user gets their preferences on any device.

---

## 2. State Taxonomy — What Goes Where

This distinction is the most important architectural decision. Mixing these two categories causes bugs that are hard to debug.

```
URL Params                          User Preferences
─────────────────────────────────   ─────────────────────────────────
region=APAC                         table:regional_details:columns
country=Singapore                   chart:deep_dive:gini:config
status=total                        chart:deep_dive:psi:colors
modelId=m001
metric=gini

Changes with drill-down navigation  Changes with explicit user action
Shared via URL copy-paste           Private to the user
Lost on page close is acceptable    Must survive sessions
Drives what DATA is fetched         Drives how DATA is DISPLAYED
Stored in: React Router             Stored in: PostgreSQL + localStorage
```

```
Rule: If sharing the URL should give someone the same VIEW,
      it belongs in the URL.

      If sharing the URL should still show each person
      their own column choices, it belongs in preferences.
```

---

## 3. Database Schema

Preferences live in **PostgreSQL** (your operational DB), not BigQuery (your analytics DB). BigQuery is for bulk analytical reads. Preferences are frequent small reads and writes — a terrible fit for BigQuery.

```sql
-- migrations/create_user_preferences.sql

CREATE TABLE user_preferences (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      VARCHAR     NOT NULL,
    pref_key     VARCHAR     NOT NULL,       -- scoped key, see Section 4
    pref_value   JSONB       NOT NULL,       -- flexible structure per preference type
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One row per user per preference key
    CONSTRAINT uq_user_pref UNIQUE (user_id, pref_key)
);

-- Index for the most common query: fetch all prefs for a user
CREATE INDEX idx_user_preferences_user_id
    ON user_preferences (user_id);

-- Index for fetching specific keys for a user
CREATE INDEX idx_user_preferences_user_pref_key
    ON user_preferences (user_id, pref_key);

-- Trigger: keep updated_at current automatically
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### Why JSONB for pref_value

Each preference type has a different structure. JSONB lets you store all types in one table without a schema migration every time you add a new configurable option.

```json
// Column visibility preference — pref_value shape
{
  "visible": ["modelName", "country", "gini", "psi"],
  "hidden":  ["runDate", "threshold"],
  "order":   ["modelName", "country", "gini", "psi"]
}

// Chart configuration preference — pref_value shape
{
  "xAxis":  "runDate",
  "yAxis":  "giniValue",
  "colors": {
    "RED":   "#ef4444",
    "AMBER": "#f59e0b",
    "GREEN": "#22c55e"
  },
  "chartType": "line"
}
```

---

## 4. Preference Key Design

The key is the most important design decision. A well-designed key lets you:
- Fetch all preferences for a page in one query
- Invalidate a specific component's preference without affecting others
- Add new preference types without changing the schema

### Key Pattern

```
{scope}:{page}:{component_id}:{preference_type}

Examples:
  table:regional_details:models_table:columns
  table:regional_summary:country_table:columns
  chart:deep_dive:gini_history:config
  chart:deep_dive:psi_history:config
  chart:regional_summary:rag_distribution:colors
```

```python
# preferences/keys.py
# Define all keys as constants — never use raw strings in code

class PrefKey:
    # Tables
    REGIONAL_SUMMARY_COLUMNS  = "table:regional_summary:country_table:columns"
    REGIONAL_DETAILS_COLUMNS  = "table:regional_details:models_table:columns"

    # Charts — Deep Dive
    DEEP_DIVE_GINI_CONFIG     = "chart:deep_dive:gini_history:config"
    DEEP_DIVE_PSI_CONFIG      = "chart:deep_dive:psi_history:config"

    # Charts — Regional Summary
    SUMMARY_RAG_DIST_COLORS   = "chart:regional_summary:rag_distribution:colors"

    @staticmethod
    def chart_config(page: str, chart_id: str) -> str:
        """Dynamic key for any chart on any page."""
        return f"chart:{page}:{chart_id}:config"

    @staticmethod
    def table_columns(page: str, table_id: str) -> str:
        """Dynamic key for any table on any page."""
        return f"table:{page}:{table_id}:columns"
```

### Fetching Multiple Keys at Once

When a page mounts, fetch all its preferences in a single query using a prefix scan:

```python
# Fetch all preferences for deep_dive page in one query
keys_for_page = await repo.get_by_prefix(user_id, prefix="chart:deep_dive:")
# Returns: gini_history:config, psi_history:config, etc.
```

---

## 5. Backend Implementation

### Models (SQLAlchemy)

```python
# models/user_preference.py

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from db.base import Base

class UserPreference(Base):
    __tablename__ = "user_preferences"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String, nullable=False, index=True)
    pref_key   = Column(String, nullable=False)
    pref_value = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### Repository — Database Operations

```python
# repositories/preference_repo.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert   # for upsert
from models.user_preference import UserPreference

class PreferenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_one(self, user_id: str, key: str) -> dict | None:
        result = await self.session.execute(
            select(UserPreference)
            .where(
                UserPreference.user_id  == user_id,
                UserPreference.pref_key == key
            )
        )
        row = result.scalar_one_or_none()
        return row.pref_value if row else None

    async def get_many(self, user_id: str, keys: list[str]) -> dict[str, dict]:
        """Fetch multiple preferences in one query. Returns {key: value} map."""
        result = await self.session.execute(
            select(UserPreference)
            .where(
                UserPreference.user_id  == user_id,
                UserPreference.pref_key.in_(keys)
            )
        )
        rows = result.scalars().all()
        return {row.pref_key: row.pref_value for row in rows}

    async def get_by_prefix(self, user_id: str, prefix: str) -> dict[str, dict]:
        """Fetch all preferences matching a key prefix. Useful for page-level loading."""
        result = await self.session.execute(
            select(UserPreference)
            .where(
                UserPreference.user_id  == user_id,
                UserPreference.pref_key.like(f"{prefix}%")
            )
        )
        rows = result.scalars().all()
        return {row.pref_key: row.pref_value for row in rows}

    async def upsert(self, user_id: str, key: str, value: dict) -> dict:
        """
        Insert or update a preference.
        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE (true upsert).
        Never fails on duplicate — always applies the latest value.
        """
        stmt = (
            insert(UserPreference)
            .values(
                user_id    = user_id,
                pref_key   = key,
                pref_value = value,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "pref_key"],
                set_={
                    "pref_value": value,
                    "updated_at": func.now(),
                }
            )
            .returning(UserPreference.pref_value)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()

    async def delete_one(self, user_id: str, key: str) -> bool:
        result = await self.session.execute(
            delete(UserPreference)
            .where(
                UserPreference.user_id  == user_id,
                UserPreference.pref_key == key
            )
        )
        await self.session.commit()
        return result.rowcount > 0
```

### Service Layer — Cache Orchestration

```python
# services/preference_service.py

import json
from repositories.preference_repo import PreferenceRepository
from cache.redis import CacheClient

PREFERENCE_TTL = 3600   # 1 hour — preferences change infrequently

class PreferenceService:
    def __init__(self, repo: PreferenceRepository, redis: CacheClient):
        self.repo  = repo
        self.redis = redis

    def _cache_key(self, user_id: str, pref_key: str) -> str:
        return f"pref:{user_id}:{pref_key}"

    async def get(self, user_id: str, key: str) -> dict | None:
        # L2: Redis
        cache_key = self._cache_key(user_id, key)
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached

        # L3: PostgreSQL
        value = await self.repo.get_one(user_id, key)
        if value:
            await self.redis.set(cache_key, value, PREFERENCE_TTL)
        return value

    async def get_many(self, user_id: str, keys: list[str]) -> dict[str, dict]:
        """
        Fetch multiple preferences efficiently.
        Checks Redis for each, fetches only misses from DB in one query.
        """
        result   = {}
        db_keys  = []

        # Check Redis for all keys
        for key in keys:
            cached = await self.redis.get(self._cache_key(user_id, key))
            if cached is not None:
                result[key] = cached
            else:
                db_keys.append(key)

        # Batch-fetch all Redis misses from DB in one query
        if db_keys:
            db_result = await self.repo.get_many(user_id, db_keys)
            for key, value in db_result.items():
                result[key] = value
                # Populate Redis for next time
                await self.redis.set(
                    self._cache_key(user_id, key),
                    value,
                    PREFERENCE_TTL
                )

        return result

    async def save(self, user_id: str, key: str, value: dict) -> dict:
        # Write to DB first (source of truth)
        saved = await self.repo.upsert(user_id, key, value)

        # Invalidate Redis — next read will pull fresh from DB
        await self.redis.delete(self._cache_key(user_id, key))

        return saved

    async def reset(self, user_id: str, key: str) -> bool:
        deleted = await self.repo.delete_one(user_id, key)
        await self.redis.delete(self._cache_key(user_id, key))
        return deleted
```

---

## 6. GraphQL Schema — Queries & Mutations

```python
# types/preferences.py

import strawberry
from typing import Any

# Generic scalar for JSONB — the value varies per preference type
JSON = strawberry.scalar(
    Any,
    name="JSON",
    description="Arbitrary JSON value",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)

@strawberry.type
class UserPreference:
    key:        str
    value:      JSON
    updated_at: str

@strawberry.input
class SavePreferenceInput:
    key:   str
    value: JSON

@strawberry.input
class SavePreferencesInput:
    """Batch save — send multiple preference changes in one mutation."""
    preferences: list[SavePreferenceInput]
```

```python
# resolvers/preferences.py

import strawberry
from services.preference_service import PreferenceService

@strawberry.type
class PreferenceQuery:

    @strawberry.field
    async def user_preferences(
        self,
        info: strawberry.types.Info,
        keys: list[str],
    ) -> list[UserPreference]:
        """
        Fetch multiple preferences at once.
        Called on page mount with all keys the page needs.
        """
        user_id = info.context["user"].id    # from auth middleware
        service = PreferenceService(
            repo  = info.context["preference_repo"],
            redis = info.context["redis"],
        )
        values = await service.get_many(user_id, keys)

        return [
            UserPreference(key=k, value=v, updated_at="")
            for k, v in values.items()
        ]


@strawberry.type
class PreferenceMutation:

    @strawberry.mutation
    async def save_preference(
        self,
        info: strawberry.types.Info,
        key:  str,
        value: JSON,
    ) -> UserPreference:
        """Save a single preference. Called on every user interaction."""
        user_id = info.context["user"].id
        service = PreferenceService(
            repo  = info.context["preference_repo"],
            redis = info.context["redis"],
        )
        saved = await service.save(user_id, key, value)
        return UserPreference(key=key, value=saved, updated_at="")

    @strawberry.mutation
    async def save_preferences(
        self,
        info: strawberry.types.Info,
        input: SavePreferencesInput,
    ) -> list[UserPreference]:
        """
        Batch save — used when multiple preferences change together.
        Example: user reorders AND hides a column in one gesture.
        """
        user_id = info.context["user"].id
        service = PreferenceService(
            repo  = info.context["preference_repo"],
            redis = info.context["redis"],
        )
        results = []
        for pref in input.preferences:
            saved = await service.save(user_id, pref.key, pref.value)
            results.append(UserPreference(key=pref.key, value=saved, updated_at=""))
        return results

    @strawberry.mutation
    async def reset_preference(
        self,
        info: strawberry.types.Info,
        key: str,
    ) -> bool:
        """Reset a preference to default. Deletes the DB row."""
        user_id = info.context["user"].id
        service = PreferenceService(
            repo  = info.context["preference_repo"],
            redis = info.context["redis"],
        )
        return await service.reset(user_id, key)
```

### GraphQL Operations (Frontend .graphql files)

```graphql
# src/preferences/preferences.graphql

query GetUserPreferences($keys: [String!]!) {
  userPreferences(keys: $keys) {
    key
    value
    updatedAt
  }
}

mutation SavePreference($key: String!, $value: JSON!) {
  savePreference(key: $key, value: $value) {
    key
    value
    updatedAt
  }
}

mutation SavePreferences($input: SavePreferencesInput!) {
  savePreferences(input: $input) {
    key
    value
  }
}

mutation ResetPreference($key: String!) {
  resetPreference(key: $key)
}
```

---

## 7. Frontend — usePreference Hook

This is the single hook every component uses to read and write preferences. It abstracts the three-layer storage entirely. Components never touch localStorage or Apollo cache directly.

```javascript
// src/hooks/usePreference.js

import { useCallback, useEffect, useRef } from 'react'
import { useApolloClient, useMutation }   from '@apollo/client'
import {
  GetUserPreferencesDocument,
  SavePreferenceDocument,
} from '../generated/graphql'

const LS_PREFIX = 'dashboard:pref:'     // namespace in localStorage

/**
 * usePreference — single hook for reading and writing user preferences.
 *
 * Implements the three-layer strategy:
 *   L1: localStorage  — instant read/write, survives page refresh
 *   L2: Apollo cache  — in-memory, shared across components in same session
 *   L3: PostgreSQL    — source of truth, cross-device persistence
 *
 * @param {string}  prefKey       - The preference key (from PrefKey constants)
 * @param {any}     defaultValue  - Value if no preference is saved yet
 *
 * @returns {{ value, save, reset, loading }}
 */
export function usePreference(prefKey, defaultValue) {
  const client = useApolloClient()
  const saveTimerRef = useRef(null)

  const [saveMutation] = useMutation(SavePreferenceDocument)

  // ─── Read ────────────────────────────────────────────────────────────────

  // L1: Read from localStorage immediately (synchronous — no render needed)
  const lsKey = `${LS_PREFIX}${prefKey}`
  const readFromLocalStorage = useCallback(() => {
    try {
      const raw = localStorage.getItem(lsKey)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }, [lsKey])

  // L2: Read from Apollo cache (in-memory)
  const readFromApolloCache = useCallback(() => {
    try {
      const cached = client.readQuery({
        query: GetUserPreferencesDocument,
        variables: { keys: [prefKey] },
      })
      const pref = cached?.userPreferences?.find(p => p.key === prefKey)
      return pref?.value ?? null
    } catch {
      return null
    }
  }, [client, prefKey])

  // Resolved value: L1 → L2 → default
  // localStorage is the fastest — use it as the primary source
  const localValue = readFromLocalStorage()
  const cacheValue = readFromApolloCache()
  const value      = localValue ?? cacheValue ?? defaultValue

  // ─── Write ───────────────────────────────────────────────────────────────

  const save = useCallback((newValue) => {
    // L1: Write to localStorage immediately — instant UI update
    try {
      localStorage.setItem(lsKey, JSON.stringify(newValue))
    } catch {
      // localStorage might be full or disabled — not fatal
      console.warn(`[Preferences] localStorage write failed for ${prefKey}`)
    }

    // L2: Write to Apollo cache — other components in same session update too