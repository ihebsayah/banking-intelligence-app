# Dashboard Philosophy

## Design Principles

### 1. Executive Workspace
The dashboard is a workspace, not a showcase. Every element must answer: "Does this help the user make a decision or take action?"

### 2. Progressive Disclosure
- **Level 1**: 4 executive summary cards (always visible)
- **Level 2**: KPI cards (role-dependent)
- **Level 3**: Charts (2-column grid)
- **Level 4**: Recent activity table

Users scan top-to-bottom. Most important info is at the top.

### 3. Data Density Over White Space
Bankers prefer information density. Cards are compact (88px height for summary cards). Charts use full width. No decorative whitespace.

### 4. Real-Time Refresh
- Auto-refresh capability via manual button
- Last refreshed timestamp visible
- Loading states for each section independently
- Graceful degradation when API is unavailable

## Layout Structure

```
┌─────────────────────────────────────────────┐
│ BankingHeader (title, refresh, timestamp)   │
├─────────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│ │Total │ │Active│ │ 30D  │ │High  │       │
│ │Port. │ │Acc.  │ │Trans.│ │Risk  │       │
│ └──────┘ └──────┘ └──────┘ └──────┘       │
├─────────────────────────────────────────────┤
│ Financial Intelligence Indexes (KPI Cards)  │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│ │  KPI │ │  KPI │ │  KPI │ │  KPI │       │
│ └──────┘ └──────┘ └──────┘ └──────┘       │
├─────────────────────────────────────────────┤
│ ┌─────────────────┐ ┌─────────────────┐    │
│ │ Revenue Trend   │ │ Growth Rate     │    │
│ │ (Line Chart)    │ │ (Area Chart)    │    │
│ └─────────────────┘ └─────────────────┘    │
│ ┌─────────────────┐ ┌─────────────────┐    │
│ │ Concentration   │ │ Risk Dist.      │    │
│ │ (Bar Chart)     │ │ (Pie Chart)     │    │
│ └─────────────────┘ └─────────────────┘    │
├─────────────────────────────────────────────┤
│ Recent Activity (Table)                     │
│ TX ID | Customer | Desc | Type | Amount    │
│ ...     ...        ...    ...    ...        │
└─────────────────────────────────────────────┘
```

## Color Coding

### Values
- **Positive values**: `var(--accent-green)` (revenue, deposits, growth)
- **Negative values**: `var(--accent-red)` (withdrawals, risk, losses)
- **Neutral values**: `var(--text-primary)` (counts, IDs)

### Status Indicators
- **Success/Active**: Green badge
- **Warning/Pending**: Amber badge
- **Error/Suspended**: Red badge
- **Info/Neutral**: Blue badge

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
