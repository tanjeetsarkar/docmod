# Phase 2 Technical Specification: Anti-Organizer Onboarding, Zero-PyTorch Intelligence & Universal Excalidraw Integration

## 1. Scope, Prerequisites & Explicit Non-Goals

This specification covers the **Phase 2 expansion** built on top of your existing local-first Python, React, and SQLite daemon. It assumes the core Daily Log stream, Kanban cards, file/image attachment pipeline, immutable `audit_events` ledger, `entity_links`, and SQLite FTS5 search index (`search_index_fts`) are already implemented and operational.

### New Capabilities Covered in This Spec
1. **Zero-Organization Progressive Onboarding:** A 4-stage UI and SQLite state machine engineered to convert "anti-organizers" (natural pilers) without upfront taxonomy friction.
2. **Zero-PyTorch Offline Intelligence Engine:** Pure SQLite + Python standard library heuristics powering **8 non-intrusive smart suggestions** and a **self-tuning anti-Clippy feedback loop**.
3. **Optional Universal Excalidraw Integration:** A lazy-loaded React sketching layer built for *all* knowledge workers (not just engineers), combining exact-position deep-linking, screenshot-first annotation, text-to-sticky promotion, 5 thinking stamps, FTS5 searchable diagram text, visual audit snapshots, and screen-share-safe presentation mode.

### Explicit Non-Goals
* **Zero PyTorch / Heavy ML Runtimes:** No PyTorch, TensorFlow, Sentence-Transformers, or multi-gigabyte local LLMs. Baseline intelligence must add $0\text{ MB}$ of ML dependencies and execute in under $5\text{ ms}$ on a standard corporate laptop CPU.
* **No Auto-Generated Visual Canvases or Force-Directed Note Graphs:** Text notes, logs, and cards will never be projected onto infinite whiteboards or jittery physics graphs. Visual canvas space is reserved strictly for deliberate, opt-in Excalidraw sketching anchored to existing notes or cards.

---

## 2. Behavioral Premise: Anti-Organizers & Universal Visual Thinking

Phase 2 pairs two complementary behavioral insights: why people reject filing systems, and why *everyone*—from engineers to managers, PMs, consultants, and writers—benefits from low-stakes visual synthesis when it stays tethered to linear text.

### 2.1 Understanding "Anti-Organizers" (Pilers vs. Filers)

| Cognitive Pattern | Why Traditional Apps Fail | Phase 2 Design Countermeasure |
| :--- | :--- | :--- |
| **Pilers vs. Filers** | Roughly half of knowledge workers are natural "pilers" who rely on recency and visual context. Nested folders feel like graveyards where thoughts vanish out of sight. | Hide structural views on Day 1; let users pile raw text freely while background SQL math clusters and resurfaces connections automatically. |
| **Extraneous Cognitive Load** | Stopping mid-thought to pick a folder, tag, or card title steals working memory from actual problem-solving (germane load) and breaks flow. | Zero mandatory metadata at entry; offer 1-click passive inline pills *after* the thought is safely captured. |
| **Taxonomy Fatigue & Guilt Cycle** | Maintenance backlogs and red "Overdue" badges trigger shame, causing messy thinkers to abandon digital tools for physical paper. | Replace red overdue counters with compassionate stale-item relief and guilt-free, 100% searchable reversible archiving. |
| **Defensive Hoarding & Loss Aversion** | Corporate workers hoard messy piles out of fear of losing proof or forgetting fixes. They resist cleanup unless retrieval feels guaranteed. | Prove effortless recall early (Day 4–5 Trust Aha! Moment) and guarantee every archived note or diagram remains instantly searchable. |

### 2.2 The Deeper Psychology of Sketching (Beyond Architects)

