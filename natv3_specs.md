# Technical Specification: Behavioral Productivity Engine

## 1. System Architecture Overview

This specification defines the upgrade path for a local-first productivity daemon built on Python, React, and SQLite. The architecture prioritizes zero-latency capture, immutable auditability, and automatic contextual resurfacing without external cloud dependencies.

* **Backend Runtime:** Python 3.11+ running an asynchronous web framework with an embedded background task scheduler.
* **Storage Engine:** Local SQLite database with Write-Ahead Logging (WAL) and the FTS5 full-text search extension enabled.
* **Local Vault:** Dedicated filesystem directory storing binary attachments organized by year and month subdirectories.
* **Frontend Client:** React single-page application utilizing optimistic UI updates, global keyboard listeners, and debounced context queries.

## 2. Database Schema & DDL

Execute the following SQLite initialization statements to support prospective memory reminders, deduplicated file attachments, full-text document indexing, associative entity graphs, and deep-work telemetry.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 1. Reminders & Prospective Memory Table
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER NOT NULL,
    reminder_text TEXT NOT NULL,
    trigger_type TEXT CHECK(trigger_type IN ('TIME', 'PERSON', 'WAITING')) NOT NULL,
    trigger_at DATETIME,
    trigger_entity TEXT,
    status TEXT CHECK(status IN ('PENDING', 'INJECTED', 'COMPLETED', 'DISMISSED')) DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    injected_at DATETIME
);

CREATE INDEX idx_reminders_status_time ON reminders(status, trigger_at);
CREATE INDEX idx_reminders_entity ON reminders(status, trigger_entity);

-- 2. File Attachments Metadata Table
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    card_id INTEGER,
    sha256_hash TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    why_saved_caption TEXT NOT NULL,
    is_ephemeral INTEGER DEFAULT 0,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attachments_hash ON attachments(sha256_hash);
CREATE INDEX idx_attachments_expiry ON attachments(is_ephemeral, expires_at);

-- 3. Full-Text Search Virtual Table for Notes and Files
CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts USING fts5(
    record_type,
    record_id UNINDEXED,
    title_or_caption,
    body_content,
    entities,
    tokenize = 'porter unicode61'
);

-- 4. Associative Entity Graph (@Person, [[Project]], #decided)
CREATE TABLE IF NOT EXISTS entity_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT CHECK(entity_type IN ('PERSON', 'PROJECT', 'DECISION')) NOT NULL,
    entity_name TEXT NOT NULL,
    note_id INTEGER,
    card_id INTEGER,
    attachment_id INTEGER,
    context_snippet TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entity_lookup ON entity_links(entity_type, entity_name);

-- 5. Context Freeze & Focus Telemetry Table
CREATE TABLE IF NOT EXISTS work_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    session_type TEXT CHECK(session_type IN ('FOCUS_BLOCK', 'CONTEXT_FREEZE')) NOT NULL,
    duration_seconds INTEGER DEFAULT 0,
    next_step_note TEXT,
    active_links_json TEXT,
    is_active_freeze INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);
```

## 3. Feature Specifications

### Pillar 1: Anti-Habituation Reminders

#### Feature 1: Daily Log Injection
* **Behavioral Goal:** Eliminate notification blindness by placing due reminders directly inside the active writing stream.
* **Backend Logic:** A Python background worker polls the `reminders` table every 30 seconds for rows where `status = 'PENDING'` and `trigger_at <= CURRENT_TIMESTAMP`.
* **Injection Flow:** Matched rows trigger an insertion at the top of Today's Daily Log with a `SYSTEM_REMINDER` block type and update the reminder status to `INJECTED`.
* **Frontend UI:** React renders injected reminders as pinned amber callout bars at the top of the `/today` route with one-click Complete and Snooze buttons.

#### Feature 2: Event-Based Person & Meeting Triggers
* **Behavioral Goal:** Surface open questions at the exact moment of human interaction rather than at an arbitrary clock time.
* **Backend Logic:** Saving a note line containing `@Name ?` or `#ask @Name` inserts a `PERSON` trigger row into `reminders` with `trigger_entity = 'Name'`.
* **Frontend UI:** When the user types `@Name` in the editor, React queries `GET /api/reminders/person/{name}` and opens a non-blocking floating HUD listing pending questions.
* **Resolution Flow:** Clicking a checkbox inside the floating HUD appends the answered item into the current note and marks the reminder `COMPLETED`.

