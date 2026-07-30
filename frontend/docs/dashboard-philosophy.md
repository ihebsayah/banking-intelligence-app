# Dashboard Philosophy

## Design Principles

### 1. Executive Workspace
The dashboard is a workspace, not a showcase. Every section must answer: "What decision does this help the user make?"

### 2. Progressive Disclosure
```
Morning Brief       → "What happened overnight?"
Critical Alerts     → "What needs my attention NOW?"
AI Executive Summary → "What does the data say?"
KPIs                → "How are we tracking?"
Charts              → "What are the trends?"
Operational Tables  → "Where are the details?"
Recent Activity     → "What changed recently?"
```

Users scan top-to-bottom. Most urgent/time-sensitive info is at the top.

### 3. Data Density Over White Space
Bankers prefer information density. Cards are compact (88px height for summary cards). Charts use full width. No decorative whitespace.

### 4. Real-Time Refresh
- Manual refresh button with spinner
- Last refreshed timestamp visible
- Loading states for each section independently
- Graceful degradation when API is unavailable (service unavailable card with endpoint details)

## Layout Structure

```
┌─────────────────────────────────────────────┐
│ BankingHeader (title, refresh, timestamp)   │
├─────────────────────────────────────────────┤
│ Morning Brief (2-3 highlight metrics)       │
├─────────────────────────────────────────────┤
│ Critical Alerts (0-3 urgent items)          │
├─────────────────────────────────────────────┤
│ AI Executive Summary (AI workspace)         │
├─────────────────────────────────────────────┤
│ Financial Intelligence Indexes (KPI Cards)  │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│ └──────┘ └──────┘ └──────┘ └──────┘       │
├─────────────────────────────────────────────┤
│ Charts (2-column grid)                      │
│ ┌─────────────────┐ ┌─────────────────┐    │
│ └─────────────────┘ └─────────────────┘    │
│ ┌─────────────────┐ ┌─────────────────┐    │
│ └─────────────────┘ └─────────────────┘    │
├─────────────────────────────────────────────┤
│ Operational Tables                          │
├─────────────────────────────────────────────┤
│ Recent Activity (compact table)             │
└─────────────────────────────────────────────┘
```

## Sections

### Morning Brief
3 compact cards showing: total portfolios, active accounts, 30D transactions. These are the first thing a banker checks each day.

### Critical Alerts
0-3 dismissable alert cards for: risk threshold breaches, compliance violations, system errors. Red/amber only. If no alerts, this section is hidden.

### AI Executive Summary
Inline AI assistant card showing: "Your AI Brief" — 2-3 sentence natural language summary of the day's key metrics and changes. Click "Ask AI" to open the full AI workspace panel.

### KPIs
Role-dependent financial intelligence indexes. Shown as compact cards with trend indicators.

### Charts
4 charts in 2-column grid. Revenue Trend (line), Growth Rate (area), Concentration (bar), Risk Distribution (pie).

### Operational Tables
Branch-level and portfolio-level tables with sortable columns.

### Recent Activity
Compact transaction log. TX ID | Customer | Description | Type | Amount | Status | Timestamp.

## Empty States

When data is unavailable:
1. Show skeleton loaders during initial load
2. Show "No data available" with dashed border when confirmed empty
3. Show service unavailable card with endpoint details when API fails
4. Always provide a retry mechanism

## Responsive Behavior

- **Desktop (>1280px)**: 4-column grid for summary, 2-column for charts
- **Tablet (768-1280px)**: 2-column for summary, 1-column for charts
- **Mobile (<768px)**: Single column, summary cards stack vertically