| Cognitive Mechanism | Behavioral Reality | Product Implication |
| :--- | :--- | :--- |
| **The Drawing Effect** | Drawing a concept roughly doubles free recall compared to writing it alone—regardless of artistic skill—because translating ideas into boxes and arrows forces active encoding. | Make converting raw text into visual layouts a 1-click habit (`Think Visually`), not a separate software workflow. |
| **Dual Coding & Breaking Linearity Tyranny** | Bullet lists encode sequential events well, but fail at spatial trade-offs, power dynamics, and causal loops. Pairing text with a linked sketch builds two independent memory traces (verbal + visual). | Anchor every Excalidraw frame directly beside its corresponding Daily Log lines, Kanban card, or `#decided` ruling. |
| **Dismantling Sketch Inhibition** | Adults avoid whiteboards due to *skill-set inhibition* ("I can't draw"), *personal inhibition* (perfectionism), and *social inhibition* (fear of judgment). | Excalidraw's hand-drawn roughness signals "work-in-progress safety"; **Screenshot-First Annotation** and **5 Thinking Stamps** eliminate Blank Canvas Paralysis. |
| **Active Synthesis vs. Passive Transcription** | Live typing encourages verbatim transcription; moving sticky notes or circling key numbers forces real-time synthesis. | Optimize the loop: *capture fast in messy linear text, synthesize selectively on canvas, present cleanly without leaking private notes.* |

---

## 3. Zero-Organization Progressive Onboarding

New users must never be greeted with an empty Kanban board, sidebars, or tag setup wizards. Structure emerges only *after* the app proves it can recall unorganized inputs reliably.

### 3.1 Four-Stage Progression State Machine

| Stage | Timing / Trigger | React UI Surface | Backend Behavior & Behavioral Goal |
| :--- | :--- | :--- | :--- |
| **Stage 0: The Anti-Tour** | Minute 1 (`stage = 0`) | `minimal_mode = true`. Hide Kanban tabs, sidebars, filter bars, and settings chrome. Render only the `/today` stream with an inviting single-line composer. | Eliminates setup paralysis and signals immediately that unformatted dumps are welcome. |
| **Stage 1: Silent Capture** | Days 1–3 (`total_entries < 15`) | Only `/today` capture, quick shortcuts, and inline `Annotate` on pasted images are visible. Zero prompts asking users to tag or categorize. | Silently builds `term_entity_cooccurrence` and temporal cadence tables in SQLite. |
| **Stage 2: First Magic Recall** | Days 4–5 (`total_entries >= 15` and first high-confidence match fires) | Reveal a single subtle inline recall banner showing a real historical match from Day 1–3 while the user types. | Delivers the **Trust Aha! Moment**, proving messy capture produces instant retrieval. |
| **Stage 3: Emergent Structure** | Day 7+ (first Auto-Pile cluster reaches $\ge 4$ notes) | Display a gentle inline chip offering to view the clustered notes as a thread/mini-board. Accepting unlocks Kanban and advanced views. | Introduces structure as an earned reward generated from the user's own notes, not upfront homework. |

### 3.2 Manual Escape Hatch
Provide a discrete toggle (`Unlock Full Workspace`) inside the command palette or user menu so experienced users can bypass progressive gating at any time without penalizing newcomers.

---

## 4. Phase 2 SQLite Schema Additions

