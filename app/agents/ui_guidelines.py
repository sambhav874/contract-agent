"""
Generative UI design guidelines for the Contract Guardian AI.

Contains:
- Core design system (colors, typography, layout)
- Premium styling patterns (glassmorphism, micro-animations)
- Data-viz templates (KPI scorecard, breach timeline, etc.)
- Chart.js patterns with data-binding rules
- SVG diagram patterns
"""

# ── Core Design System ────────────────────────────────────────────────

CORE_DESIGN_SYSTEM = """## Core Design System

### Philosophy
- **Seamless**: widget should feel native to the chat, not a foreign embed.
- **Flat-premium**: no heavy shadows or neon. Use subtle borders, gentle gradients, and soft glassmorphism.
- **Warm minimal**: clean geometric layouts with soft rounded corners (rx=12). Warm neutrals (slate tones) with indigo as primary accent.
- **Data-Grounded**: NEVER use simulated, placeholder, or dummy data. Use ONLY values from the STRUCTURED DATA block. If data is missing, explain the gap — do NOT fabricate.
- **Text outside, visuals inside** — explanatory text OUTSIDE the code fence.

### When NOT to generate UI
- Simple factual Q&A ("What are the payment terms?") → just answer in markdown
- Contract clause lookups → cite and quote the clause
- Definitions or explanations → prose is better than a chart
- If the STRUCTURED DATA block is empty or has <3 data points → explain why a chart can't be built

### When TO generate UI
- Performance dashboards with multiple KPIs
- Target vs Actual comparisons across metrics
- Trend analysis over time (if time-series data exists)
- Penalty/financial impact breakdowns
- Contract structure diagrams or process flows

### Streaming-safe rendering
- **HTML**: `<style>` (short) → content → `<script>` last.
- **SVG**: `<defs>` first → visual elements immediately.
- Solid fills only — gradients/shadows flash during DOM diffs.

### Rules
- No comments, no emoji, no position:fixed, no iframes
- No font-size below 11px
- No dark/colored backgrounds on outer containers
- Typography: weights 400/500/600/700 only, sentence case
- CDN allowlist: `cdnjs.cloudflare.com`, `esm.sh`, `cdn.jsdelivr.net`, `unpkg.com`
- ALWAYS load Inter font: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">`
"""

# ── Premium Styling ───────────────────────────────────────────────────

PREMIUM_STYLING = """## Premium Styling System

### CSS Variables (REQUIRED in every HTML widget)
```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f8fafc;
  --bg-tertiary: #f1f5f9;
  --bg-card: rgba(255,255,255,0.85);
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-tertiary: #94a3b8;
  --border-light: #f1f5f9;
  --border-default: #e2e8f0;
  --indigo-50: #eef2ff; --indigo-100: #e0e7ff; --indigo-400: #818cf8; --indigo-500: #6366f1; --indigo-600: #4f46e5; --indigo-700: #4338ca;
  --emerald-50: #ecfdf5; --emerald-400: #34d399; --emerald-500: #10b981; --emerald-600: #059669;
  --amber-50: #fffbeb; --amber-400: #fbbf24; --amber-500: #f59e0b; --amber-600: #d97706;
  --rose-50: #fff1f2; --rose-400: #fb7185; --rose-500: #f43f5e; --rose-600: #e11d48;
  --sky-50: #f0f9ff; --sky-400: #38bdf8; --sky-500: #0ea5e9;
  --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px; --radius-xl: 20px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.08);
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', ui-monospace, monospace;
}
```

### Glassmorphism Card Pattern
```css
.card {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  border: 0.5px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  transition: box-shadow 0.2s, transform 0.2s;
}
.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
```

### Micro-animations (subtle, performant)
```css
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes countUp {
  from { opacity: 0; transform: scale(0.8); }
  to { opacity: 1; transform: scale(1); }
}
.animate-in { animation: fadeInUp 0.4s ease-out both; }
.stat-value { animation: countUp 0.5s cubic-bezier(0.16,1,0.3,1) both; }
```

### Stat Card Pattern (for KPI metrics)
```html
<div class="card animate-in" style="animation-delay: 0.1s">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
    <div style="width:8px;height:8px;border-radius:50%;background:var(--emerald-500)"></div>
    <span style="font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em">KPI Label</span>
  </div>
  <div style="font-size:28px;font-weight:700;color:var(--text-primary);line-height:1" class="stat-value">94.2%</div>
  <div style="display:flex;align-items:center;gap:6px;margin-top:8px">
    <span style="font-size:11px;font-weight:500;color:var(--text-tertiary)">Target: ≥95%</span>
    <span style="font-size:10px;font-weight:600;padding:2px 6px;border-radius:4px;background:var(--rose-50);color:var(--rose-600)">-0.8% below</span>
  </div>
</div>
```

### Severity Color Coding (ALWAYS use these)
- **On Track / OK**: emerald-500 (#10b981) fill, emerald-50 background
- **Warning / Medium**: amber-500 (#f59e0b) fill, amber-50 background
- **Breach / High**: rose-500 (#f43f5e) fill, rose-50 background  
- **Critical**: rose-600 (#e11d48) fill, rose-50 background with rose-200 border
- **Neutral / Info**: indigo-500 (#6366f1) fill, indigo-50 background
"""

