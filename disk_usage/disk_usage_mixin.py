"""
disk_usage_mixin.py

Production-hardened mixin that adds a *non-column* "disk usage" attribute
to any SQLAlchemy model, computed from file paths stored either directly
in columns or nested inside JSON/JSONB columns.

Design:
    - Path locations are declared explicitly per-model via __path_fields__.
    - Usage is computed lazily via an async method (Redis + disk I/O).
    - Result is cached in Redis, keyed by table + primary key + a version
      suffix (updated_at/version column if present) so a slow, in-flight
      write can never overwrite a fresher value with stale data.
    - Cache is proactively invalidated on update/delete via SQLAlchemy
      Session events, registered once at startup.
    - Redis failures degrade to direct computation rather than breaking
      the request.

Setup:
    1. Add DiskUsageMixin to your declarative models.
    2. Declare __path_fields__ per model (see example at bottom).
    3. Call register_disk_usage_cache_invalidation(sync_redis_client) once
       at app startup.
    4. Single row:  size = await instance.get_disk_usage(async_redis)
       List of rows: sizes = await get_disk_usage_bulk(rows, async_redis)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional, Union

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

logger = logging.getLogger("disk_usage_mixin")

# Change per-environment if multiple apps/envs share one Redis instance.
CACHE_NAMESPACE = "app"


# ---------------------------------------------------------------------------
# 1. Declaring where paths live, per model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnPath:
    """A column that directly stores a path string, e.g. file_path = Column(String)."""
    column: str


@dataclass(frozen=True)
class JSONPath:
    """
    A path nested inside a JSON/JSONB column.

    key_path uses dot notation; append `[]` to a segment to iterate a list.
    Examples:
        "thumbnail.path"            -> blob["thumbnail"]["path"]
        "attachments[].path"        -> blob["attachments"][*]["path"]
        "versions[].files[].path"   -> nested lists, arbitrary depth
    """
    column: str
    key_path: str


PathSpec = Union[ColumnPath, JSONPath]


# ---------------------------------------------------------------------------
# 2. Resolving raw path strings out of a row
# ---------------------------------------------------------------------------

def _walk_json_path(data: Any, segments: list[str]) -> list[str]:
    if data is None:
        return []
    if not segments:
        return [data] if isinstance(data, str) else []

    seg, *rest = segments
    is_list_seg = seg.endswith("[]")
    key = seg[:-2] if is_list_seg else seg

    if not isinstance(data, dict):
        return []
    value = data.get(key)

    if is_list_seg:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            out.extend(_walk_json_path(item, rest))
        return out

    return _walk_json_path(value, rest)


def resolve_json_paths(json_blob: Optional[dict], key_path: str) -> list[str]:
    if not json_blob:
        return []
    return _walk_json_path(json_blob, key_path.split("."))


def _collect_raw_paths(instance: "DiskUsageMixin") -> list[str]:
    paths: list[str] = []
    for spec in getattr(instance, "__path_fields__", []):
        if isinstance(spec, ColumnPath):
            value = getattr(instance, spec.column, None)
            if value:
                paths.append(value)
        elif isinstance(spec, JSONPath):
            blob = getattr(instance, spec.column, None)
            paths.extend(resolve_json_paths(blob, spec.key_path))
    return paths


# ---------------------------------------------------------------------------
# 3. Computing bytes on disk (blocking - always runs in threadpool)
# ---------------------------------------------------------------------------

def _resolve_full_path(p: str, base_dir: Optional[str]) -> Optional[str]:
    """Joins relative paths onto base_dir and guards against traversal
    escaping that base dir. Absolute paths are trusted as-is (this mixin
    has no way to know if they were already sandboxed upstream)."""
    full_path = p if os.path.isabs(p) else os.path.join(base_dir or "", p)
    full_path = os.path.realpath(full_path)

    if base_dir:
        base_real = os.path.realpath(base_dir)
        if os.path.commonpath([full_path, base_real]) != base_real:
            logger.warning("disk_usage: path %r resolves outside base_dir, skipping", p)
            return None

    return full_path


def _path_size(full_path: str) -> int:
    try:
        if os.path.isdir(full_path):
            total = 0
            # followlinks=False (default) avoids symlink loops
            for root, _dirs, files in os.walk(full_path, followlinks=False):
                for f in files:
                    try:
                        total += os.stat(os.path.join(root, f)).st_size
                    except OSError:
                        continue
            return total
        return os.stat(full_path).st_size
    except OSError:
        return 0


def _compute_disk_usage_sync(paths: list[str], base_dir: Optional[str]) -> int:
    total = 0
    for p in paths:
        full_path = _resolve_full_path(p, base_dir)
        if full_path is None:
            continue
        total += _path_size(full_path)
    return total


# ---------------------------------------------------------------------------
# 4. Cache key (version-aware) + mixin
# ---------------------------------------------------------------------------

def _cache_version_suffix(instance: Any) -> str:
    """Folding updated_at/version into the key means a slow, in-flight
    write can never clobber a fresher value: it writes under the OLD
    version's key, which nothing will ever read again."""
    for attr in ("updated_at", "modified_at", "version"):
        value = getattr(instance, attr, None)
        if value is not None:
            return str(value)
    return "nv"  # no version column available on this model