These tables extend your existing SQLite database (WAL mode enabled) cleanly without modifying existing core tables.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 1. Progressive Onboarding State Machine
CREATE TABLE IF NOT EXISTS user_progression (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    stage INTEGER DEFAULT 0,              -- 0: Anti-Tour, 1: Capture, 2: Recall, 3: Full
    minimal_mode INTEGER DEFAULT 1,
    total_entries INTEGER DEFAULT 0,
    first_recall_shown INTEGER DEFAULT 0,
    kanban_unlocked INTEGER DEFAULT 0,
    excalidraw_enabled INTEGER DEFAULT 1,
    first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Term-to-Entity Co-occurrence Matrix (Powers Implicit Linking)
CREATE TABLE IF NOT EXISTS term_entity_cooccurrence (
    term TEXT NOT NULL,                   -- Normalized lowercase token (len >= 4, non-stopword)
    entity_name TEXT NOT NULL,            -- e.g., '@Priya' or '[[Payments-V2]]'
    cooccurrence_count INTEGER DEFAULT 1,
    last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (term, entity_name)
);
CREATE INDEX IF NOT EXISTS idx_cooccurrence_term ON term_entity_cooccurrence(term);

-- 3. Weekly Temporal Cadence Cache (Powers Pre-Meeting Briefs)
CREATE TABLE IF NOT EXISTS entity_cadence_stats (
    entity_name TEXT NOT NULL,
    day_of_week INTEGER NOT NULL,         -- 0 (Sunday) through 6 (Saturday)
    hour_bucket INTEGER NOT NULL,         -- 0 through 23 (local time)
    occurrence_count INTEGER DEFAULT 1,
    last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_name, day_of_week, hour_bucket)
);

-- 4. Emergent Auto-Pile Clusters (Computed by Pure-Python Clustering Worker)
CREATE TABLE IF NOT EXISTS suggested_piles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggested_label TEXT NOT NULL,        -- Top TF-IDF phrase or shared entity
    note_ids_json TEXT NOT NULL,          -- JSON array of clustered note IDs
    cohesion_score REAL NOT NULL,         -- Average pairwise S(a, b) score
    status TEXT CHECK(status IN ('PENDING', 'ACCEPTED', 'DISMISSED')) DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. Self-Tuning Suggestion Engine Feedback (Anti-Clippy Guardrail)
