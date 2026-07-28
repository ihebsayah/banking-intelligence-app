# UI Components

## Layout Components

### TopBar (`src/components/Layout/TopBar.tsx`)
- Workspace title ("Banking Intelligence System")
- Command palette trigger button (Ctrl+K hint)
- Theme cycle button (sun → moon → monitor)
- User avatar with dropdown (Profile, Settings, Sign Out)
- Sticky, 48px height, `var(--bg-primary)` background

### BankingSidebar (`src/components/Layout/BankingSidebar.tsx`)
- Logo + app name
- Navigation items (role-filtered)
- Bottom section: Profile, Settings, Dev Monitor (admin only)
- Collapse toggle (256px ↔ 64px)
- Tooltips on collapsed hover
- Sign Out button

### BankingHeader (`src/components/Layout/BankingHeader.tsx`)
- Page title + subtitle
- Last refreshed timestamp
- Refresh button with spinner
- Custom actions slot

## Core UI Components

### Button Variants
- **`btn-primary`**: `var(--accent-blue)` background, white text
- **`btn-secondary`**: `var(--bg-tertiary)` background, bordered
- **`btn-ghost`**: Transparent, hover reveals `var(--bg-hover)`
- **`btn-danger`**: Red variant for destructive actions

### Card (`glass-card-static`)
- `var(--bg-card)` background
- `var(--bg-border)` border
- Rounded corners (12px)
- No shadow by default

### Input
- `var(--bg-tertiary)` background
- `var(--bg-border)` border, `var(--accent-blue)` on focus
- `var(--text-primary)` text color
- 36px height, 8px border-radius

### Status Badges
- **`badge-success`**: Green for active/compliant
- **`badge-error`**: Red for suspended/non-compliant
- **`badge-warning`**: Amber for pending/in-progress
- **`badge-info`**: Blue for neutral states

### Avatar
- Circular, `var(--accent-blue)` fallback background
- White initial letter on fallback
- Sizes: sm (32px), md (40px), lg (56px)

## Composite Components

### CommandPalette
- Modal overlay with search input
- Filtered command list with keyboard navigation
- Categories: Navigation, Actions, Settings
- Esc to close, Enter to select

### AiAssistantPanel
- Slide-in right panel (400px)
- Chat interface with message history
- Textarea input, Enter to send
- Loading state with pulsing dots
- Integrates with `queryApi.submitQuery()`

### KPICard
- Metric value with formatting
- Trend indicator (up/down arrow + percentage)
- Sparkline chart (optional)
- Loading skeleton state

### DataTable
- Sortable column headers
- Row hover highlight (`var(--bg-hover)`)
- Alternating row colors (subtle)
- Empty state when no data

## Theming

All components use CSS custom properties:
- Background: `var(--bg-*)`
- Text: `var(--text-*)`
- Accent: `var(--accent-*)`
- Border: `var(--bg-border)`

Toggle `.dark` class on `<html>` to switch themes.
