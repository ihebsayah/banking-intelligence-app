# Command Palette

## Overview

Global command palette triggered by `Ctrl+K` (or `Cmd+K` on macOS). Provides keyboard-first navigation and actions.

## Features

- **Search**: Type to filter commands by name
- **Categories**: Navigation, Actions, Settings
- **Keyboard navigation**: ↑↓ to move, Enter to execute, Esc to close
- **Fuzzy matching**: Partial string matching on command names
- **Global**: Works from any page in the application

## Implementation

### Component
`src/components/CommandPalette.tsx`

### State
Managed by `uiStore.ts`:
```typescript
commandPaletteOpen: boolean
setCommandPaletteOpen: (open: boolean) => void
```

### Keyboard Shortcut
```typescript
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      setCommandPaletteOpen(!commandPaletteOpen)
    }
  }
  window.addEventListener('keydown', handler)
  return () => window.removeEventListener('keydown', handler)
}, [commandPaletteOpen])
```

## Commands

### Navigation
| Label | Route | Description |
|-------|-------|-------------|
| Dashboard | `/banking` | Executive overview |
| Branches | `/banking/branches` | Branch management |
| Risk Management | `/banking/risk` | Risk scoring |
| Compliance | `/banking/compliance` | Compliance audit |
| Reports | `/banking/reports` | Query engine |
| Admin | `/banking/admin` | System admin |
| Profile | `/banking/profile` | User profile |
| Settings | `/banking/settings` | Preferences |

### Actions
| Label | Action | Description |
|-------|--------|-------------|
| Toggle Theme | `uiStore.setTheme()` | Cycle light/dark/system |
| Toggle AI Assistant | `uiStore.setAiPanelOpen()` | Open/close AI panel |
| Sign Out | `authStore.logout()` | Clear token, redirect |

## Styling

- **Overlay**: Semi-transparent black (`rgba(0,0,0,0.5)`)
- **Modal**: `var(--bg-card)` background, `var(--bg-border)` border
- **Input**: Full width, `var(--bg-tertiary)` background
- **Selected item**: `var(--bg-hover)` background
- **Text**: `var(--text-primary)` for labels, `var(--text-muted)` for shortcuts

## Accessibility

- Focus trapped in modal when open
- Screen reader announces "Command palette" on open
- All commands navigable via keyboard only
- Esc always closes the palette