CREATE TABLE IF NOT EXISTS suggestion_feedback (
    suggestion_type TEXT PRIMARY KEY,     -- e.g., 'AUTO_PILE', 'PASSIVE_ACTION', 'PRIOR_ART'
    accepted_count INTEGER DEFAULT 0,
    dismissed_count INTEGER DEFAULT 0,
    consecutive_dismissals INTEGER DEFAULT 0,
    confidence_threshold REAL DEFAULT 0.65,
    muted_until DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. Optional Excalidraw Scenes (Stored as Pure JSON Locally)
CREATE TABLE IF NOT EXISTS excalidraw_scenes (
    id TEXT PRIMARY KEY,                  -- UUID or project/date slug (e.g., 'payments-arch', 'daily-2026-11')
    title TEXT NOT NULL,
    elements_json TEXT NOT NULL,          -- Serialized non-deleted Excalidraw elements
    app_state_json TEXT NOT NULL,         -- Minimal persisted appState keys
    files_json TEXT DEFAULT '{}',         -- Embedded binary file references (e.g., pasted screenshots)
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 7. Bidirectional Excalidraw Deep Links & Live SVG Previews
CREATE TABLE IF NOT EXISTS excalidraw_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id TEXT NOT NULL REFERENCES excalidraw_scenes(id) ON DELETE CASCADE,
    target_element_id TEXT NOT NULL,      -- Frame ID or Element ID on the canvas
    target_type TEXT CHECK(target_type IN ('frame', 'element', 'group')) DEFAULT 'frame',
    origin_workflow TEXT CHECK(origin_workflow IN (
        'sketch_from_card',
        'screenshot_annotation',
        'sticky_promotion',
        'manual_copy_link'
    )) DEFAULT 'sketch_from_card',
    target_label TEXT NOT NULL,           -- Pill display label
    card_id INTEGER,                      -- Optional link to existing Kanban card
    note_id INTEGER,                      -- Optional link to existing Daily Log entry
    attachment_id INTEGER,                -- Optional link when annotating a pasted screenshot
    cached_svg TEXT,                      -- Sanitized SVG thumbnail synced on debounced save
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_excalidraw_links_card ON excalidraw_links(card_id);
CREATE INDEX IF NOT EXISTS idx_excalidraw_links_note ON excalidraw_links(note_id);
CREATE INDEX IF NOT EXISTS idx_excalidraw_links_scene ON excalidraw_links(scene_id);

-- 8. SQLite FTS5 Index of Every Text Box Inside Excalidraw (Zero Visual Black Holes)
CREATE VIRTUAL TABLE IF NOT EXISTS excalidraw_text_fts USING fts5(
    scene_id UNINDEXED,
    frame_id UNINDEXED,
    element_id UNINDEXED,
    scene_title,
    text_content,
    tokenize = 'porter unicode61'
);

-- 9. Visual Auditability: Compressed SVG Milestone Snapshots Linked to audit_events
CREATE TABLE IF NOT EXISTS excalidraw_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id TEXT NOT NULL REFERENCES excalidraw_scenes(id) ON DELETE CASCADE,
    frame_id TEXT NOT NULL,
    audit_event_id INTEGER,               -- Foreign reference to existing audit_events.id
    trigger_type TEXT CHECK(trigger_type IN ('DAILY_DIFF', 'MANUAL_MILESTONE')) DEFAULT 'DAILY_DIFF',
    snapshot_label TEXT,                  -- e.g., 'Q4 Hiring Plan v2'
    svg_compressed BLOB NOT NULL,         -- zlib-compressed sanitized SVG bytes
    captured_date TEXT NOT NULL,          -- YYYY-MM-DD (dedupes automatic daily snapshots)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snapshots_scene_frame ON excalidraw_snapshots(scene_id, frame_id, created_at);
```

---

## 5. Zero-PyTorch Offline Intelligence Engine

Corporate work notes are dense with exact domain vocabulary: service names, Jira IDs, client names, error codes, `@Person` mentions, and weekly meeting schedules. Pure SQLite + deterministic Python heuristics deliver high relevance with zero ML runtime overhead.

### 5.1 Deterministic Clustering Math (No Embeddings Required)
To cluster untagged notes over a rolling $14\text{-day}$ window without neural networks, compute a weighted pairwise similarity score $S(a, b)$ in Python:

$$S(a, b) = 0.45 \cdot J_{\text{entities}}(a, b) + 0.35 \cdot J_{\text{keywords}}(a, b) + 0.20 \cdot T_{\text{proximity}}(a, b)$$

* **$J_{\text{entities}}(a, b)$:** Jaccard similarity of extracted `@Person` and `[[Project]]` entities between note $a$ and note $b$.
* **$J_{\text{keywords}}(a, b)$:** Jaccard similarity of the top 10 non-stopword tokens (minimum length 4, weighted by inverse document frequency from SQLite).
* **$T_{\text{proximity}}(a, b)$:** Exponential temporal decay capturing work bursts:
  $$T_{\text{proximity}}(a, b) = \exp\left(-\frac{|\Delta t|}{48\text{ hours}}\right)$$
* **Connected Components:** Form edges where $S(a, b) \ge \tau$ (default $\tau = 0.55$). Any connected component with 4 or more untagged notes becomes a `PENDING` entry in `suggested_piles`, titled by the highest-frequency shared bigram or entity.

### 5.2 The 8 Smart, Engaging Suggestions

| # | Suggestion Type | Zero-PyTorch Engine Logic | UI Behavior & User Action |
| :--- | :--- | :--- | :--- |
| **1** | **Auto-Pile Clustering ("Emerging Thread")** | Daily Python worker computes $S(a, b)$ on untagged entries from the past 14 days. | Quiet banner in `/today`: *"4 scattered notes look related to **Auth Timeout**. Bundle them?"* (`Bundle` / `Ignore`). |
| **2** | **Passive Action & Decision Spotting** | Compiled Python regex scans saved lines for commitment cues (`"I'll send"`, `"need to check"`, `"follow up"`) or resolution cues (`"we agreed"`, `"finalized"`, `"going with"`). | Faint inline pill fades in beside the line without interrupting typing: `[+ Track]` or `[Log #decided]`. |
| **3** | **Cadence-Aware Pre-Meeting Briefs** | Background ticker checks `entity_cadence_stats` for any `@Person` occurring $\ge 3$ times on the current weekday within the next $30\text{ minutes}$. | Soft top strip 15 minutes prior: *"Talking to `@Priya` soon? 3 open notes and 1 recent file."* |
| **4** | **"You Already Solved This" (Prior-Art Rescue)** | Triggered when pasted/typed text contains error patterns (`Exception`, `502`, `timeout`, stack traces) or a `?`. Runs SQLite `bm25` across `search_index_fts` and `excalidraw_text_fts` for entries older than $7\text{ days}$. | Compact inline hint beneath the line: *"Similar issue logged 3 months ago — view fix."* |
| **5** | **Zero-Effort Implicit Linking** | Queries `term_entity_cooccurrence` for typed nouns; fires when $P(\text{entity} \mid \text{term}) \ge 0.75$ with `cooccurrence_count >= 4`. | Ghost tag preview next to cursor accepted via `Tab`: `Link to [[Payments-V2]]?` |
| **6** | **Compassionate Stale-Item Relief** | Daily query against `audit_events` for active cards or todos untouched for more than $7\text{ days}$. Strictly avoids red overdue styling. | Low-stress inline card prompt: *"Untouched for 9 days — still care about this?"* (`Keep` · `Snooze 1w` · `Drop guilt-free`). |
| **7** | **Reversible "Declutter Confidence" Sweep** | Weekly job identifies resolved threads and unpinned notes older than $30\text{ days}$ sitting in active views. | 1-click **Sweep to Searchable Archive** action with explicit assurance that search still indexes every word and undo is instant. |
| **8** | **End-of-Day "Invisible Progress" Digest** | At 17:30 local time (configurable), aggregates top 3 entities and recurring noun phrases touched today via SQLite counts. | Calm 3-bullet summary card validating progress even when zero checkboxes were ticked. |

### 5.3 Anti-Clippy Guardrails & Self-Tuning Feedback Loop
Enforce three hard rules in the Python suggestion dispatcher:
1. **Zero Focus Stealing:** Render suggestions strictly as inline ghost pills or in a collapsible peripheral strip—never modal popups.
2. **Strict Display Budget:** Cap visible suggestions at a maximum of **2 active prompts at once**, ranked by confidence score.
3. **Self-Tuning Threshold Adaptation (`POST /api/suggestions/feedback`):**
   * **On Accept:** Increment `accepted_count`, reset `consecutive_dismissals = 0`, lower `confidence_threshold` by $0.02$ (floor $0.50$).
   * **On Dismiss:** Increment `dismissed_count` and `consecutive_dismissals`. At `consecutive_dismissals >= 3`, raise `confidence_threshold` by $+0.10$ (ceiling $0.95$) and set `muted_until = NOW() + 14 days`.

*(Optional Future Extensibility: A zero-PyTorch static embedding plugin via `model2vec` + NumPy can plug into this exact scoring interface later if synonym-level recall is ever requested.)*

---

## 6. Optional Universal Excalidraw Integration

Excalidraw is integrated as a **100% opt-in, lazy-loaded visual thinking companion** engineered for both technical and non-technical corporate workflows—without ever becoming mandatory or breaking the audit trail.

### 6.1 Behavioral Guardrails & Simplified `UIOptions`
* **Dormant Until Invoked:** Dynamic `React.lazy()` code-splitting ensures `@excalidraw/excalidraw` and `@excalidraw/excalidraw/index.css` incur **zero RAM or startup cost** for users who stay purely in text.
* **Anchored Artifacts (No Orphaned Whiteboards):** Every canvas frame originates from or binds to a Daily Log date, Kanban card, pasted screenshot, `@Person` dossier, or `#decided` entry—eliminating `"Untitled Drawing 14"` clutter.
* **Reduced Tool Noise:** Configure Excalidraw's `UIOptions` on mount to hide cloud sync, live collaboration server controls, and complex export menus—keeping the surface focused on **Select, Box, Arrow, Freehand, Text, Laser Pointer, and the 5 Thinking Stamps**.

### 6.2 Core Linking Mechanics (Exact-Position Round-Trip)

#### A. One-Click "`+ Sketch` from Card" (Auto-Framed Creation)
1. Clicking **`+ Sketch`** on any card or note opens the associated project/topic scene (creating a row in `excalidraw_scenes` if absent).
2. React computes the rightmost bounding box $x_{\max}$ of existing non-deleted elements and inserts a new Excalidraw **Frame** (`type: "frame"`, width $900$, height $600$) at $x = x_{\max} + 160$.
3. Embed bidirectional metadata on the frame via `convertToExcalidrawElements`:
   * `name`: Card or note title (e.g., `"Q3 Pricing Trade-offs"` or `"Architecture Review: Checkout Retry"`).
   * `customData`: `{ cardId: 42, source: "localnote" }`.
   * `link`: `"localnote://card/42"`.
4. Persist a row in `excalidraw_links` and insert an interactive link pill + live SVG preview inside the card.

#### B. Exact-Position Viewport Deep-Linking (`scrollToContent`)
Clicking any sketch pill, SVG thumbnail, or FTS5 diagram search hit mounts Excalidraw, locates the target element or frame ID, and invokes `scrollToContent` inside `requestAnimationFrame` so container layout dimensions settle first:

```typescript
function jumpToCanvasTarget(excalidrawAPI: ExcalidrawImperativeAPI, targetElementId: string) {
  const elements = excalidrawAPI.getSceneElements();
  const target = elements.find(
    (el) => el.id === targetElementId && !el.isDeleted
  );
  if (!target) return;

  requestAnimationFrame(() => {
    excalidrawAPI.scrollToContent(target, {
      fitToViewport: true,
      viewportZoomFactor: 0.75,
      animate: true,
      duration: 350,
    });
  });
}
```

#### C. Copy-Link From Canvas (`generateLinkForSelection`) & Return Jump (`onLinkOpen`)
* Pass `generateLinkForSelection={(id, type) => "localnote://canvas/" + activeSceneId + "/" + type + "/" + id}` so users can right-click any shape or group on a canvas and paste an exact deep-link directly into any Daily Log line.
* Pass `onLinkOpen` to intercept `localnote://card/{id}` and `localnote://note/{id}` links, sliding the linked card or note open in a side drawer beside the canvas without losing viewport position.

#### D. Debounced Persistence & Live SVG Preview (`exportToSvg`)
* Debounce `onChange` writes to `PUT /api/excalidraw/scenes/{sceneId}` by $1500\text{ ms}$ (flushing on unmount).
* On save, filter each linked frame's elements (`el.frameId === frameId || el.id === frameId`), call `exportToSvg`, and persist the sanitized SVG into `excalidraw_links.cached_svg` so linked cards never show stale PNG screenshots.
* *(Optional Power-User Shortcut)* Lazily import `@excalidraw/mermaid-to-excalidraw` only when a user clicks **"Convert to Sketch"** on a Mermaid block inside a note.

### 6.3 The Six Universal Zero-Friction Canvas Patterns

#### Pattern 1: "Screenshot-First Annotation" (The Anti-Inhibition Gateway)
* **Trigger:** Hovering over any image or screenshot pasted (`Ctrl+V`) into the Daily Log or a card reveals an **`Annotate`** button.
* **Implementation:**
  1. Lazy-loads a focused Excalidraw modal pre-populated with a frame containing the pasted image (`type: "image"`, locked in background so strokes never accidentally drag the screenshot).
  2. Immediately invokes `excalidrawAPI.setActiveTool({ type: "arrow" })` and sets `currentItemStrokeColor: "#e03131"` (red ink) in `initialData.appState`.
  3. Pressing `Esc` or clicking **`Done`** saves the scene (`origin_workflow = 'screenshot_annotation'`), exports the combined SVG, and replaces the inline image preview with the crisp annotated visual—while keeping the original clean file untouched on disk.

#### Pattern 2: "Text-to-Sticky-Notes" Promotion (`Think Visually`)
* **Trigger:** Highlighting 3 to 10 lines in the Daily Log or inside a card displays a subtle floating action: **`Think Visually`**.
* **Implementation:**
  1. Splits highlighted non-empty lines into discrete strings and strips leading markdown bullets (`- `, `* `, `[] `).
  2. Creates a new Excalidraw Frame titled from the first line or parent card, and lays out each line as an individual `convertToExcalidrawElements` rectangle (`backgroundColor` cycled across soft pastel fills, `fillStyle: "solid"`, `label: { text: lineText }`) arranged in a neat 3-column grid inside the frame.
  3. Stores `{ noteId, lineIndex }` in each sticky's `customData` and links the frame back to the originating Daily Log section so messy linear bullets become spatially rearrangeable in one click.

#### Pattern 3: Five 1-Click "Thinking Stamps" (Anti-Choice-Overload Scaffolds)
Instead of a bloated template marketplace, render a compact 5-button **"Stamps"** pill bar in Excalidraw's `renderTopRightUI` prop. Clicking any stamp appends a pre-defined JSON element factory at the center of the current viewport (`appState.scrollX`, `appState.scrollY`):
1. **2x2 Trade-off Grid:** Intersecting sketchy axes with 4 editable quadrant labels (`Impact vs. Effort` default).
2. **Stakeholder / Influence Map:** Three concentric dashed circles (`Core Decision Makers`, `Influencers`, `Informed`).
3. **Cause-and-Effect Flow:** Three connected sketchy boxes with bound arrows ready for double-click labeling.
4. **Pros / Cons / Open Questions:** Three vertical swimlane headers with starter sticky rectangles.
5. **Milestone Strip (`Now -> Next -> Later`):** Horizontal directional arrow with 3 labeled milestone nodes.

#### Pattern 4: SQLite FTS5 Deep Indexing of Canvas Text (Zero Visual Black Holes)
* **Backend Sync:** Whenever `PUT /api/excalidraw/scenes/{sceneId}` persists updated `elements_json`, Python executes a lightweight synchronous parse (under $2\text{ ms}$):
  1. Deletes existing rows in `excalidraw_text_fts` where `scene_id = ?`.
  2. Iterates through non-deleted elements where `el.get("type") == "text"` and `el.get("text", "").strip()` is non-empty.
  3. Inserts `(scene_id, el.get("frameId") or "", el["id"], scene_title, el["text"])` into `excalidraw_text_fts`.
* **Search Integration:** Unified global search queries both `search_index_fts` and `excalidraw_text_fts`. Clicking a diagram search result navigates to `scene_id` and calls `jumpToCanvasTarget(api, element_id)`, flying the camera straight to the exact text box inside the drawing.

#### Pattern 5: Visual Auditability ("Canvas Snapshots" in `audit_events`)
* **Automatic Daily Diff Snapshot:** When a linked frame's cached SVG changes on a *new calendar date* (`captured_date != today`), Python compresses the SVG via standard-library `zlib.compress()`, writes a row to `excalidraw_snapshots` (`trigger_type = 'DAILY_DIFF'`), and appends a matching record to the existing `audit_events` ledger (`event_type = 'CANVAS_EVOLVED'`, `summary = "Updated sketch: Q4 Hiring Plan"`).
* **Manual Milestone Stamp:** Clicking **`Stamp Milestone`** inside the Excalidraw frame header prompts for an optional 3-word label (e.g., `"Post-Review Approved"`) and saves a `MANUAL_MILESTONE` snapshot immediately.
* **Visual Replay:** Hovering or clicking historical canvas audit events opens a lightweight side-by-side SVG diff/timeline modal showing how a strategy, org map, or architecture evolved across weeks.

#### Pattern 6: "Clean Present" Mode (Corporate Screen-Share Safety)
* **Trigger:** A **`Present Frame`** icon button sits directly beside every Excalidraw link pill and SVG thumbnail inside cards and Daily Logs.
* **Implementation:**
  1. Enters a dedicated full-viewport route/overlay (`/present/canvas/{sceneId}/{frameId}`) that completely unmounts the Daily Log, Kanban lanes, reminders, and sidebars—eliminating any risk of leaking private notes during Zoom/Teams/Meet screen-shares.
  2. Mounts Excalidraw in `viewModeEnabled: true` (with a 1-click toggle to unlock live co-editing), triggers `scrollToContent(targetFrame, { fitToViewport: true, viewportZoomFactor: 0.92 })`, and activates Excalidraw's built-in **Laser Pointer** tool (`setActiveTool({ type: "laser" })`).
  3. Pressing `Esc` exits cleanly back to the user's private workspace.

---

## 7. Phase 2 Daemon Workers & REST API Contract

### New Python Background Jobs
1. **Incremental Co-occurrence, Cadence & Canvas FTS5 Updater (Event Hooks):**
   * On note save: tokenizes new text (pure Python regex + stopword set) and upserts `term_entity_cooccurrence` and `entity_cadence_stats` in under $2\text{ ms}$.
   * On Excalidraw scene save: extracts `type == "text"` nodes into `excalidraw_text_fts` and checks whether a `DAILY_DIFF` zlib-compressed SVG snapshot should be logged to `excalidraw_snapshots` + `audit_events`.
2. **Nightly Auto-Pile & Stale-Relief Scanner (Every $6\text{ h}$):** Computes pairwise $S(a, b)$ clustering over the last 14 days of untagged entries, flags stale items untouched for $> 7\text{ days}$, and refreshes the 17:30 End-of-Day digest cache.

### Phase 2 REST API Endpoints

| Endpoint | Method | Purpose | Key Request / Response Fields |
| :--- | :--- | :--- | :--- |
| `/api/onboarding/state` | GET / PATCH | Read or advance progressive onboarding stage | `stage`, `minimal_mode`, `kanban_unlocked`, `excalidraw_enabled` |
| `/api/suggestions/live` | POST | Real-time passive action, prior-art (notes + canvas FTS5), & implicit links | Input: `draft_text` -> Output: max 2 ranked inline suggestion payloads |
| `/api/suggestions/daily` | GET | Fetch pending Auto-Piles, Cadence Briefs, Stale Relief, & EOD Digest | Filtered by `suggestion_feedback` thresholds & mute windows |
| `/api/suggestions/feedback` | POST | Record accept/dismiss to self-tune thresholds | `suggestion_type`, `action` (`ACCEPT` / `DISMISS`) -> updated threshold |
| `/api/piles/{id}/resolve` | POST | Accept (group into view/tag) or dismiss a suggested pile | `action` (`ACCEPT` / `DISMISS`), optional `custom_label` |
| `/api/excalidraw/scenes/{id}` | GET / PUT | Load or save scene JSON, refresh `excalidraw_text_fts`, sync SVGs & daily snapshots | `elements_json`, `app_state_json`, `files_json`, `frame_svgs` |
| `/api/excalidraw/links` | GET / POST | Create/query deep links (`sketch_from_card`, `screenshot_annotation`, `sticky_promotion`) | `scene_id`, `target_element_id`, `origin_workflow`, `card_id`, `note_id`, `cached_svg` |
| `/api/excalidraw/search` | GET | Query `excalidraw_text_fts` for exact-box deep-link matches | Query: `?q=...` -> Returns `scene_id`, `frame_id`, `element_id`, snippet |
| `/api/excalidraw/snapshots/{scene_id}/{frame_id}` | GET / POST | Retrieve visual audit timeline or create a `MANUAL_MILESTONE` snapshot | `snapshot_label`, decompressed SVG list, timestamps, `audit_event_id` |