def _cache_key(instance: "DiskUsageMixin") -> str:
    pk = inspect(instance).identity
    pk_str = "_".join(str(p) for p in pk) if pk else "transient"
    version = _cache_version_suffix(instance)
    return f"{CACHE_NAMESPACE}:disk_usage:{instance.__tablename__}:{pk_str}:{version}"


class DiskUsageMixin:
    """Mix into any declarative model to add a computed, Redis-cached
    disk_usage attribute. Not a mapped column - no schema/migration needed."""

    __path_fields__: list[PathSpec] = []
    __storage_base_dir__: Optional[str] = None  # set per-model if paths are relative

    async def get_disk_usage(self, redis, ttl: int = 86400) -> int:
        """Bytes on disk used by this row's files. Cached in Redis until
        the row changes or ttl expires. Falls back to direct computation
        if Redis is unavailable."""
        key = _cache_key(self)

        try:
            cached = await redis.get(key)
            if cached is not None:
                return int(cached)
        except Exception:
            logger.warning("disk_usage cache read failed for %s", key, exc_info=True)

        paths = _collect_raw_paths(self)
        size = await run_in_threadpool(_compute_disk_usage_sync, paths, self.__storage_base_dir__)

        try:
            await redis.set(key, size, ex=ttl)
        except Exception:
            logger.warning("disk_usage cache write failed for %s", key, exc_info=True)

        return size


async def get_disk_usage_bulk(
    instances: list["DiskUsageMixin"],
    redis,
    ttl: int = 86400,
    max_concurrency: int = 10,
) -> list[int]:
    """Efficient disk usage lookup for a list of rows (e.g. a list endpoint).
    One MGET for cache reads, concurrent (capped) computation for misses,
    one pipelined write-back. Returns sizes in the same order as `instances`."""
    if not instances:
        return []

    keys = [_cache_key(obj) for obj in instances]

    try:
        cached_values = await redis.mget(keys)
    except Exception:
        logger.warning("disk_usage bulk cache read failed, computing all rows directly", exc_info=True)
        cached_values = [None] * len(instances)

    results: list[Optional[int]] = [int(v) if v is not None else None for v in cached_values]
    miss_indices = [i for i, v in enumerate(results) if v is None]

    if miss_indices:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _compute(i: int):
            async with semaphore:
                obj = instances[i]
                paths = _collect_raw_paths(obj)
                size = await run_in_threadpool(_compute_disk_usage_sync, paths, obj.__storage_base_dir__)
                return i, size

        computed = await asyncio.gather(*(_compute(i) for i in miss_indices))

        try:
            async with redis.pipeline(transaction=False) as pipe:
                for i, size in computed:
                    pipe.set(keys[i], size, ex=ttl)
                await pipe.execute()
        except Exception:
            logger.warning("disk_usage bulk cache write failed", exc_info=True)

        for i, size in computed:
            results[i] = size

    return results  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# 5. Cache invalidation on update/delete
#
# NOTE: these are SQLAlchemy *sync* Session events - they work correctly
# with AsyncSession too, since it runs a sync Session underneath. The
# redis client here must be a *sync* client (redis.Redis, not
# redis.asyncio.Redis), since Session events have no event loop to await
# on. This proactive delete is a courtesy cleanup on top of the version-
# aware cache key above, which is what actually guarantees correctness
# for models that have an updated_at/version column. For models without
# one, this event is the only staleness protection, so keep it registered.
#
# For bulk data migrations, prefer Core-level bulk statements over looping
# session.commit() - ORM commits fire this per-row and will hit Redis once
# per row.
# ---------------------------------------------------------------------------

def register_disk_usage_cache_invalidation(sync_redis_client) -> None:
    """Call once at app startup."""

    @event.listens_for(Session, "before_flush")
    def _capture_dirty(session, flush_context, instances):
        keys = session.info.setdefault("_disk_usage_invalidate", set())
        for obj in session.dirty:
            if isinstance(obj, DiskUsageMixin) and session.is_modified(obj):
                keys.add(_cache_key(obj))
        for obj in session.deleted:
            if isinstance(obj, DiskUsageMixin):
                keys.add(_cache_key(obj))

    @event.listens_for(Session, "after_commit")
    def _invalidate(session):
        keys = session.info.pop("_disk_usage_invalidate", None)
        if keys:
            try:
                sync_redis_client.delete(*keys)
            except Exception:
                logger.warning("disk_usage cache invalidation failed", exc_info=True)


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------
#
# class Document(Base, DiskUsageMixin):
#     __tablename__ = "documents"
#
#     id = Column(Integer, primary_key=True)
#     file_path = Column(String)
#     metadata_json = Column(JSONB)
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#
#     __path_fields__ = [
#         ColumnPath("file_path"),
#         JSONPath("metadata_json", "thumbnail.path"),
#         JSONPath("metadata_json", "attachments[].path"),
#     ]
#
# # at startup:
# register_disk_usage_cache_invalidation(sync_redis_client)
#
# # single row:
# @router.get("/documents/{doc_id}")
# async def get_document(doc_id: int, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
#     doc = await db.get(Document, doc_id)
#     size = await doc.get_disk_usage(redis)
#     return {"id": doc.id, "disk_usage_bytes": size}
#
# # list of rows:
# @router.get("/documents")
# async def list_documents(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
#     docs = (await db.execute(select(Document))).scalars().all()
#     sizes = await get_disk_usage_bulk(docs, redis)
#     return [{"id": d.id, "disk_usage_bytes": s} for d, s in zip(docs, sizes)]