# ── Color Palette ─────────────────────────────────────────────────────

COLOR_PALETTE = """## Color Palette (for Chart.js)

| Ramp | 50 (fill bg) | 200 (stroke) | 400 (accent) | 600 (subtitle) | 800 (title) |
|------|-------------|-------------|-------------|----------------|-------------|
| Indigo | #EEF2FF | #C7D2FE | #818CF8 | #4F46E5 | #3730A3 |
| Emerald | #ECFDF5 | #A7F3D0 | #34D399 | #059669 | #065F46 |
| Amber | #FFFBEB | #FDE68A | #FBBF24 | #D97706 | #92400E |
| Slate | #F8FAFC | #E2E8F0 | #94A3B8 | #64748B | #334155 |
| Rose | #FFF1F2 | #FECDD3 | #FB7185 | #E11D48 | #9F1239 |
| Sky | #F0F9FF | #BAE6FD | #38BDF8 | #0284C7 | #075985 |

- Chart.js: use 400 for borderColor, 400 with 0.15 alpha for backgroundColor
- Target/threshold lines: Slate-400 with dashed stroke
- On-track data: Emerald-400; breach data: Rose-400; pending: Amber-400
"""

# ── Chart.js Patterns ─────────────────────────────────────────────────

CHARTS_CHART_JS = """## Charts (Chart.js 4.x)

### Setup Pattern (REQUIRED for every chart)
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<div style="position:relative;width:100%;max-width:700px;margin:0 auto;font-family:'Inter',sans-serif">
  <!-- Stat cards grid ABOVE the chart -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px">
    <!-- Stat cards here -->
  </div>
  <!-- Chart container -->
  <div style="background:var(--bg-card,#fff);border:0.5px solid #e2e8f0;border-radius:14px;padding:20px;box-shadow:0 1px 2px rgba(0,0,0,0.04)">
    <div style="font-size:14px;font-weight:600;color:#0f172a;margin-bottom:4px">Chart Title</div>
    <div style="font-size:11px;color:#94a3b8;margin-bottom:16px">Subtitle with data context</div>
    <div style="position:relative;height:280px"><canvas id="c1"></canvas></div>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js" onload="init()"></script>
```

### Chart.js Configuration Rules
- Canvas CANNOT use CSS variables — use hex from color ramps
- Height on wrapper div only. responsive:true, maintainAspectRatio:false
- Always set `plugins.legend.labels.font.family` to `'Inter'`
- borderRadius:6 for bars, tension:0.3 for smooth lines, pointRadius:0 for clean lines
- Grid: only horizontal, color `rgba(0,0,0,0.04)`, no border
- Multiple charts: unique canvas IDs (c1, c2, c3...)
- ALWAYS call chart.update() after any data modification

### Target vs Actual Pattern (most common use case)
```js
datasets: [
  {
    label: 'Target',
    data: [95, 95, 95, 95, 95],  // FROM STRUCTURED DATA
    borderColor: '#94A3B8',
    borderDash: [6, 4],
    borderWidth: 1.5,
    pointRadius: 0,
    fill: false
  },
  {
    label: 'Actual',
    data: [97, 93, 91, 94, 96],  // FROM STRUCTURED DATA
    borderColor: '#818CF8',
    backgroundColor: 'rgba(129,140,248,0.12)',
    borderWidth: 2,
    pointRadius: 3,
    pointBackgroundColor: '#818CF8',
    fill: true,
    tension: 0.3
  }
]
```

### Penalty Waterfall (horizontal bar)
```js
{
  type: 'bar',
  data: {
    labels: kpiNames,          // FROM STRUCTURED DATA
    datasets: [{
      data: penaltyAmounts,    // FROM STRUCTURED DATA
      backgroundColor: penaltyAmounts.map(v => v > 5000 ? '#fb7185' : v > 1000 ? '#fbbf24' : '#94a3b8'),
      borderRadius: 4,
      barThickness: 18
    }]
  },
  options: {
    indexAxis: 'y',
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { family: 'Inter' }, callback: v => '$' + v.toLocaleString() } },
      y: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 } } }
    }
  }
}
```
"""

