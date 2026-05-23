# Enterprise Dashboard — Best Practices, Features & Roadmap

**Application:** Model Risk Monitoring Dashboard (Regional Summary → Regional Details → Deep Dive)  
**Informed by:** Grafana · Datadog · Tableau · Power BI · Looker · Bloomberg Terminal · Databricks

---

## Table of Contents

1. [Industry Benchmark — What the Best Dashboards Get Right](#1-industry-benchmark--what-the-best-dashboards-get-right)
2. [Information Architecture & Navigation](#2-information-architecture--navigation)
3. [Data Visualization Principles](#3-data-visualization-principles)
4. [UX & Interaction Design](#4-ux--interaction-design)
5. [Performance Best Practices](#5-performance-best-practices)
6. [Accessibility — WCAG 2.1 AA](#6-accessibility--wcag-21-aa)
7. [Security, Compliance & Audit](#7-security-compliance--audit)
8. [Development Best Practices](#8-development-best-practices)
9. [Testing Strategy](#9-testing-strategy)
10. [Feature Roadmap — Phased](#10-feature-roadmap--phased)
11. [Application Management](#11-application-management)

---

## 1. Industry Benchmark — What the Best Dashboards Get Right

### Grafana — Visualization Flexibility
Grafana's defining quality is that every panel is independently configurable. Users do not ask an admin to change a chart — they change it themselves. Key lessons:
- **Panel-level time range override** — one panel can show "last 7 days" while another shows "last 30 days" on the same page
- **Variable templating** — dropdown filters at the top of the page dynamically rewrite all queries on that page
- **Link chaining** — clicking a data point navigates to a different dashboard with context passed as URL params (exactly your drill-down model)
- **Annotations** — events (deployments, incidents) overlaid on time-series charts as vertical markers

**Apply to your app:** Your RAG status drill-down is Grafana's link chaining. Threshold lines on Gini/PSI charts come from Grafana's threshold markers. Panel-level date range pickers for the Deep Dive.

---

### Datadog — Contextual Intelligence
Datadog's strength is that the dashboard is never just a display — it's an investigation tool.
- **Anomaly detection** overlaid directly on charts, not in a separate alert list
- **Correlate across panels** — brushing (highlighting) a time range in one panel highlights the same range in all panels on the page
- **Audit trail on the dashboard itself** — every change to a dashboard is logged: who changed what panel, when, with a diff view
- **Saved Views** — users save a combination of filters + time range + layout as a named "View" they can return to or share

**Apply to your app:** Threshold breach highlighting across the model metrics table. Saved filter combinations for power users (e.g., "Singapore RED models, last quarter").

---

### Tableau / Power BI — Business Intelligence Layer
BI tools excel at making data trustworthy and shareable.
- **Data freshness indicator** — every view shows "Last updated: 14 minutes ago". Users always know if data is stale
- **Certified data sources** — a green checkmark on a metric means it has been validated. Users trust certified numbers
- **Scheduled subscriptions** — users receive a PDF/email snapshot of their configured dashboard on a schedule (e.g., every Monday morning)
- **Export to Excel/PDF** — one-click export of any table or chart with the current filters applied

**Apply to your app:** "Data as of [timestamp]" on every page. Export the current Regional Details table filtered view to CSV. Weekly email digest of RED model counts by region.

---

### Bloomberg Terminal — Information Density for Experts
Bloomberg serves professional users who want maximum information in minimum space.
- **Keyboard-first navigation** — every view accessible with mnemonics. Power users never touch the mouse
- **Configurable layouts** — users split the screen into panels they arrange themselves
- **Context persistence** — the last model you viewed is remembered; returning to any screen shows where you left off

**Apply to your app:** Keyboard shortcuts for common actions (Escape to go back, R/A/G to filter by status). Remember the last region and country the user was viewing.

---

### Looker — Governance & Collaboration
Looker treats every dashboard as a living document.
- **In-dashboard comments** — users annotate specific data points or cells with notes that are visible to the team
- **Exploration from any cell** — right-clicking any data point opens an "Explore from here" menu to investigate further
- **Version history** — dashboard layouts and metric definitions are versioned; you can see what the dashboard looked like 3 months ago
- **Row-level security** — what region a user can see is enforced in the query layer, not in the UI

**Apply to your app:** Annotation on individual model rows ("This PSI spike was due to Q3 data refresh"). Row-level security so APAC analysts can only see APAC models.

---

## 2. Information Architecture & Navigation

### The Three-Level Hierarchy Is Correct — Enforce It Consistently

```
Level 1: Regional Summary          → Answer: "Which countries need attention?"
Level 2: Regional Details          → Answer: "Which models in this country/status are at risk?"
Level 3: Deep Dive                 → Answer: "Why is this model's metric in this RAG status?"
```

Each level must answer exactly one question. If a page tries to answer two questions, split it.

### Breadcrumb Navigation — Always Show Context

Users drilling down lose their spatial context. A persistent breadcrumb prevents disorientation.

```
APAC  >  Singapore  >  Total  >  Model XYZ  >  Gini
 ↑           ↑           ↑          ↑           ↑
Click to   Click to   Click to   Click to   Current
Level 1    Level 2    Level 2    Level 3    (not clickable)
with APAC  filtered   filtered   filtered
```

Implementation: derive the breadcrumb array directly from URL params — no additional state needed.

### Active Filter Chips — Always Visible

Show the active filters as removable chips below the breadcrumb. Users can remove a chip to widen scope without pressing back.

```
[ APAC × ]  [ Singapore × ]  [ RED × ]     ← click × to remove that filter
```

When all chips are removed, the page returns to its broadest view (equivalent to Level 1).

### Global Region Switcher

The region selector should be in the top navigation, not per-page. Switching region from APAC to EMEA should re-run the current page with the new region, not navigate away.

```
[ 🌏 APAC ▼ ]   ← global region selector in nav bar
```

This is how Grafana's variable templating works — one control rewrites all queries.

---

## 3. Data Visualization Principles

### The RAG Status Table — Specific Guidance

**Colour is not enough.** Always combine colour with a symbol or label for colour-blind users (~8% of male users).

```
❌  Bad:   Red cell (colour only)
✅  Good:  🔴 12  or  [RED] 12  or  ▲ 12
```

**Show delta, not just current count.** A RED count of 12 means nothing without context. RED count of 12 (+3 from last run) is immediately actionable.

```
Country        Red        Amber     Green     Total
Singapore    🔴 12 ▲3    🟡 8      🟢 45     65
India        🔴 5        🟡 3 ▼1   🟢 62     70
```

**Sortable columns.** Users must be able to sort by RED count descending to immediately see the worst country. Default sort should be by RED descending — that is the default attention priority.

**Row-level trend sparklines.** A tiny 7-day sparkline per row tells a story that the current count cannot: is this getting better or worse?

### Metric Charts (Gini, PSI) — Deep Dive

**Always show the threshold line.** The chart alone is meaningless without the breach threshold drawn as a horizontal reference line.

**Show the full distribution, not just the trend.** Add a secondary histogram panel alongside the time-series to show the distribution of scores across all models, with the selected model highlighted.

**Colour the area under the line by RAG status.** When Gini crosses from GREEN to AMBER, the background area changes colour. This makes the transition date visually obvious without reading data labels.

```
Gini over time
 0.8 |                          ____
 0.7 |--- threshold ----------/----\-----
 0.6 |              ___      /      \
 0.5 |_____________/   \____/        \___
      [  GREEN area  ][AMBER][GREEN][ AMBER ]
```

**Confidence intervals.** If your model produces confidence intervals on metrics, shade them. This is standard in financial risk dashboards.

### Chart Selection Guide

| Data type | Correct chart | Avoid |
|-----------|---------------|-------|
| RAG count by country | Stacked bar or heat map | Pie chart (hard to compare) |
| Metric trend over time | Line chart with threshold | Bar chart (hides trend direction) |
| Model score distribution | Histogram or violin plot | Line chart (hides distribution shape) |
| Country vs country comparison | Side-by-side bar | Radar/spider chart (hard to read) |
| Correlation between two metrics | Scatter plot | Two separate line charts |
| Current vs benchmark | Bullet chart | Gauge (wastes space) |

### Data Freshness — Non-Negotiable

Every page, every chart, every table must display:

```
Regional Details — Singapore  ·  As of: 2026-05-23 06:00 UTC  ·  Next refresh: 18:00 UTC
```

If data is older than expected (ETL job failed), show a warning banner:

```
⚠️  Data may be stale. Last successful refresh was 26 hours ago. Contact the data team.
```

This is what Tableau calls "data trust" — users must never wonder if they are looking at yesterday's numbers.

---

## 4. UX & Interaction Design

### Progressive Disclosure — The Core Principle

Show the minimum needed to make a decision at each level. Do not show model-level detail on the summary page. Forcing users to scroll past irrelevant information before reaching what they need is the most common dashboard failure.

```
Level 1: 6 numbers per country (R/A/G counts + delta + total + sparkline)
Level 2: 5-7 columns per model (name, country, metric scores, trend)
Level 3: Full metric history, distribution, benchmarks, documentation
```

### Empty States — Always Meaningful

Never show a blank table with no explanation.

```
❌  Bad:   Empty table. No rows.
✅  Good:  ✅ No RED models in Singapore. Last checked: 2026-05-23 06:00 UTC.
✅  Good:  🔍 No models match the current filters. Try removing the 'Status: RED' filter.
```

### Loading States — Avoid Layout Shift

Use skeleton screens (grey placeholder shapes in the exact layout of the final content) rather than spinners. The page layout should never jump when data loads.

```
Before load:                          After load:
┌─────────────────────────┐          ┌─────────────────────────┐
│ ████████  ███  ██  ███  │          │ Singapore  12  8   45   │
│ ████████  ██   ██  ███  │   →      │ India       5  3   62   │
│ ████████  ███  ██  ███  │          │ Japan       2  7   81   │
└─────────────────────────┘          └─────────────────────────┘
     (skeleton)                             (real data)
```

### Error States — Specific and Actionable

```
❌  Bad:   "An error occurred."
✅  Good:  "Could not load model metrics for Singapore. The data service returned a timeout.
           [Retry]  [View cached data from 2 hours ago]  [Report this issue]"
```

### Keyboard Shortcuts — For Power Users

Implement keyboard shortcuts that power users discover via a `?` help modal.

| Key | Action |
|-----|--------|
| `?` | Open keyboard shortcut reference |
| `Esc` | Go back to previous level |
| `R` | Filter by RED |
| `A` | Filter by AMBER |
| `G` | Filter by GREEN |
| `C` | Clear all filters |
| `E` | Export current view |
| `F` | Open search/filter panel |
| `↑ ↓` | Navigate table rows |
| `Enter` | Drill into selected row |
| `Ctrl+K` | Command palette (search all models/regions) |

### Hover States — Contextual Tooltips

Every metric value should have a tooltip explaining what it means, how it is calculated, and what the threshold is. Analysts know this; stakeholders often do not.

```
Hover over Gini score cell:
┌─────────────────────────────────────────┐
│ Gini Coefficient                        │
│ Value:     0.342                        │
│ Status:    AMBER                        │
│ Threshold: RED < 0.25 | AMBER 0.25-0.35 │
│ As of:     2026-05-23                   │
│ Previous:  0.318 (↑ deteriorating)     │
└─────────────────────────────────────────┘
```

### Saved Views (Power BI / Datadog Pattern)

Users frequently return to the same filtered view. Let them save it.

```
Current URL: /regional-details?region=APAC&country=SG&status=RED

[💾 Save this view]  →  "Name this view: ___________________"
                                         Singapore RED Models

Saved views appear in:
- Left sidebar under "My Views"
- Homepage as quick-access tiles
- Shared with team (optional)
```

Implementation: save the full URL as a named preference. The URL-as-state pattern you already use makes this trivial — a saved view is just a stored URL string.

### Command Palette (Ctrl+K)

Increasingly standard in developer tools (Linear, Vercel, Raycast). Lets users jump to any model, region, or view without navigating the hierarchy.

```
Ctrl+K opens:
┌─────────────────────────────────────────┐
│ 🔍 Search models, regions, views...     │
├─────────────────────────────────────────┤
│ Recent                                  │
│   Model XYZ-001  ·  Singapore  ·  AMBER │
│   EMEA Summary                          │
├─────────────────────────────────────────┤
│ Results for "credit risk"               │
│   CR-Model-42   ·  India  ·  RED        │
│   CR-Model-17   ·  Japan  ·  GREEN      │
└─────────────────────────────────────────┘
```

---

## 5. Performance Best Practices

### Core Web Vitals Targets for Dashboards

| Metric | Target | What it measures |
|--------|--------|-----------------|
| LCP (Largest Contentful Paint) | < 2.5s | Time until main table/chart is visible |
| FID / INP (Interaction to Next Paint) | < 200ms | Time from cell click to navigation start |
| CLS (Cumulative Layout Shift) | < 0.1 | How much the page jumps during load |

### Table Virtualisation — Non-Negotiable for Large Lists

Never render thousands of DOM nodes. Use virtual scrolling (only render rows in the viewport).

```jsx
// Use @tanstack/react-virtual or react-window
import { useVirtualizer } from '@tanstack/react-virtual'

function ModelMetricsTable({ models }) {
  const parentRef = useRef(null)

  const virtualizer = useVirtualizer({
    count:           models.length,
    getScrollElement: () => parentRef.current,
    estimateSize:    () => 48,        // row height in px
    overscan:        10,              // extra rows rendered above/below viewport
  })

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <table style={{ height: `${virtualizer.getTotalSize()}px` }}>
        <tbody>
          {virtualizer.getVirtualItems().map(virtualRow => (
            <ModelMetricRow
              key={virtualRow.index}
              model={models[virtualRow.index]}
              style={{ transform: `translateY(${virtualRow.start}px)` }}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

### Chart Rendering — Canvas over SVG at Scale

For charts with more than 1,000 data points, use Canvas-based rendering (Chart.js, ECharts) rather than SVG-based (Recharts, Nivo). SVG creates one DOM node per data point; Canvas draws to a single bitmap.

| Data points | Use |
|-------------|-----|
| < 500 | Recharts (SVG) — easy, accessible |
| 500–5,000 | Chart.js (Canvas) |
| > 5,000 | ECharts or custom WebGL |

### API-Level Performance

**Pagination on the Regional Details table.** Never return all 500 models in one response. Use cursor-based pagination (not offset — offset has BigQuery performance problems at scale).

```graphql
query GetRegionalDetails($region: String!, $country: String, $after: String, $first: Int = 50) {
  regionalDetails(region: $region, country: $country, first: $first, after: $after) {
    edges {
      cursor
      node { ...ModelMetricRowFields }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    totalCount
  }
}
```

**Query complexity limits.** Strawberry supports query complexity limits. Prevent deeply nested queries from killing BigQuery.

```python
# main.py
schema = strawberry.Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=10),
        QueryComplexityLimiter(max_complexity=1000),
    ]
)
```

**HTTP response compression.** Enable gzip/brotli compression on FastAPI. GraphQL JSON responses can be 10x smaller compressed.

```python
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Frontend Bundle Optimisation

```javascript
// vite.config.js — code splitting per page
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react':   ['react', 'react-dom', 'react-router-dom'],
          'vendor-apollo':  ['@apollo/client', 'graphql'],
          'vendor-charts':  ['recharts', 'chart.js'],
          'vendor-table':   ['@tanstack/react-virtual', '@tanstack/react-table'],
        }
      }
    }
  }
})
```

Each page loads only its chunk. The Deep Dive page (with heavy chart libraries) does not block the Regional Summary page from loading fast.

---

## 6. Accessibility — WCAG 2.1 AA

### Why This Matters for Your Application

Enterprise dashboards used in regulated industries (banking, risk management) face accessibility audits. WCAG 2.1 AA compliance is increasingly a procurement requirement. The European Accessibility Act (EAA) enforcement began in 2025.

### Colour & Contrast

The RAG colour scheme (Red/Amber/Green) is a colour-blind accessibility problem by design.

```
Solution: Never use colour as the ONLY indicator of RAG status.
Always pair colour with: icon, label, or pattern.

❌  Bad:   <td style={{ background: '#ef4444' }}>12</td>
✅  Good:  <td className="cell-red" aria-label="12 RED models">
             <span aria-hidden="true">🔴</span> 12
           </td>
```

Minimum contrast ratios:
- Body text: 4.5:1 against background
- Large text (18px+): 3:1
- Chart lines: 3:1 against chart background
- RAG red (#ef4444) on white (#fff): ✅ passes at 4.0:1 for large text — borderline, prefer darker red
- Recommended RED: #dc2626 (contrast 4.5:1 on white) ✅

### Keyboard Navigation for Tables

Complex data tables require ARIA grid patterns.

```jsx
// Accessible data table
<table
  role="grid"
  aria-label="Model metrics for Singapore — 65 models"
  aria-rowcount={totalRows}
>
  <thead>
    <tr role="row">
      <th
        scope="col"
        role="columnheader"
        aria-sort="descending"       // when sorted
        tabIndex={0}
        onKeyDown={handleSortKey}    // Enter to sort, Space to sort
      >
        Red Count
      </th>
    </tr>
  </thead>
  <tbody>
    <tr
      role="row"
      tabIndex={0}
      aria-selected={isSelected}
      onKeyDown={(e) => {
        if (e.key === 'Enter') drillDown(row)
        if (e.key === 'ArrowDown') focusNextRow()
        if (e.key === 'ArrowUp')   focusPrevRow()
      }}
    >
      <td role="gridcell" tabIndex={-1}>
        Singapore
      </td>
      <td
        role="gridcell"
        tabIndex={-1}
        aria-label="12 RED models, click to filter"
        onClick={() => handleCellClick('red')}
        onKeyDown={(e) => e.key === 'Enter' && handleCellClick('red')}
      >
        12
      </td>
    </tr>
  </tbody>
</table>
```

### Focus Management During Navigation

When user drills from Summary → Details, focus must be managed — don't leave the user's screen reader announcing nothing.

```jsx
// pages/RegionalDetails/RegionalDetails.jsx
import { useEffect, useRef } from 'react'

function RegionalDetails() {
  const headingRef = useRef(null)

  // When this page mounts (user navigated here), move focus to the heading
  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <div>
      {/* tabIndex={-1} allows programmatic focus without tab stop */}
      <h1 ref={headingRef} tabIndex={-1}>
        Regional Details — Singapore (Total)
      </h1>
      {/* ... */}
    </div>
  )
}
```

### Chart Accessibility

Charts are inherently inaccessible to screen readers. Always provide a data table alternative.

```jsx
function MetricChart({ data, metric }) {
  return (
    <div>
      <canvas
        aria-label={`${metric} score over time for Model XYZ. Trend is deteriorating.`}
        role="img"
      />

      {/* Visually hidden but screen-reader accessible data table */}
      <details>
        <summary className="sr-only">View chart data as table</summary>
        <table>
          <caption>{metric} scores — tabular data</caption>
          <thead>
            <tr><th>Date</th><th>Score</th><th>Status</th></tr>
          </thead>
          <tbody>
            {data.map(point => (
              <tr key={point.date}>
                <td>{point.date}</td>
                <td>{point.value}</td>
                <td>{point.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

// CSS for visually hidden but screen-reader visible
// .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
```

### Accessible Toast / Notification System

Status messages (preference saved, export complete) must be announced to screen readers.

```jsx
// Use role="status" for non-urgent updates (preference saved)
// Use role="alert" for urgent updates (data load failed)

<div role="status" aria-live="polite" aria-atomic="true">
  {message && <span>{message}</span>}
</div>
```

---

## 7. Security, Compliance & Audit

### Role-Based Access Control (RBAC)

For a model risk dashboard, different users see different data and have different capabilities.

```python
# types/rbac.py

from enum import Enum

class Role(Enum):
    VIEWER        = "viewer"        # read-only, own region only
    ANALYST       = "analyst"       # read-only, all regions
    MODEL_OWNER   = "model_owner"   # can add annotations, acknowledge alerts
    RISK_MANAGER  = "risk_manager"  # all of above + export, reports
    ADMIN         = "admin"         # all of above + user management

# Permissions matrix
PERMISSIONS = {
    "view_summary":         [Role.VIEWER, Role.ANALYST, Role.MODEL_OWNER, Role.RISK_MANAGER, Role.ADMIN],
    "view_details":         [Role.VIEWER, Role.ANALYST, Role.MODEL_OWNER, Role.RISK_MANAGER, Role.ADMIN],
    "view_deep_dive":       [Role.ANALYST, Role.MODEL_OWNER, Role.RISK_MANAGER, Role.ADMIN],
    "export_data":          [Role.RISK_MANAGER, Role.ADMIN],
    "add_annotation":       [Role.MODEL_OWNER, Role.RISK_MANAGER, Role.ADMIN],
    "acknowledge_alert":    [Role.MODEL_OWNER, Role.RISK_MANAGER, Role.ADMIN],
    "manage_users":         [Role.ADMIN],
}
```

```python
# Enforce in resolvers with a decorator
def require_permission(permission: str):
    def decorator(func):
        async def wrapper(self, info: strawberry.types.Info, *args, **kwargs):
            user = info.context["user"]
            if user.role not in PERMISSIONS.get(permission, []):
                raise PermissionError(f"Role {user.role} cannot perform: {permission}")
            return await func(self, info, *args, **kwargs)
        return wrapper
    return decorator

@strawberry.field
@require_permission("export_data")
async def export_regional_details(self, info, region: str, format: str) -> ExportResult:
    ...
```

### Row-Level Security — Region Scoping

A VIEWER from APAC must not be able to see EMEA data even by modifying URL params.

```python
# services/regional_service.py
async def get_summary(region: str, user: User) -> RegionalSummary:
    # Enforce region access regardless of what region was requested
    if user.role == Role.VIEWER and region not in user.allowed_regions:
        raise PermissionError(f"Access denied to region: {region}")
    # ...
```

### Audit Trail

Every significant user action must be logged. This is non-negotiable for regulated industries.

**What to log:**
- Who (user_id, role, IP, session_id)
- What (action, resource_type, resource_id)
- When (timestamp with timezone)
- Result (success/failure, previous value, new value for writes)

```python
# models/audit_log.py

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id            = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id       = Column(String, nullable=False, index=True)
    user_role     = Column(String, nullable=False)
    session_id    = Column(String)
    ip_address    = Column(String)
    action        = Column(String, nullable=False)   # "view_deep_dive", "export_data", "add_annotation"
    resource_type = Column(String)                   # "model", "region", "preference"
    resource_id   = Column(String)                   # model_id, region name
    metadata      = Column(JSONB)                    # filters active, export format, etc.
    success       = Column(Boolean, nullable=False)
    error_message = Column(String)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), index=True)
```

```python
# middleware/audit.py — log automatically via GraphQL middleware

class AuditMiddleware:
    async def resolve(self, next, root, info, *args, **kwargs):
        user = info.context.get("user")
        start = time.time()

        try:
            result = await next(root, info, *args, **kwargs)
            await log_action(user, info.field_name, success=True, duration=time.time()-start)
            return result
        except Exception as e:
            await log_action(user, info.field_name, success=False, error=str(e))
            raise
```

**What the audit log enables:**
- Regulatory compliance — "who viewed this model's risk data on this date?"
- Security investigation — "who exported data from the RED category last week?"
- Usage analytics — "which features are actually used?" (informs roadmap)
- Debugging — "what was the user doing when this error occurred?"

### Data Export Controls

```python
# All exports are logged, watermarked, and rate-limited

@strawberry.mutation
@require_permission("export_data")
async def export_regional_details(
    self,
    info: strawberry.types.Info,
    region: str,
    format: str,   # "csv" | "xlsx" | "pdf"
) -> ExportResult:
    user = info.context["user"]

    # Rate limit: max 10 exports per hour per user
    if await export_rate_limiter.is_exceeded(user.id):
        raise RateLimitError("Export limit reached. Max 10 exports per hour.")

    # Log the export
    await audit_log.record(user, "export_data", resource_type="region", resource_id=region)

    # Generate export with watermark (user name + timestamp embedded)
    export = await export_service.generate(
        region=region,
        format=format,
        watermark=f"Exported by {user.email} on {datetime.now().isoformat()}"
    )

    return ExportResult(download_url=export.url, expires_in=300)
```

---

## 8. Development Best Practices

### Design System First

Before building any component, establish a design system. Every visual decision should be a token, not a hardcoded value.

```javascript
// src/design-system/tokens.js

export const tokens = {
  // RAG Colours — accessible versions
  color: {
    rag: {
      red:   { bg: '#fef2f2', text: '#dc2626', border: '#fca5a5' },
      amber: { bg: '#fffbeb', text: '#d97706', border: '#fcd34d' },
      green: { bg: '#f0fdf4', text: '#16a34a', border: '#86efac' },
    },
    // Never use raw hex values in components — always use tokens
    surface:   { default: '#ffffff', muted: '#f9fafb', subtle: '#f3f4f6' },
    text:      { primary: '#111827', secondary: '#6b7280', disabled: '#9ca3af' },
    border:    { default: '#e5e7eb', strong: '#d1d5db' },
  },

  // Spacing scale — consistent rhythm
  space: { 1: '4px', 2: '8px', 3: '12px', 4: '16px', 6: '24px', 8: '32px' },

  // Typography
  font: {
    size: { xs: '12px', sm: '14px', base: '16px', lg: '18px', xl: '20px' },
    mono: '"JetBrains Mono", "Fira Code", monospace',   // for metric values
  },

  // Animation
  transition: { fast: '100ms ease', base: '200ms ease', slow: '300ms ease' },
}
```

### Component API Design

Components should have clear, predictable APIs. Use the compound component pattern for complex interactive components (tables, panels).

```jsx
// Compound component pattern — flexible, composable
<DataTable data={models} onRowClick={handleDrillDown}>
  <DataTable.Column id="modelName" label="Model"   sortable />
  <DataTable.Column id="country"   label="Country" sortable />
  <DataTable.Column id="gini"      label="Gini"    sortable renderCell={GiniCell} />
  <DataTable.Column id="psi"       label="PSI"     sortable renderCell={PsiCell} />
  <DataTable.ColumnToggle />    {/* built-in show/hide panel */}
  <DataTable.Export format="csv" />
  <DataTable.Pagination pageSize={50} />
</DataTable>
```

### Error Boundaries — Per Section, Not Per Page

If a chart fails to render, the table should still work.

```jsx
// Wrap each independent section in its own error boundary
function RegionalDetails() {
  return (
    <div>
      <ErrorBoundary fallback={<TableError />}>
        <ModelMetricsTable />
      </ErrorBoundary>

      <ErrorBoundary fallback={<ChartError />}>
        <RAGDistributionChart />
      </ErrorBoundary>
    </div>
  )
}
```

### Environment Configuration

```
// .env.development
VITE_GRAPHQL_URL=http://localhost:8000/graphql
VITE_ENABLE_MOCK_DATA=true
VITE_LOG_LEVEL=debug

// .env.production
VITE_GRAPHQL_URL=https://api.yourdomain.com/graphql
VITE_ENABLE_MOCK_DATA=false
VITE_LOG_LEVEL=error
```

### Mock Service Worker — Development Without Backend

During development, use Mock Service Worker (MSW) to mock GraphQL responses. This lets frontend and backend teams work in parallel.

```javascript
// src/mocks/handlers.js
import { graphql, HttpResponse } from 'msw'

export const handlers = [
  graphql.query('GetRegionalSummary', ({ variables }) => {
    return HttpResponse.json({
      data: {
        regionalSummary: {
          region: variables.region,
          countries: mockCountries,
        }
      }
    })
  }),
]
```

---

## 9. Testing Strategy

### Testing Pyramid for a Dashboard Application

```
                    ╔════════╗
                    ║  E2E   ║    5%  — Critical user journeys only
                   ╔╬════════╬╗
                  ║ Integration ║  25%  — API contract, page-level tests
                 ╔╬══════════════╬╗
                ║    Unit Tests    ║  70%  — Components, hooks, services
               ╚══════════════════╝
```

### Unit Tests — Components and Hooks

```javascript
// src/components/CountryRow/CountryRow.test.jsx
import { render, screen, userEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CountryRow from './CountryRow'

const mockCountry = {
  countryId: 'SG',
  countryName: 'Singapore',
  modelCounts: { red: 12, amber: 8, green: 45, total: 65 }
}

test('displays all RAG counts', () => {
  render(<MemoryRouter><CountryRow country={mockCountry} /></MemoryRouter>)
  expect(screen.getByText('12')).toBeInTheDocument()  // RED count
  expect(screen.getByText('8')).toBeInTheDocument()   // AMBER count
  expect(screen.getByText('45')).toBeInTheDocument()  // GREEN count
})

test('navigates to regional details on RED cell click', async () => {
  const { container } = render(
    <MemoryRouter initialEntries={['/regional-summary?region=APAC']}>
      <CountryRow country={mockCountry} />
    </MemoryRouter>
  )
  await userEvent.click(screen.getByLabelText('12 RED models, click to filter'))
  // Assert navigation happened with correct URL params
  expect(window.location.search).toContain('country=SG')
  expect(window.location.search).toContain('status=red')
})

test('RED cell has accessible aria-label', () => {
  render(<MemoryRouter><CountryRow country={mockCountry} /></MemoryRouter>)
  expect(screen.getByLabelText(/12 RED models/)).toBeInTheDocument()
})
```

```javascript
// src/hooks/usePreference.test.js
import { renderHook, act } from '@testing-library/react'
import { usePreference } from './usePreference'

test('returns default value when no preference is saved', () => {
  const { result } = renderHook(() =>
    usePreference('test:key', { visible: ['col1', 'col2'] })
  )
  expect(result.current.value).toEqual({ visible: ['col1', 'col2'] })
})

test('saves to localStorage immediately on change', () => {
  const { result } = renderHook(() =>
    usePreference('test:key', {})
  )
  act(() => result.current.save({ visible: ['col1'] }))
  expect(JSON.parse(localStorage.getItem('dashboard:pref:test:key')))
    .toEqual({ visible: ['col1'] })
})
```

### Integration Tests — GraphQL Resolvers

```python
# tests/test_regional_resolver.py
import pytest
from strawberry.test import TestClient
from main import schema

@pytest.mark.asyncio
async def test_regional_summary_returns_countries(test_db, test_redis):
    client = TestClient(schema)
    result = await client.query(
        """
        query { regionalSummary(region: "APAC") {
          region
          countries { countryId countryName modelCounts { red amber green total } }
        }}
        """
    )
    assert result.errors is None
    assert result.data["regionalSummary"]["region"] == "APAC"
    assert len(result.data["regionalSummary"]["countries"]) > 0

@pytest.mark.asyncio
async def test_region_access_denied_for_wrong_role(test_db):
    # VIEWER for APAC cannot see EMEA
    client = TestClient(schema, context_value={"user": viewer_apac_user})
    result = await client.query('query { regionalSummary(region: "EMEA") { region } }')
    assert "Access denied" in str(result.errors)
```

### E2E Tests — Critical Journeys

```javascript
// tests/e2e/drill-down.spec.js  (Playwright)
test('full drill-down journey: Summary → Details → Deep Dive → Back', async ({ page }) => {
  await page.goto('/regional-summary?region=APAC')

  // Verify summary loads
  await expect(page.getByText('Singapore')).toBeVisible()

  // Click Singapore's RED cell
  await page.getByRole('gridcell', { name: /12 RED models/ }).click()

  // Should navigate to Regional Details with filters applied
  await expect(page).toHaveURL(/country=SG.*status=red|status=red.*country=SG/)
  await expect(page.getByRole('heading', { name: /Singapore/ })).toBeVisible()

  // Click a Gini cell
  await page.getByRole('gridcell', { name: /Gini.*AMBER/ }).first().click()

  // Should navigate to Deep Dive
  await expect(page).toHaveURL(/deep-dive.*metric=gini/)
  await expect(page.getByText('Gini History')).toBeVisible()

  // Press Escape to go back
  await page.keyboard.press('Escape')
  await expect(page).toHaveURL(/regional-details/)
})

test('breadcrumb navigation works correctly', async ({ page }) => {
  await page.goto('/deep-dive?region=APAC&country=SG&status=red&modelId=m001&metric=gini')

  // Click "APAC" breadcrumb
  await page.getByRole('link', { name: 'APAC' }).click()
  await expect(page).toHaveURL('/regional-summary?region=APAC')
})
```

### Visual Regression Testing

Use Chromatic (Storybook) or Percy to catch unintended visual changes.

```javascript
// CountryRow.stories.jsx
export const WithRedModels = {
  args: {
    country: { countryId: 'SG', countryName: 'Singapore',
               modelCounts: { red: 12, amber: 8, green: 45, total: 65 } }
  }
}

export const AllGreen = {
  args: {
    country: { countryId: 'SG', countryName: 'Singapore',
               modelCounts: { red: 0, amber: 0, green: 65, total: 65 } }
  }
}

export const EmptyRegion = {
  args: {
    country: { countryId: 'SG', countryName: 'Singapore',
               modelCounts: { red: 0, amber: 0, green: 0, total: 0 } }
  }
}
```

---

## 10. Feature Roadmap — Phased

### Phase 0 — Foundation (Weeks 1–4)
*Get the core architecture right before adding features.*

**Architecture**
- [ ] Layered backend (Resolver → Service → Repository)
- [ ] DataLoader registry — zero N+1 queries
- [ ] URL-as-filter-state (useFilterState hook)
- [ ] Apollo normalized cache with type policies
- [ ] User preferences persistence (3-layer: localStorage → Redis → PostgreSQL)
- [ ] graphql-codegen running in watch mode
- [ ] RBAC + row-level region security
- [ ] Audit log middleware

**Core UI**
- [ ] Design system tokens (colour, spacing, typography)
- [ ] RAG-aware table with colour + icon (not colour alone)
- [ ] Skeleton loading screens (no spinners, no layout shift)
- [ ] Empty states for all data scenarios
- [ ] Error boundaries per section
- [ ] Basic breadcrumb navigation
- [ ] Active filter chips with remove

**Data**
- [ ] "Data as of [timestamp]" on every page
- [ ] Data staleness warning banner
- [ ] ETL cache invalidation webhook endpoint

---

### Phase 1 — Core Features (Weeks 5–8)

**Navigation & Filtering**
- [ ] Global region switcher in nav bar
- [ ] Drill-down: Summary → Details → Deep Dive
- [ ] Back navigation with preserved filter state
- [ ] Column show/hide in all tables (with preference persistence)
- [ ] Column sort (all columns, multi-column sort)

**Visualisation**
- [ ] RAG counts with delta vs. previous run (▲▼)
- [ ] Row-level 7-day sparklines on summary table
- [ ] Time-series chart with threshold line on Deep Dive
- [ ] Hover tooltips with metric definition, threshold, and previous value
- [ ] Colour area under chart line by RAG status

**Performance**
- [ ] Virtual scrolling for tables > 100 rows
- [ ] Cursor-based pagination on all list queries
- [ ] Response compression (gzip)
- [ ] Code splitting per route

**Accessibility**
- [ ] ARIA grid roles on all tables
- [ ] Focus management on page navigation
- [ ] All interactive elements keyboard accessible
- [ ] Screen reader alternative for all charts (data table in `<details>`)
- [ ] 4.5:1 contrast ratio verified on all text
- [ ] Visible focus indicators on all interactive elements

---

### Phase 2 — Power Features (Weeks 9–14)

**Advanced Filtering & Search**
- [ ] Ctrl+K command palette — search models by name, ID, country
- [ ] Multi-select filter (select multiple countries at once)
- [ ] Date range picker — compare current run vs. any historical run
- [ ] Metric range filter (e.g., Gini between 0.25 and 0.35)
- [ ] Saved views — save + name a URL + filter combination

**Annotations & Collaboration**
- [ ] Row-level annotations — add a note to a model (e.g., "PSI spike due to Q3 refresh")
- [ ] Annotation history — see all notes on a model over time
- [ ] @mention team members in annotations (triggers notification)
- [ ] Annotation visibility: private / team / all

**Alerting**
- [ ] Per-model alert subscriptions — notify me when Model XYZ goes RED
- [ ] Per-region alert subscriptions — notify me when APAC RED count exceeds 20
- [ ] Alert channels: in-app notification, email, Slack webhook
- [ ] Alert history log — "this model has been RED for 3 consecutive runs"
- [ ] Alert suppression — snooze an alert for a defined period

**Export & Reporting**
- [ ] Export current table view to CSV (respects all active filters)
- [ ] Export chart to PNG/SVG
- [ ] Scheduled report — email a PDF snapshot on a schedule (weekly, monthly)
- [ ] Share view — generate a shareable link with a point-in-time snapshot
- [ ] Print-optimised CSS for all pages

**Chart Configuration**
- [ ] User-configurable axis selection on all charts
- [ ] User-configurable chart type (line / bar / area)
- [ ] User-configurable colour scheme
- [ ] Chart annotation — click to mark a point in the history ("Model retrained")
- [ ] Chart comparison — overlay two models on the same chart

---

### Phase 3 — Enterprise Features (Weeks 15–24)

**Advanced Analytics**
- [ ] Trend analysis — "at current rate, how many models will breach in 30 days?"
- [ ] Cohort comparison — models by vintage, segment, geography
- [ ] Benchmark overlay — compare model metrics against regional or global average
- [ ] Correlation view — scatter plot of Gini vs PSI across all models
- [ ] Distribution histogram — score distribution across all models

**Workflow & Governance**
- [ ] Model acknowledgement — risk manager formally acknowledges a RED model with notes
- [ ] Acknowledgement workflow — requires two-level sign-off for HIGH materiality models
- [ ] Audit trail viewer — searchable log of all user actions (Datadog-style)
- [ ] Dashboard version history — restore a previous layout
- [ ] Model metadata panel — link to model documentation, owner, last validation date

**Administration**
- [ ] User management UI — invite users, assign roles, assign region access
- [ ] SSO integration (SAML, OIDC)
- [ ] Session management — active sessions, force logout
- [ ] Data access log — per-user report of what data was accessed

**Customisation**
- [ ] Custom layout builder — users arrange panels (Grafana-style)
- [ ] Custom metric thresholds per model — override global RED/AMBER boundaries
- [ ] Custom dashboard per role — risk manager sees different default view than analyst
- [ ] Embeddable widgets — embed a single panel in another internal tool (iframe with JWT auth)

**Notifications Hub**
- [ ] Unified notification centre — all alerts, annotations, workflow events in one place
- [ ] Notification preferences — per-type, per-channel settings
- [ ] Digest mode — batch notifications into a daily or weekly summary email

---

### Phase 4 — AI-Assisted Features (Post Week 24)

- [ ] Natural language query — "show me all models in APAC that deteriorated in Q1"
- [ ] Automated insight generation — "PSI for Credit Models in Singapore is trending up, driven by 3 models"
- [ ] Anomaly detection — surface unexpected metric movements without user setting a threshold
- [ ] Recommended actions — "Model XYZ has been AMBER for 6 runs. Consider escalating."

---

## 11. Application Management

### Feature Flag Strategy

Never deploy all features at once. Use feature flags to release progressively.

```javascript
// src/config/features.js
export const features = {
  COMMAND_PALETTE:        import.meta.env.VITE_FF_COMMAND_PALETTE === 'true',
  SAVED_VIEWS:            import.meta.env.VITE_FF_SAVED_VIEWS     === 'true',
  ANNOTATIONS:            import.meta.env.VITE_FF_ANNOTATIONS      === 'true',
  ALERTING:               import.meta.env.VITE_FF_ALERTING         === 'true',
  EXPORT:                 import.meta.env.VITE_FF_EXPORT           === 'true',
}

// Usage in component
import { features } from '../../config/features'

{features.ANNOTATIONS && <AnnotationPanel modelId={model.modelId} />}
```

### Monitoring — What to Track in Production

**Frontend (Real User Monitoring)**
- Page load time per route (target: LCP < 2.5s)
- Drill-down interaction latency (click → navigation complete, target: < 200ms)
- GraphQL query durations from the client
- JavaScript error rate by component
- Feature usage heatmap (which columns are hidden most often — informs defaults)

**Backend**
- GraphQL resolver latency per field (p50, p95, p99)
- DataLoader batch sizes (are batches actually working?)
- Redis cache hit rate per key pattern (target: > 80% for summary queries)
- BigQuery query duration (alert if > 10s)
- ETL pipeline success/failure (alert if latest run is > 2× expected cadence old)

**Business**
- Most-viewed regions and countries
- Most-used filters and drill-down paths
- Export frequency by user role
- Alert subscription counts
- Annotation creation rate (measures engagement)

### Dependency Management

```json
// package.json — pin minor versions, allow patch updates
{
  "dependencies": {
    "@apollo/client":     "^3.9.0",
    "react":              "^18.3.0",
    "react-router-dom":   "^6.24.0",
    "recharts":           "^2.12.0"
  }
}
```

Run `npm audit` in CI. Fail the build on high-severity vulnerabilities. Update dependencies on a scheduled sprint task (monthly), not ad-hoc.

### Database Migration Strategy

```
migrations/
  0001_create_user_preferences.sql
  0002_create_audit_logs.sql
  0003_create_annotations.sql
  0004_create_alert_subscriptions.sql
  0005_create_saved_views.sql
```

Never run migrations manually. Use Alembic (Python) with automatic rollback on failure.

```python
# alembic/env.py
# All migrations are versioned, reversible, and run in CI before deployment
```

---

## Summary — Priority Matrix

| Quadrant | Features |
|----------|----------|
| **Do first** (high impact, low effort) | Skeleton loaders · Delta indicators · Breadcrumbs · Filter chips · Data freshness timestamp · Column sort · Accessible RAG colours |
| **Do next** (high impact, higher effort) | Column show/hide persistence · Cursor pagination · Virtual scrolling · Saved views · CSV export · Keyboard shortcuts |
| **Plan carefully** (high value, complex) | Annotation system · Alerting engine · Scheduled reports · Acknowledgement workflow · SSO |
| **Validate demand first** (uncertain value) | Custom layout builder · Natural language query · Embeddable widgets · AI insights |

---

## Cross-Reference — Related Architecture Documents

| Topic | Document |
|-------|---------|
| API patterns, DataLoader, GraphQL schema | `dashboard-architecture-guide.md` |
| User preference persistence (columns, charts) | `user-preferences-architecture.md` |
| This document (features, UX, roadmap) | `dashboard-best-practices-roadmap.md` |
