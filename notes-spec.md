# Product & Technical Specification: Local Behavioral Notes & Kanban Daemon (v2.0)

## 1. Executive Summary & Product Vision
### 1.1 Problem Statement
Traditional Kanban boards (Trello-style) fail for personal daily productivity because they impose high cognitive and interaction friction. Recording a fleeting thought requires selecting a board, choosing a lane, creating a card, and managing board clutter. Consequently, users revert to physical pen and paper for zero-latency capture, losing digital searchability and historical auditability.

### 1.2 Core Objective
Transform the existing local **Python + React + SQLite** Kanban daemon from a static "card management board" into a **behavior-driven, chronological work ledger**. The system will match the speed of physical paper via an interstitial daily log while automatically maintaining a Kanban workflow and an immutable audit trail tailored for corporate rituals (daily standups, context switching, and performance reviews).

### 1.3 Target Environment Constraints (Corporate Compliance)
* **100% Local & Air-Gapped:** Runs strictly on `localhost` via the background Python daemon and local SQLite database file. Zero external cloud dependencies, ensuring compliance with strict corporate IT and data-loss prevention (DLP) policies.
* **Sub-Second Capture Latency:** From intent to recorded thought must take under $2\text{ seconds}$.

---

## 2. Behavioral Pillars & Core Workflows

1. **Capture First, Structure Later:** The default landing screen is no longer the Kanban board; it is **Today's Interstitial Stream** (`/today`). Users type timestamped lines throughout the day without deciding where a note belongs.
2. **Inline Action Promotion:** Syntax triggers inside the daily stream (e.g., `TODO:`, `[]`, `#blocker`) automatically spawn or update Kanban cards in the background.
3. **Zero-Effort Auditability:** Every state change, card movement, note entry, and task completion is recorded in an append-only SQLite audit ledger via database triggers.
4. **High-Reward Corporate Retrieval:** One-click views synthesize raw logs and card movements into ready-to-read **Daily Standup updates** and **Quarterly Brag Documents**.

---

## 3. System Architecture

* **Backend Daemon:** Python (FastAPI or Flask) serving REST APIs + background scheduler thread (for nightly board hygiene) + optional OS hotkey listener (`pynput` / local localhost popup).
* **Database:** SQLite3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) enabled for fast concurrent local reads/writes and automated triggers for audit logging.
* **Frontend:** React.js Single Page Application (SPA) prioritizing keyboard-first navigation, instant input focus, and Markdown rendering.

---

## 4. Database Schema Specification (SQLite)

### 4.1 New & Updated Tables

```sql
-- 1. Daily Interstitial Logs Table (Primary Capture Stream)
CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date TEXT NOT NULL,                  -- Format: YYYY-MM-DD
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    content TEXT NOT NULL,                   -- Raw markdown/text entry
    entry_type TEXT DEFAULT 'note',          -- 'note', 'todo', 'win', 'blocker', 'parked_state'
    linked_card_id INTEGER NULL,             -- FK to cards.id if promoted or referenced
    tags TEXT DEFAULT '[]',                  -- JSON array of extracted #tags
    FOREIGN KEY (linked_card_id) REFERENCES cards(id) ON DELETE SET NULL
);

-- 2. Enhanced Kanban Cards Table (Upgrading Existing Table)
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    lane TEXT NOT NULL DEFAULT 'todo',       -- 'backlog', 'todo', 'doing', 'blocked', 'done'
    priority INTEGER DEFAULT 0,
    project_tag TEXT NULL,                   -- e.g., '#auth-service', '#q3-migration'
    source_log_id INTEGER NULL,              -- Traceability back to the thought that spawned it
    is_archived INTEGER DEFAULT 0,           -- Boolean (0 or 1) for nightly hygiene
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL
);

-- 3. Immutable Audit Ledger Table (The Core Memory Engine)
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_date TEXT NOT NULL,                -- Format: YYYY-MM-DD for fast indexing
    entity_type TEXT NOT NULL,               -- 'card' or 'log'
    entity_id INTEGER NOT NULL,
    event_action TEXT NOT NULL,              -- 'CREATED', 'MOVED_LANE', 'UPDATED', 'COMPLETED', 'ARCHIVED', 'LOGGED'
    old_value TEXT NULL,                     -- e.g., old lane name
    new_value TEXT NULL,                     -- e.g., new lane name
    context_snapshot TEXT NOT NULL           -- Human-readable title/summary at the time of event
);

CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_events(event_date);
CREATE INDEX IF NOT EXISTS idx_logs_date ON daily_logs(log_date);
CREATE INDEX IF NOT EXISTS idx_cards_lane_archived ON cards(lane, is_archived);
```