# ── Data Binding Rules ────────────────────────────────────────────────

DATA_BINDING_RULES = """## Data Binding Rules (CRITICAL)

When generating charts or dashboards, you receive a `STRUCTURED DATA` block with real KPI, breach, and performance data.

### Rules
1. **ONLY use values from STRUCTURED DATA** — never invent numbers, dates, or percentages
2. For KPI scorecards: use `kpis[].name`, `kpis[].value_min`, `kpis[].unit`, `kpis[].operator` for targets
3. For breach data: use `breaches[].actual_value`, `breaches[].threshold_value`, `breaches[].penalty_amount`, `breaches[].is_breach`
4. For performance trends: use `actuals[]` with their timestamps and values
5. If a KPI has no corresponding breach or actual data, show it as "No data" with a gray indicator — do NOT fabricate a value
6. Show the data source count: "Based on N performance records" in a footer
7. Round all numbers: percentages to 1 decimal, currency to whole numbers
8. Always show units alongside values

### Stat Card Data Mapping
For each KPI in the structured data:
- **Label**: `kpi.name`
- **Value**: Use the latest `actual.value` for that kpi_id, or "Pending" if no actuals
- **Target**: `kpi.operator` + `kpi.value_min` + `kpi.unit`
- **Status dot**: green if actual meets target, rose if breach, amber if within 5% of threshold
- **Delta**: calculate `actual - target` and show as "+X.X above" or "-X.X below"

### Chart Data Mapping
- **X-axis labels**: Use actual dates from `actuals[].timestamp` (format: "MMM DD")
- **Y-axis data**: Use actual values from `actuals[].value`
- **Threshold line**: Horizontal line at `kpi.value_min` with dashed Slate-400 stroke
- **Data points**: Color code — emerald if above threshold, rose if below
"""

# ── SVG Diagram Patterns ─────────────────────────────────────────────

SVG_PATTERNS = """## SVG Diagrams

`<svg width="100%" viewBox="0 0 680 H">` — 680px fixed width. Adjust H to fit content + 40px buffer.

### Arrow marker (required):
`<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#64748B" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>`

### Style
- Inline font styles with 'Inter', system-ui fallback
- 13-14px labels, 11-12px subtitles
- Stroke 0.5-1px borders, 1.5px arrows
- rx=10-14 for nodes
- Use Indigo-50 fill + Indigo-200 stroke for primary nodes
- Use Emerald-50 for "success" nodes, Rose-50 for "breach/alert" nodes

### Diagram Types
1. **Flowchart** — ≤4 nodes per row, left→right or top→bottom
2. **Timeline** — Horizontal axis with event markers, stagger labels above/below
3. **Hierarchy** — Root at top, children below, vertical arrows
4. **Penalty Escalation** — Stepped flow showing breach → trigger → penalty → remediation

### Rules
- ≤4 nodes per row, ≤5 words per title
- Node width ≥ (chars × 8 + 40) px
- 2-3 color ramps max, Slate for structural
- Verify no arrow crosses unrelated boxes
"""

# ── Assembled Guidelines ──────────────────────────────────────────────

# Full guidelines — only injected when the intent classifier says DATA_VIZ or DIAGRAM
FULL_GUIDELINES = f"""
{CORE_DESIGN_SYSTEM}

{PREMIUM_STYLING}

{COLOR_PALETTE}

{CHARTS_CHART_JS}

{DATA_BINDING_RULES}

{SVG_PATTERNS}
"""

# Compact guidelines — for DATA_VIZ mode (no SVG section)
DATA_VIZ_GUIDELINES = f"""
{CORE_DESIGN_SYSTEM}

{PREMIUM_STYLING}

{COLOR_PALETTE}

{CHARTS_CHART_JS}

{DATA_BINDING_RULES}
"""

# Diagram-only guidelines — for DIAGRAM mode (no Chart.js section)
DIAGRAM_GUIDELINES = f"""
{CORE_DESIGN_SYSTEM}

{PREMIUM_STYLING}

{COLOR_PALETTE}

{SVG_PATTERNS}
"""
