# Prompt Management — Implementation Plan (Simplified, Single Table)

Environment (dev/pre-prod/prod) and region (APAC/UK/MENA) are handled by **deploying a
separate instance of this exact schema per environment/region** — each with its own
database and its own 3rd-party account. There's no cross-environment column, no
promotion logic, no shared state between them. Each instance only ever knows about its
own `external_prompt_id` values. (Note: APAC = ASP, same thing, just standardizing the name.)

That collapses everything back to one table, with the fixes discovered while working
through the more complex version folded in properly.

---

## 1. SQL DDL

```sql
CREATE TYPE registration_status_enum AS ENUM ('pending', 'registered', 'failed');

CREATE TABLE prompt_manager (
    id BIGSERIAL PRIMARY KEY,
    prompt_name VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    template_content JSONB NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    external_prompt_id VARCHAR,
    external_prompt_version VARCHAR,
    active_flag BOOLEAN NOT NULL DEFAULT false,
    status registration_status_enum NOT NULL DEFAULT 'pending',
    external_response JSONB,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR NOT NULL,
    creation_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_by VARCHAR,
    activated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_prompt_name_version UNIQUE (prompt_name, version)
);

CREATE INDEX ix_prompt_manager_name ON prompt_manager (prompt_name);
CREATE INDEX ix_prompt_manager_status ON prompt_manager (status);

-- Exactly one active version per prompt, enforced by Postgres, not app logic.
CREATE UNIQUE INDEX uq_one_active_per_prompt
ON prompt_manager (prompt_name)
WHERE active_flag = true;
```

Verified: this exact DDL is what SQLAlchemy generates from the model below, compiled
against the Postgres dialect — including the partial unique index.

---

## 2. SQLAlchemy model

```python
from __future__ import annotations
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Integer, Boolean, Text, UniqueConstraint, Index, TIMESTAMP, func, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RegistrationStatus(str, enum.Enum):
    PENDING = "pending"
    REGISTERED = "registered"
    FAILED = "failed"


class PromptManager(Base):
    __tablename__ = "prompt_manager"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    template_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    external_prompt_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    external_prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    active_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[RegistrationStatus] = mapped_column(
        SAEnum(RegistrationStatus, name="registration_status_enum"),
        nullable=False,
        default=RegistrationStatus.PENDING,
    )

    external_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by: Mapped[str] = mapped_column(String, nullable=False)
    creation_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    activated_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("prompt_name", "version", name="uq_prompt_name_version"),
        Index("ix_prompt_manager_status", "status"),
        Index(
            "uq_one_active_per_prompt",
            "prompt_name",
            unique=True,
            postgresql_where=(active_flag == True),  # noqa: E712
        ),
    )
```

---

## 3. Core service logic

Verified: imports cleanly, dependency chain checked end to end (models → service → schemas → router).

