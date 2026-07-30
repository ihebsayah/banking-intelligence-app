# Command Palette

## Overview

Global command palette triggered by `Ctrl+K` (or `Cmd+K` on macOS). Keyboard-first navigation and actions for the entire application. Designed as the primary power-user interface.

## Features

- **Search**: Type to filter commands by name (case-insensitive substring match)
- **Categories**: Navigate, Run actions
- **Keyboard navigation**: ↑↓ to move, Enter to execute, Esc to close
- **Global**: Works from any page in the application
- **Extensible**: New commands can be added without changing the component

## Implementation

### Component
`src/components/CommandPalette.tsx`

### State
```typescript
// uiStore.ts
commandPaletteOpen: boolean
setCommandPaletteOpen: (open: boolean) => void
```

### Keyboard Shortcut
```typescript
Ctrl/Cmd + K → open/close
Esc → close
↑/↓ → navigate
Enter → execute selected
```

## Commands

### Navigate
| Label | Route | Description |
|-------|-------|-------------|
| Dashboard | `/dashboard` | Executive overview |
| Branches | `/branches` | Branch management |
| AI Assistant | `/assistant` | AI workspace |
| KPI Analytics | `/kpi` | Financial KPIs |
| KPI Governance | `/kpi-governance` | KPI governance |
| Risk Monitor | `/risk` | Risk scoring |
| Compliance | `/compliance` | Compliance audit |
| Reports | `/reports` | Query engine |
| Admin | `/admin` | System admin |
| Profile | `/profile` | User profile |
| Settings | `/settings` | Preferences |

### Actions
| Label | Action | Description |
|-------|--------|-------------|
| Toggle Theme | `toggleTheme` | Cycle light/dark/system |
| Toggle AI Assistant | `toggleAiPanel` | Open/close AI workspace |
| Sign Out | `logout` | End session |

### Future
- "Open report: [name]" — quick access to saved reports
- "Switch branch: [name]" — set active branch context
- "Search: transactions > 1M" — type-ahead search
- "Run: [command]" — execute system actions

## Styling

- **Overlay**: Semi-transparent black (`rgba(0,0,0,0.5)`), `backdrop-filter: blur(4px)`
- **Modal**: `var(--bg-card)` background, `var(--bg-border)` border, max-w-md
- **Input**: Full width, transparent background
- **Selected item**: `var(--bg-hover)` background
- **Text**: `var(--text-primary)` for labels, `var(--text-subtle)` for shortcuts

## Accessibility

- Focus trapped in modal when open
- Screen reader announces "Command palette" on open
- All commands navigable via keyboard only
- Esc always closes the palette