### 4.2 Automated SQLite Triggers for Zero-Miss Auditing
By placing audit logic inside SQLite triggers, even manual SQL edits or script updates are guaranteed to be tracked.

```sql
-- Trigger: Log every card lane movement automatically
CREATE TRIGGER IF NOT EXISTS trg_card_lane_move
AFTER UPDATE OF lane ON cards
WHEN OLD.lane != NEW.lane
BEGIN
    INSERT INTO audit_events (
        event_date, entity_type, entity_id, event_action, old_value, new_value, context_snapshot
    ) VALUES (
        DATE('now', 'localtime'),
        'card',
        NEW.id,
        CASE WHEN NEW.lane = 'done' THEN 'COMPLETED' ELSE 'MOVED_LANE' END,
        OLD.lane,
        NEW.lane,
        NEW.title
    );

    UPDATE cards 
    SET last_activity_at = CURRENT_TIMESTAMP,
        completed_at = CASE WHEN NEW.lane = 'done' THEN CURRENT_TIMESTAMP ELSE completed_at END
    WHERE id = NEW.id;
END;
```

---

## 5. Functional Feature Specifications

### Feature 1: The "Today" Interstitial Stream (`/today`)
* **User Story:** As a user in the middle of a corporate workday, I want the app to open with the cursor already focused in a single input box so I can type a thought and hit `Enter` in under $2\text{ seconds}$.
* **Behavior:**
  * Displays a chronological feed of today's entries (`10:15 AM — Joined architecture sync, decided to deprecate v1 endpoint`).
  * Supports **Context-Switch Parking**: Starting an entry with `PARK:` or clicking "Park Brain" highlights the entry at the top of the screen in a yellow banner (`"Currently parked: Debugging line 412 of auth.py before jumping into 2 PM call"`). Dismissing it logs when work resumed.
  * Displays an **"Active Focus" mini-widget** at the top right showing only the cards currently in the `doing` lane (maximum 3 cards recommended).

### Feature 2: Inline Action Promotion Engine (Backend Parser)
* **User Story:** I want to write notes naturally without switching to the Kanban board to create tasks.
* **Parsing Rules (Executed in Python on `POST /api/logs`):**
  * **Task Creation:** If an entry starts with `TODO:`, `[]`, or `TASK:`, the backend strips the prefix, creates a new record in `cards` (in the `todo` lane), and links `daily_logs.linked_card_id = new_card.id`.
  * **Immediate Doing:** If an entry starts with `DOING:`, it creates the card directly in the `doing` lane.
  * **Card Reference:** Typing `@card-12` in a log entry links that timestamped note directly to Card `#12`'s activity history and updates its `last_activity_at` timestamp.
  * **Tag Extraction:** Any `#tag` (e.g., `#win`, `#blocker`, `#incident`, `#project-x`) is parsed via regex `r'#([\w-]+)'` and stored in the JSON `tags` column.

### Feature 3: Corporate "Standup Mode" Generator (`/standup`)
* **User Story:** Every morning at 9:30 AM, I need to answer what I did yesterday, what I am doing today, and what is blocking me without digging through old notes.
* **Query Logic:**
  * **Yesterday (or Last Working Day):** Runs a query on `audit_events` and `daily_logs` for the previous active workday (automatically looks back to Friday if today is Monday). Groups items by:
    * *Completed Cards* (`event_action = 'COMPLETED'`)
    * *Progress & Movements* (`event_action = 'MOVED_LANE'`)
    * *Key Notes Logged* (`daily_logs` entries)
  * **Today's Plan:** Pulls all non-archived cards currently in `doing` and top-priority `todo` cards.
  * **Blockers:** Pulls any card in the `blocked` lane or any log entry from the last $48\text{ hours}$ tagged `#blocker`.
* **UI Action:** Includes a **"Copy as Markdown for Slack/Teams"** button for instant pasting into team chat channels.

