# AI Assistant Experience

## Overview

Global AI assistant accessible from any page via the TopBar or keyboard shortcut. Provides natural language query interface to the banking data.

## Access Points

1. **TopBar button**: Click the AI icon in the top-right
2. **Command palette**: "Toggle AI Assistant" action
3. **Keyboard shortcut**: Configurable (default: none to avoid conflicts)

## Layout

- **Position**: Fixed right side panel
- **Width**: 400px
- **Height**: Full viewport height
- **Animation**: 200ms slide-in from right
- **Overlay**: None — panel pushes content or overlaps

## Components

### Header
- Title: "AI Assistant"
- Subtitle: "Ask questions about your banking data"
- Close button (×)

### Message Area
- Scrollable message list
- User messages: Right-aligned, `var(--accent-blue)` background
- AI responses: Left-aligned, `var(--bg-card)` background
- Loading state: Pulsing dots animation

### Input Area
- Textarea (auto-expanding, max 120px)
- Placeholder: "Ask about portfolio, transactions, risk..."
- Send button (arrow icon)
- Enter to send, Shift+Enter for newline

## Integration

### API
Uses `queryApi.submitQuery()` from `src/api/dashboard.ts`:
```typescript
const response = await queryApi.submitQuery({
  query: userMessage,
  query_type: 'nl'
})
```

### Response Handling
- Success: Display `response.answer` in message list
- Error: Display error message with retry option
- Loading: Show pulsing dots while waiting

## Message Format

### User Message
```tsx
<div className="flex justify-end">
  <div className="rounded-xl px-4 py-2.5 text-sm max-w-[85%]"
    style={{ background: 'var(--accent-blue)', color: 'white' }}>
    {message}
  </div>
</div>
```

### AI Response
```tsx
<div className="flex justify-start">
  <div className="rounded-xl px-4 py-2.5 text-sm max-w-[85%]"
    style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)', border: '1px solid var(--bg-border)' }}>
    {response}
  </div>
</div>
```

## State Management

### Local State
```typescript
const [messages, setMessages] = useState<Message[]>([])
const [input, setInput] = useState('')
const [isLoading, setIsLoading] = useState(false)
const messagesEndRef = useRef<HTMLDivElement>(null)
```

### Global State
```typescript
// uiStore.ts
aiPanelOpen: boolean
setAiPanelOpen: (open: boolean) => void
```

## Example Queries

- "What is the total portfolio value?"
- "Show me high-risk branches"
- "Compare Q1 vs Q2 revenue"
- "List transactions over 1M TND"
- "What compliance issues are pending?"

## Error Handling

| Error | Display |
|-------|---------|
| Network error | "Connection failed. Check your network." with retry |
| API error | "Unable to process query. Please rephrase." |
| Timeout | "Query timed out. Try a simpler question." |
| Empty response | "I didn't understand. Could you rephrase?" |

## Design Principles

1. **Non-blocking**: Panel doesn't prevent interaction with main content
2. **Context-aware**: Can reference current page (future enhancement)
3. **Persistent**: Message history survives page navigation (within session)
4. **Accessible**: Keyboard navigable, screen reader friendly
