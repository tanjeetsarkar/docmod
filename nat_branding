# Brand & In-App Microcopy Specification: `nat.`

## 1. Core Brand Identity

### 1.1 Name & Orthography
* **Brand Mark:** `nat.` (Strictly lowercase, always followed by a hard period).
* **Primary Tagline:** *not a to do.*
* **Contextual Backronyms:**
  * *For the anti-bloat / origin story:* **n**ot **a**nother **t**rello.
  * *For corporate / audit utility:* **n**otes, **a**udited & **t**imestamped.
* **Pronunciation:** `/næt/` (Rhymes with *cat* or *flat*).

### 1.2 Brand Voice & Persona
`nat.` speaks like a sharp, pragmatic senior engineer who hates bureaucracy, ceremonies, and bloated productivity tools.
* **Zero Guilt:** Traditional to-do apps punish you with red overdue badges. `nat.` never shames the user; it calmly records reality and clears clutter out of your way.
* **Terse & Tactile:** Sentences are short. Words feel mechanical and fast—like ink hitting paper or a commit hitting a git log.
* **Anti-Ceremony:** Never use corporate project-management jargon like *"Grooming," "Sprint Velocity," "Deliverables,"* or *"Action Items."* Use *"nats," "stream," "parked," "doing,"* and *"ledger."*

---

## 2. The Verb Lexicon (Habit-Building Language)

For users to stick to the app, the brand name must replace the action in everyday speech and across the interface:

| Term | Part of Speech | Definition | Example Usage |
| :--- | :--- | :--- | :--- |
| **nat** | *Verb* | To capture a fleeting thought, task, blocker, or win in $< 2\text{ seconds}$ without leaving your flow. | *"Hold on, let me nat that API port before I forget."* |
| **a nat** | *Noun* | A single timestamped entry in the daily interstitial stream. | *"Drop a nat whenever you switch tasks."* |
| **natted** | *Adjective / Past Verb* | Safely written to the local SQLite audit ledger; no longer taking up working memory. | *"Don't worry about the Q3 metric, it's natted."* |
| **natting** | *Gerund* | The act of interstitial journaling throughout the workday. | *"Natting between calls keeps my brain clear."* |
| **un-natted** | *Adjective* | Volatile mental context or verbal decisions that haven't been captured yet. | *"Never jump into an urgent Slack huddle with un-natted state."* |

---

## 3. Visual & Typographic Direction

### 3.1 Typography
* **Brand Mark & Metadata (`nat.`, timestamps, `#tags`, `TODO:`):** Monospace (`JetBrains Mono`, `Fira Code`, or `IBM Plex Mono`). Gives the immediate impression of a fast local daemon and terminal precision.
* **Body Stream & Card Titles:** Crisp humanist sans-serif (`Inter`, `Geist`, or system UI) for effortless reading.

### 3.2 Color Palette ("Paper & Phosphor")
* **Light Mode (Physical Notebook Feel):**
  * Background: Warm Dot-Grid Paper (`#FAF8F5`)
  * Primary Ink: Deep Charcoal (`#18181B`)
  * Accent / Period in `nat.`: International Orange (`#EA580C`)
* **Dark Mode (Local Daemon Feel):**
  * Background: Matte Obsidian (`#0F1115`)
  * Primary Ink: Crisp Off-White (`#E4E4E7`)
  * Accent / Period in `nat.`: Phosphor Amber (`#F59E0B`)

### 3.3 CLI / Daemon Startup Banner & README Header
Display this in the Python console when the local daemon starts up:

```text
                 _     
  _ __    __ _  | |_   
 | '_ \  / _` | | __|  
 | | | || (_| | | |_  _ 
 |_| |_| \__,_|  \__|(_)  not a to do.
 ------------------------------------------------
 [daemon] localhost:7420 | sqlite: wal-mode | air-gapped
```

---

## 4. External Positioning & Launch Copy

### 4.1 GitHub Repository Metadata
* **Repo Name Suggestions:** `nat-log`, `notatodo`, `nat-local`, or `nat`
* **GitHub Short Description (About Box):**
  > `nat. (not a to do.) — Fast as a physical notebook. Audited like a git log. A 100% local Python, React, and SQLite work stream and automatic standup ledger.`
* **Topics/Tags:** `local-first` `sqlite` `interstitial-journaling` `productivity` `kanban` `developer-tools` `python` `react` `work-log`

### 4.2 Platform-Specific Launch Headlines
* **Hacker News (`Show HN`):**
  > *Show HN: nat. (not a to do.) – I replaced my dead Kanban board with a localhost interstitial work log (Python/React/SQLite)*
* **LinkedIn / Corporate Angle:**
  > *Why I stopped using Trello for personal notes and built "nat." (not a to do.)—an air-gapped work stream that writes my daily standup and year-end performance review automatically.*
* **Reddit (`r/selfhosted`, `r/productivity`, `r/ExperiencedDevs`):**
  > *Paper notebooks beat digital boards on speed, but fail on search and auditability. Meet nat. (not a to do.)—capture thoughts in 2 seconds, auto-build your brag doc.*

### 4.3 The Master Launch Pitch Paragraph (For `README.md`)
> Most digital note and Kanban apps fail for one simple reason: they treat every fleeting thought like project management overhead. By the time you open a browser tab, pick a board, choose a lane, and create a card, your train of thought is gone—which is why so many of us regress to a physical pen and notebook. Paper wins on zero-latency capture, but it fails miserably when you need to remember what you solved three Tuesdays ago or what to say in tomorrow's 9:30 AM standup. **`nat.`** (*not a to do.*) bridges that gap. Running entirely on your machine as a lightweight Python, React, and SQLite daemon, **`nat.`** gives you the frictionless speed of a paper scratchpad backed by an immutable audit ledger. You don't organize, categorize, or groom cards; you just *nat* your thoughts into a live daily stream as you switch tasks. Promote actionable lines to a secondary board when needed, and let **`nat.`** automatically compile your daily standups, timelines, and year-end wins behind the scenes.

---

## 5. In-App Microcopy Specification

### 5.1 Global Header & Navigation Bar
* **Top-Left Logo:** `nat.` *(Hover tooltip: `not a to do. — local sqlite ledger active`)*
* **Navigation Tabs (with keyboard shortcuts):**
  * `[1] Stream` *(Route: `/today`)*
  * `[2] Standup` *(Route: `/standup`)*
  * `[3] Board` *(Route: `/board`)*
  * `[4] Ledger` *(Route: `/audit`)*
* **Local Status Pill (Bottom-Right Footer):**
  * Connected: `● local sqlite · 0ms`
  * Offline/Daemon Down: `○ daemon asleep — restart python server to nat`

---

### 5.2 View 1: The Daily Stream (`/today`)

#### Primary Input Bar (Always Focused)
* **Default Placeholder:**
  `nat a thought, #win, #blocker, or start with TODO: ... (Enter to drop)`
* **Syntax Helper Subtext (Muted beneath input):**
  `Tip: Start with TODO: to spawn a card · PARK: to save mental state · #win for your brag doc`

#### Context-Switch Parking Banner (Triggered by `PARK:`)
* **Banner Header:** `⏸ BRAIN PARKED`
* **Banner Body:** `"{parked_content}"` *(e.g., "Halfway through refactoring auth middleware, line 140")*
* **Banner Subtext:** `Natted at {timestamp} before you switched context.`
* **Action Button:** `[Resume & Clear]` *(Clicking logs: `Resumed from parked state` in the audit trail).*

#### Active Focus Mini-Widget (Top Right of `/today`)
* **Header:** `On Your Desk Right Now (Doing)`
* **Empty State:** `Nothing in Doing. Pull a card or type DOING: below.`
* **Overload Warning (If $>3$ cards in Doing):** `You're juggling {count} things at once. Finish or drop one back to Todo.`

#### Stream Empty States
* **Morning (Before 12:00 PM, 0 nats):**
  `Fresh page. Nothing natted yet today. Dump what's in your head before your first call.`
* **Afternoon (After 12:00 PM, 0 nats):**
  `suspiciously quiet today. Nat a quick line on what you've been tackling.`

---

### 5.3 View 2: Corporate Standup Generator (`/standup`)

* **Page Title:** `The Daily Brief`
* **Page Subtitle:** `Everything you natted and moved since your last working day. Zero memory required.`
* **Section 1 Header (Yesterday / Friday):** `What Moved & Got Done ({day_name})`
  * *Empty State:* `No cards closed or nats logged on {day_name}.`
* **Section 2 Header (Today):** `On Deck Today`
  * *Empty State:* `No cards in Doing yet. Promote a nat from your stream to set today's focus.`
* **Section 3 Header (Blockers):** `In The Way (#blocker & Blocked Lane)`
  * *Empty State:* `Clear skies. Nothing tagged #blocker in the last 48 hours.`
* **Primary Action Button:** `[Copy Standup as Markdown]`
  * *Post-Click State:* `[✓ Copied — Paste into Slack/Teams]`

---

### 5.4 View 3: The Secondary Kanban Board (`/board`)

* **Page Subtitle:** `Cards serve the stream, not the other way around. Done cards vanish to the Ledger after 24h.`
* **Lane Titles & Sub-captions:**
  * **Backlog:** `Someday / Uncommitted`
  * **Todo:** `Queued Up`
  * **Doing:** `Active Focus (Keep <= 3)`
  * **Blocked:** `Waiting on Others`
  * **Done:** `Closed Today (Auto-archives tonight)`
* **Stale Card Decay Badge (Amber border after $3\text{ days}$ in Doing):**
  * *Badge Text:* `Stale · 4d no nats`
  * *Hover / Inline Nudge:* `Sitting in Doing for 4 days with zero activity. Still on this, or move it back to Todo?`
* **Nightly Hygiene Notification Banner (Dismissible):**
  * `🧹 Swept {count} finished cards off the board into your permanent Ledger.`

---

### 5.5 View 4: The Audit & Brag Ledger (`/audit`)

* **Page Title:** `The Permanent Ledger`
* **Page Subtitle:** `Your immutable paper trail. Filter by date or #tag for 1-on-1s, timesheets, and performance reviews.`
* **Search Input Placeholder:** `Search every nat, card title, or #project-tag...`
* **Quick Filter Pills:**
  * `[All Activity]` `[🏆 #win & #impact]` `[✅ Completed Cards]` `[🔥 #incident & #blocker]`
* **Summary Banner (Dynamic per date range):**
  * `Between {start_date} and {end_date}, you logged {log_count} nats, shipped {done_count} cards, and recorded {win_count} #wins.`
* **Export Button:** `[Export Brag Doc (.md)]`
* **Empty Filter State:**
  * `Nothing natted matching that filter. Try widening your date range.`

---

### 5.6 System Toasts & Micro-Feedback

Keep toast notifications ultra-brief ($1.5\text{ seconds}$ duration, bottom-left corner):
* **Standard Note Logged:** `Natted.`
* **Inline `TODO:` Logged:** `Natted & spawned in Todo.`
* **Inline `DOING:` Logged:** `Natted & moved straight to Doing.`
* **Card Completed:** `Closed & stamped to Ledger.`
* **Context Parked:** `Brain parked. Go take that call.`
* **Card Archived:** `Tucked into the Ledger.`