#### Feature 3: Inline Natural-Language Deferral
* **Behavioral Goal:** Keep hands on the keyboard during live meetings by parsing reminder times directly from text input.
* **Backend Logic:** The note ingestion endpoint scans text for `/in <duration>` or `@<day/time>` regex tokens and resolves them using Python datetime parsing.
* **Frontend UI:** As the user types a valid time token, the React editor highlights the token as an interactive pill showing the resolved timestamp before submission.

#### Feature 4: The Waiting-On Boomerang
* **Behavioral Goal:** Track delegated corporate dependencies without cluttering the user's primary execution board.
* **Backend Logic:** Lines or cards tagged `#waiting` create a `WAITING` reminder set for $+72$ hours and move the associated Kanban card to a hidden Waiting state.
* **Boomerang Flow:** If the item remains unresolved when `trigger_at` arrives, the daemon injects a follow-up prompt into Today's Daily Log.

### Pillar 2: Frictionless File & Media Memory

#### Feature 5: Direct Clipboard Stream
* **Behavioral Goal:** Capture screenshots, log snippets, and files in under two seconds via standard paste commands.
* **Frontend UI:** An `onPaste` listener on the React root container intercepts binary image blobs, copied spreadsheet tables, and OS file handles.
* **Backend Logic:** Python computes the SHA-256 digest of the incoming stream; if the hash exists in `attachments`, it reuses the existing stored path to prevent duplication.

#### Feature 6: Mandatory 3-Word Context Micro-Prompt
* **Behavioral Goal:** Prevent the attachment graveyard by capturing retrieval cues at the exact moment a file is saved.
* **Frontend UI:** Immediately after an `onPaste` or drag-and-drop upload, React mounts an auto-focused inline text input directly beneath the file preview.
* **Validation Rule:** Pressing `Enter` commits the caption to `why_saved_caption`; pressing `Escape` defaults the caption to the active note heading plus timestamp.

#### Feature 7: SQLite FTS5 Deep Content Indexing
* **Behavioral Goal:** Allow users to find attached corporate documents by searching for phrases contained inside the files.
* **Backend Logic:** Upon saving an attachment, Python spawns an asynchronous extraction task for PDF, DOCX, CSV, JSON, Markdown, and plain text files.
* **Indexing Flow:** Extracted text is sanitized and inserted into `search_index_fts` alongside the user's `why_saved_caption` and associated note entities.

#### Feature 8: Ephemeral Scratch Attachments
* **Behavioral Goal:** Permit heavy temporary debugging dumps without permanently bloating the local SQLite vault.
* **Frontend UI:** Holding `Shift` while pasting or toggling the hourglass icon on an attachment marks the upload as Ephemeral ($7$-day time-to-live).
* **Backend Logic:** A daily daemon cleanup job queries `attachments` where `is_ephemeral = 1` and `expires_at < CURRENT_TIMESTAMP`, unlinking the file and purging its FTS5 row.

### Pillar 3: Contextual Retrieval & Serendipity

#### Feature 9: Automatic Entity Dossiers
* **Behavioral Goal:** Mirror associative human memory by aggregating all activity around people and projects automatically.
* **Backend Logic:** On every note save, Python extracts `@Person` and `[[Project]]` tokens via regex and writes directional references into `entity_links`.
* **Frontend UI:** Clicking any entity pill opens a unified Dossier Drawer displaying open tasks, attached files, decisions, and a reverse-chronological mention timeline.

#### Feature 10: Ghost Context Sidebar
* **Behavioral Goal:** Push relevant historical knowledge to the user automatically without requiring manual search queries.
* **Frontend UI:** While typing in `/today` or editing a card, React debounces the active paragraph every $2000\text{ ms}$ and sends keywords to `/api/context/ghost`.
* **Backend Logic:** Python executes an FTS5 $\text{BM25}$ ranking query excluding today's entries and returns the top three historical notes or attachments for sidebar rendering.

```sql
SELECT record_type, record_id, title_or_caption,
       snippet(search_index_fts, 3, '<b>', '</b>', '...', 18) AS excerpt,
       bm25(search_index_fts, 10.0, 5.0, 2.0) AS rank
FROM search_index_fts
WHERE search_index_fts MATCH :sanitized_query
ORDER BY rank
LIMIT 3;
```

