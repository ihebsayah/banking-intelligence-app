# Frontend Design System

## Principles

- **Clean** — minimal chrome, maximum content density
- **Neutral** — slate palette, blue accents only for interactive elements
- **Calm** — no flashing, no bouncing, 150ms transitions max
- **Data-first** — whitespace is a feature, hierarchy through typography

## Colour Palette

| Token | Usage |
|-------|-------|
| `bg-primary` (#080b14) | Page background |
| `bg-secondary` (#0d1020) | Sidebar, topbar |
| `bg-card` (#151b2e) | Cards, panels |
| `bg-border` (#1e2640) | Borders, dividers |
| `bg-hover` (#1a2038) | Hover states |
| Blue-400/500/600 | Interactive elements, links, active states |
| Slate-300/400/500 | Text hierarchy (primary/secondary/muted) |
| Green-400 | Success, positive values |
| Red-400 | Errors, negative values, danger |
| Amber-400 | Warnings, pending states |

## Typography

- **Font**: Inter (system-ui fallback)
- **Mono**: JetBrains Mono (code, data, IDs)
- **Sizes**: xs (11px), sm (13px), base (15px), lg (18px)
- **Weights**: medium (500), semibold (600), bold (700)
- **Hierarchy**: h1 = text-base font-semibold white, h2 = text-sm font-semibold slate-200

## Spacing

- Page padding: `p-6`
- Card padding: `p-4` to `p-6`
- Section gaps: `space-y-6`
- Grid gaps: `gap-4` to `gap-6`

## Components

### Buttons
- `btn-primary` — blue-600 bg, white text, no shadow (removed glow effects)
- `btn-secondary` — bg-tertiary, slate text, border
- `btn-ghost` — transparent, hover reveals bg-hover
- `btn-danger` — red-500/10 bg, red text

### Cards
- `glass-card` — bg-card, border-bg-border, rounded-lg, subtle hover border
- `glass-card-static` — same without hover effect

### Badges
- `badge-blue/green/red/yellow/purple/gray` — muted bg, colored text, thin border

### Inputs
- `input` — bg-tertiary, border-bg-border, blue focus ring

## Animations

- Duration: 150ms for transitions, 200ms for enters
- Only: fade-in, slide-up, pulse (loading dots)
- No: glow, bounce, spin-slow, flow, stepGlow

## Icon System

- **Library**: lucide-react (consistent, single source)
- **Size standard**: 14px (inline), 16px (nav/actions), 20px (feature icons), 24px (screens)