### Feature 4: Audit Replay & "Brag Document" View (`/audit`)
* **User Story:** During 1-on-1s, timesheet filing, or annual performance reviews, I want to filter my entire work history by date range and project tag.
* **Capabilities:**
  * Date Range Picker: *This Week, Last Month, Q1/Q2/Q3/Q4, Custom*.
  * Filter by Tag/Category: Filter specifically for `#win`, `#impact`, `#incident`, or project tags.
  * Visual Timeline: Renders a day-by-day collapsible timeline showing every card completed and note recorded during that window, plus summary metrics (e.g., *"24 cards completed, 142 interstitial logs recorded"*).

### Feature 5: Board Hygiene & Anti-Stagnation Engine
* **User Story:** I stopped using my old Kanban board because the "Done" lane got cluttered and old tasks rotted in "Doing."
* **Automated Rules (Run on Python daemon startup or nightly cron):**
  1. **Auto-Archive Done Cards:** Any card in the `done` lane where `completed_at` is older than $24\text{ hours}$ automatically gets `is_archived = 1`. It vanishes from the Kanban board (keeping the board clean) while remaining 100% visible in the Audit Replay view.
  2. **Stale Card Decay Visual:** Any card in the `doing` lane where `last_activity_at` is older than $3\text{ days}$ turns amber in the UI with a prompt: *"Stalled? Move back to Backlog, break it down, or log a note."*

---

## 6. REST API Specification (Python Daemon)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/today` | Returns today's interstitial logs, currently parked context banner, and active `doing` cards. |
| `POST` | `/api/logs` | Accepts `{ "content": "..." }`. Parses prefixes (`TODO:`, `PARK:`) and `#tags`, inserts log, spawns card if applicable, and logs audit event. |
| `Patch` | `/api/logs/{id}/complete` | If a log entry is linked to a card, marks the linked card as `done` directly from the daily log stream. |
| `GET` | `/api/standup` | Aggregates last working day's audit events, today's `doing` lane, and active `#blocker` items. |
| `GET` | `/api/audit` | Query params: `start_date`, `end_date`, `tag`, `search_query`. Returns grouped chronological audit trail. |
| `GET` | `/api/board` | Returns non-archived cards grouped by lane, enriched with `days_since_activity` for stale card highlighting. |
| `PUT` | `/api/cards/{id}/move` | Moves card between lanes; SQLite trigger automatically records the immutable audit event. |
| `POST` | `/api/hygiene/run` | Manually or automatically triggers archiving of old `done` cards. |

---

## 7. Frontend UI/UX & Keyboard-First Specification

To beat the speed of physical paper, the React UI must eliminate mouse dependency:

1. **Global Navigation Bar (Minimalist):**
   * `1` or `Alt+1`: **Today Stream** (Default Home)
   * `2` or `Alt+2`: **Standup Brief**
   * `3` or `Alt+3`: **Kanban Board** (Secondary View)
   * `4` or `Alt+4`: **Audit & Brag Ledger**
2. **Auto-Focus Rule:** Whenever the browser tab gains focus (`window.onfocus`) on the `/today` route, the cursor automatically jumps to the bottom quick-capture input bar.
3. **Quick-Capture Bookmarklet / Mini-Window:**
   * Expose a lightweight route `/quick-capture` designed for a $500 \times 180\text{ px}$ frameless browser popup (`window.open`), allowing users to bind an OS shortcut or browser shortcut that opens a floating command bar over any corporate app, saves the note on `Enter`, and auto-closes.

---

## 8. Phased Implementation Roadmap

### Phase 1: The Data & Audit Foundation (Backend & SQLite)
* Write a migration script to back up your existing SQLite `.db` file.
* Add the `daily_logs` and `audit_events` tables and alter the existing `cards` table with timestamp and archive columns.
* Implement the SQLite triggers for automatic lane movement and completion logging.

### Phase 2: The Interstitial Stream & Inline Parser
* Build the `POST /api/logs` endpoint with regex parsing for `TODO:`, `DOING:`, `PARK:`, and `#tags`.
* Build the React `/today` view as the new default homepage with auto-focusing input and inline card status indicators.

### Phase 3: Corporate Ritual Views (The Retention Hook)
* Implement `/api/standup` with smart Monday-to-Friday lookback logic.
* Build the `/standup` and `/audit` React views with one-click Markdown copy buttons.

### Phase 4: Board Hygiene & Polish
* Add the auto-archiving logic for completed cards and the visual decay indicator for stale `doing` cards on your existing Kanban component.