#### Feature 11: Corporate Decision Ledger
* **Behavioral Goal:** Create an instant audit trail explaining why architectural or business choices were made months ago.
* **Backend Logic:** Any note line containing `#decided` is indexed in `entity_links` with `entity_type = 'DECISION'` along with linked `@Person` approvers and file IDs.
* **Frontend UI:** A dedicated Decisions navigation tab displays a filterable table showing the date, decision statement, stakeholders, and supporting attachments.

### Pillar 4: Executive Function & Deep Work Protection

#### Feature 12: One-Click Context Freeze
* **Behavioral Goal:** Eliminate attention residue during urgent corporate interruptions by parking working memory externally.
* **Frontend UI:** Clicking Freeze on an active Kanban card opens a single-field modal prompting for the immediate next step and current terminal or PR link.
* **Resume Flow:** Frozen cards display a high-contrast Cyan banner at the top of the board; clicking Resume restores the saved links and clears the freeze flag.

#### Feature 13: Rich Corporate URL & Local Path Resolver
* **Behavioral Goal:** Replace noisy URLs and file paths with clean, actionable badges that bridge browser and OS workflows.
* **Frontend UI:** A custom Markdown renderer parses configured regex patterns (such as Jira keys, Git pull requests, and local paths) into compact visual pills.
* **Backend Logic:** Clicking a local path pill calls `POST /api/os/open-path`, which validates the path against an allowed directory list and invokes the OS file handler.

#### Feature 14: Micro-Timebox Heartbeat
* **Behavioral Goal:** Calibrate task estimation accuracy and automate timesheet reporting without intrusive stopwatch management.
* **Frontend UI:** Clicking Focus ($25\text{m}$) starts a Web Worker timer that updates the browser `document.title` and shows a subtle progress border around the active card.
* **Backend Logic:** Completed sessions write a `FOCUS_BLOCK` record to `work_sessions` and append an immutable entry to `audit_events`, displaying cumulative effort badges on cards.

#### Feature 15: Friday Close-Open-Loops Ritual View
* **Behavioral Goal:** Neutralize weekend anxiety caused by the Zeigarnik effect by resolving loose ends in a single batch workflow.
* **Backend Logic:** Calling `GET /api/ritual/friday` aggregates unchecked daily log todos from the past $7$ days, uncaptioned files, and stale `#waiting` items.
* **Frontend UI:** A keyboard-driven triage queue lets the user process each item with single-key shortcuts: `D` (Mark Done), `M` (Migrate to Next Week), or `K` (Kill/Archive).

## 4. Background Daemon Lifecycle

The Python daemon manages three non-blocking asynchronous background loops alongside the HTTP server:

1. **Prospective Memory Ticker ($30\text{s}$ interval):** Evaluates due `TIME` and `WAITING` reminders, writes injections to Today's Daily Log, and pushes WebSocket events to connected React clients.
2. **FTS5 & Entity Indexer (Queue-driven):** Processes uploaded binary attachments in a background thread pool so large PDF text extraction never blocks HTTP response times.
3. **Vault Garbage Collector ($6\text{h}$ interval):** Purges expired ephemeral files from disk, removes orphaned FTS5 rows, and runs `PRAGMA optimize` on the SQLite connection.

## 5. REST API Endpoint Summary

| Endpoint | Method | Purpose | Request Payload | Response Summary |
|---|---|---|---|---|
| `/api/reminders/parse` | POST | Parse inline time and entity tokens | Raw note string, note ID | Created reminder object |
| `/api/reminders/person/{name}` | GET | Fetch pending prompts for person | URL parameter name | List of open person reminders |
| `/api/attachments/stream` | POST | Upload clipboard or dropped file | Multipart file, caption, TTL flag | Attachment ID, dedupe status |
| `/api/context/ghost` | POST | Live BM25 similarity search | Active text paragraph | Top 3 historical matches |
| `/api/os/open-path` | POST | Launch local file or IDE folder | Local filesystem path string | Execution status code |

The table above outlines the core endpoints required to connect the React frontend with the local Python daemon. All endpoints bind strictly to `127.0.0.1` to guarantee local corporate security compliance.