# Frontend Design System

## Color Tokens

All colors use CSS custom properties defined in `src/index.css`. The `dark` class on `<html>` activates dark mode; light mode is the default.

### Background Tokens
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-primary` | `#f8fafc` | `#040711` | Page background |
| `--bg-secondary` | `#f1f5f9` | `#050b14` | Sidebar, secondary surfaces |
| `--bg-tertiary` | `#e2e8f0` | `#070d19` | Input backgrounds, skeletons |
| `--bg-card` | `#ffffff` | `#08111e` | Cards, panels |
| `--bg-hover` | `#e2e8f0` | `#0c1930` | Row hover, interactive states |
| `--bg-border` | `#cbd5e1` | `#0f2040` | All borders |

### Text Tokens
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--text-primary` | `#0f172a` | `#ffffff` | Headings, primary content |
| `--text-secondary` | `#334155` | `#c8d6e5` | Values, secondary labels |
| `--text-muted` | `#64748b` | `#8899aa` | Table cells, labels |
| `--text-subtle` | `#94a3b8` | `#556677` | Placeholders, metadata |

### Accent Tokens
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--accent-blue` | `#2563eb` | `#4d9fff` | Primary actions, links |
| `--accent-green` | `#16a34a` | `#22c55e` | Success, positive values |
| `--accent-red` | `#dc2626` | `#ef4444` | Errors, negative values |
| `--accent-amber` | `#d97706` | `#f59e0b` | Warnings, caution |
| `--accent-purple` | `#9333ea` | `#a855f7` | Tags, special states |

## Typography

- **Font stack**: System font stack via Tailwind defaults
- **Base size**: 14px
- **Headings**: Bold, `var(--text-primary)`, uppercase tracking on section headers
- **Body**: Regular weight, `var(--text-secondary)`
- **Labels**: 10px uppercase, bold, `var(--text-muted)`, `tracking-wider`
- **Monospace**: `font-mono` for IDs, codes, amounts

## Spacing & Layout

- **Sidebar**: 256px expanded, 64px collapsed
- **TopBar**: 48px height, sticky
- **Page padding**: 24px (p-6)
- **Card padding**: 20px (p-5)
- **Grid gaps**: 16px (gap-4) for card grids, 20px (gap-5) for chart grids
- **Max content width**: 1600px centered

## Component Patterns

### Cards
```tsx
<div className="rounded-xl border p-5"
  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
  {/* content */}
</div>
```

### Buttons
```tsx
<button className="btn-primary">Primary</button>
<button className="btn-ghost">Ghost</button>
<button className="btn-secondary">Secondary</button>
```

### Status Badges
```tsx
<span className="badge-success">Active</span>
<span className="badge-error">Suspended</span>
<span className="badge-warning">Pending</span>
```

### Table Rows
```tsx
<tr className="border-b transition-colors"
  style={{ borderColor: 'var(--bg-border)' }}>
  <td style={{ color: 'var(--text-primary)' }}>Cell</td>
</tr>
```

## Animations

- **Budget**: 200ms max
- **Types**: fade-in, slide-in only
- **Purpose**: Directional feedback, not decoration
- **Avoid**: Bounce, spin (except loading), scale, glow