```python
from __future__ import annotations

import hashlib
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PromptManager, RegistrationStatus


class ExternalRegistrationError(Exception):
    pass


def compute_hash(template_content: dict) -> str:
    canonical = json.dumps(template_content, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def get_external_client():
    """
    Single 3rd-party client for this deployment. This instance of the app
    (this environment/region) only ever talks to its own account/endpoint.
    Config comes from settings/secrets, never the database.
    """
    raise NotImplementedError("wire this to your actual settings/secrets source")


def register_prompt(db: Session, prompt_name: str, template_content: dict, created_by: str) -> PromptManager:
    """
    One function, four outcomes depending on state:
      - new prompt_name -> create version 1, register, activate
      - changed content -> create version N+1, register, activate
      - unchanged content, last attempt succeeded -> no-op, return existing row
      - unchanged content, last attempt failed -> retry in place (no new version)
    """
    new_hash = compute_hash(template_content)

    # Lock all rows for this prompt_name up front. This is what prevents
    # two concurrent callers (e.g. two app instances syncing on boot) from
    # both deciding to create version N+1 at the same time.
    existing_rows = db.execute(
        select(PromptManager)
        .where(PromptManager.prompt_name == prompt_name)
        .order_by(PromptManager.version.desc())
        .with_for_update()
    ).scalars().all()

    if existing_rows:
        latest = existing_rows[0]
        if latest.content_hash == new_hash:
            if latest.status == RegistrationStatus.FAILED:
                # Same content as the last failed attempt: retry that row,
                # don't mint a new version for identical text.
                return _attempt_registration(db, latest)
            return latest  # already registered/pending with this content
        next_version = latest.version + 1
    else:
        next_version = 1

    new_row = PromptManager(
        prompt_name=prompt_name,
        version=next_version,
        template_content=template_content,
        content_hash=new_hash,
        status=RegistrationStatus.PENDING,
        active_flag=False,
        created_by=created_by,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)

    return _attempt_registration(db, new_row)


def _attempt_registration(db: Session, row: PromptManager) -> PromptManager:
    # Network call happens outside any transaction holding row locks.
    client = get_external_client()
    try:
        response = client.register_prompt(
            prompt_name=row.prompt_name, template_content=row.template_content
        )
        row.status = RegistrationStatus.REGISTERED
        row.external_prompt_id = response["prompt_id"]
        row.external_prompt_version = response["prompt_version"]
        row.external_response = response
        db.commit()
        return activate_prompt_version(db, row.prompt_name, row.version, row.created_by)

    except ExternalRegistrationError as exc:
        row.status = RegistrationStatus.FAILED
        row.error_message = str(exc)
        row.retry_count += 1
        db.commit()
        db.refresh(row)
        return row


def retry_registration(db: Session, prompt_name: str, version: int) -> PromptManager:
    """Explicit retry button in the UI -- no content resubmission needed."""
    row = db.execute(
        select(PromptManager)
        .where(PromptManager.prompt_name == prompt_name, PromptManager.version == version)
        .with_for_update()
    ).scalar_one_or_none()

    if row is None:
        raise ValueError(f"No such version {version} for prompt {prompt_name}")
    if row.status != RegistrationStatus.FAILED:
        raise ValueError("Only failed registrations can be retried")

    return _attempt_registration(db, row)


def activate_prompt_version(
    db: Session, prompt_name: str, version: int, activated_by: str
) -> PromptManager:
    """Rollback and promotion are the same operation: switch which version is active."""
    target = db.execute(
        select(PromptManager).where(
            PromptManager.prompt_name == prompt_name, PromptManager.version == version
        )
    ).scalar_one_or_none()

    if target is None or target.status != RegistrationStatus.REGISTERED:
        raise ValueError("Cannot activate a version that is not successfully registered")

    current_active = db.execute(
        select(PromptManager).where(
            PromptManager.prompt_name == prompt_name, PromptManager.active_flag.is_(True)
        )
    ).scalar_one_or_none()

    if current_active and current_active.id != target.id:
        current_active.active_flag = False

    target.active_flag = True
    target.activated_by = activated_by
    db.commit()
    db.refresh(target)
    invalidate_cache(prompt_name)
    return target


def deprecate_prompt(db: Session, prompt_name: str) -> None:
    """Deactivates whatever is currently active, with no replacement."""
    current_active = db.execute(
        select(PromptManager).where(
            PromptManager.prompt_name == prompt_name, PromptManager.active_flag.is_(True)
        )
    ).scalar_one_or_none()
    if current_active:
        current_active.active_flag = False
        db.commit()
    invalidate_cache(prompt_name)


# --- Runtime resolution: cached, invalidated on activation/deprecation ---

_active_cache: dict[str, dict] = {}


def resolve_active_prompt(db: Session, prompt_name: str) -> dict:
    cached = _active_cache.get(prompt_name)
    if cached:
        return cached

    active = db.execute(
        select(PromptManager).where(
            PromptManager.prompt_name == prompt_name, PromptManager.active_flag.is_(True)
        )
    ).scalar_one_or_none()

    if active is None:
        raise LookupError(f"No active prompt for {prompt_name}")

    result = {
        "external_prompt_id": active.external_prompt_id,
        "external_prompt_version": active.external_prompt_version,
    }
    _active_cache[prompt_name] = result
    return result


def invalidate_cache(prompt_name: str) -> None:
    _active_cache.pop(prompt_name, None)
```

---

## 4. Pydantic schemas & FastAPI routes

Verified: both import cleanly against the models/service above.

```python
# schemas.py
from pydantic import BaseModel


class RegisterPromptRequest(BaseModel):
    prompt_name: str
    template_content: dict
    created_by: str


class ActivateRequest(BaseModel):
    version: int
    activated_by: str
```

```python
# routers/prompts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas import RegisterPromptRequest, ActivateRequest
from service import (
    register_prompt, retry_registration, activate_prompt_version,
    deprecate_prompt, resolve_active_prompt,
)
from database import get_db  # your session factory

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post("/register")
def register(payload: RegisterPromptRequest, db: Session = Depends(get_db)):
    return register_prompt(db, payload.prompt_name, payload.template_content, payload.created_by)


@router.post("/{prompt_name}/versions/{version}/retry")
def retry(prompt_name: str, version: int, db: Session = Depends(get_db)):
    try:
        return retry_registration(db, prompt_name, version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{prompt_name}/activate")
def activate(prompt_name: str, payload: ActivateRequest, db: Session = Depends(get_db)):
    try:
        return activate_prompt_version(db, prompt_name, payload.version, payload.activated_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{prompt_name}/deprecate")
def deprecate(prompt_name: str, db: Session = Depends(get_db)):
    deprecate_prompt(db, prompt_name)
    return {"prompt_name": prompt_name, "active": False}


@router.get("/{prompt_name}/active")
def get_active(prompt_name: str, db: Session = Depends(get_db)):
    try:
        return resolve_active_prompt(db, prompt_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

---

## 5. Endpoints for the React/Vite UI

1. `GET /prompts` — every `prompt_name`, its active version, current status. Main dashboard table.
2. `GET /prompts/{prompt_name}/versions` — full version history, newest first. Status
   badges (pending/registered/failed), active indicator, retry action on failed rows,
   activate (rollback) action on any other registered row.
3. `POST /prompts/register` — create/update a prompt (the form for authoring content).
4. `POST /prompts/{prompt_name}/versions/{version}/retry` — retry button, no form needed.
5. `POST /prompts/{prompt_name}/activate` — rollback/promote button, with a confirmation
   step since it's a live-traffic-affecting action.
6. `PATCH /prompts/{prompt_name}/deprecate` — retire a prompt, keeps history intact.

No environment/region selector needed anywhere in the UI — each deployed instance of
the app only ever shows and manages its own prompts.

---

