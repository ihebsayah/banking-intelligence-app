# AI Assistant Experience

## Overview

Global AI workspace accessible from any page via the TopBar or command palette. Designed as GitHub Copilot for banking data — not a chat page, but an intelligent workspace embedded in the application.

## Access Points

1. **TopBar button**: Click the AI icon in the top-right
2. **Command palette**: "Toggle AI Assistant" action

## Layout

- **Position**: Fixed right side panel
- **Width**: 400px
- **Height**: Full viewport height
- **Animation**: 200ms slide-in from right
- **Overlay**: None — panel overlaps content

## Capabilities

### Chat
Natural language query interface for banking data. Ask about portfolios, transactions, risk, compliance, revenue.

### Insights
AI responses include structured insights: record count, execution time, data source, and freshness metadata.

### Explain This Chart (future)
Select any chart on the page and ask the AI to explain what it shows. Copilot-like context awareness.

### Suggested Actions (future)
After each query, the AI suggests follow-up actions: "View details", "Export to CSV", "Compare with last quarter".

### Conversation History (future)
Session-based history. Past queries survive page navigation but not browser close (no persistence layer yet).

### Context Awareness (future)
The AI panel knows which page you're on and can tailor responses: "Showing risk page — would you like to drill into high-risk branches?"

## Implementation

### State
```typescript
// uiStore.ts
aiPanelOpen: boolean
setAiPanelOpen: (open: boolean) => void
```

### Messages
```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  result?: QueryResult;
  isLoading?: boolean;
  isError?: boolean;
}
```

### API
```
POST /api/query
{ query: string, role: string }
→ { answer, row_count, execution_time_ms, source, data_freshness, insights }
```

### Message Display
- User: Right-aligned, `var(--accent-blue)` background, white text
- AI: Left-aligned, `var(--bg-card)` background, `var(--text-secondary)` text
- Loading: Pulsing dots animation
- Error: `var(--accent-red)` text with retry message
- Result footer: Row count | Source | Freshness in monospace text

## Query Examples

- "What is the total portfolio value?"
- "Show me high-risk branches"
- "Compare Q1 vs Q2 revenue"
- "List transactions over 1M TND"
- "What compliance issues are pending?"

## Design Principles

1. **Copilot, not ChatGPT**: AI is an active workspace tool, not a standalone chatbot
2. **Non-blocking**: Panel doesn't prevent interaction with main content
3. **Context-aware**: Knows which page you're on (future)
4. **Persistent**: Message history survives page navigation within session
5. **Accessible**: Keyboard navigable, screen reader friendly
