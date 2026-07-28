# Design Decisions

## 1. CSS Variables Over Tailwind Dark Mode

**Decision**: Use CSS custom properties in `src/index.css` instead of Tailwind's built-in `dark:` prefix.

**Rationale**:
- Single source of truth for all colors
- Theme switching via class toggle (`document.documentElement.classList.toggle('dark')`)
- Supports system preference detection
- Inline styles with `var()` work everywhere — no Tailwind config dependency
- Easier to extend with custom themes later

**Tradeoff**: Inline styles lose Tailwind's utility class ergonomics for colors. Accepted because consistency and runtime switching matter more.

## 2. Minimal Shell Pattern

**Decision**: TopBar (48px) + collapsible Sidebar (256px/64px) instead of full-featured header.

**Rationale**:
- Maximizes content area for data-heavy pages
- Follows Microsoft Fabric, Stripe, Linear patterns
- Sidebar collapse reduces cognitive load for power users
- TopBar reserved for global actions only (theme, command palette, user menu)

## 3. Command Palette as Primary Navigation

**Decision**: Ctrl+K command palette as the primary navigation mechanism, with sidebar as secondary.

**Rationale**:
- Keyboard-first workflow for power users
- Searchable — no need to remember where things are
- Extensible (can add actions, not just routes)
- Follows VS Code, Linear, Raycast patterns

## 4. AI Assistant as Global Panel

**Decision**: AI assistant as a slide-in side panel, not a standalone page.

**Rationale**:
- Always accessible regardless of current page
- Can reference current page context
- Non-blocking — user can still see and interact with main content
- Follows GitHub Copilot, Cursor patterns

## 5. SSO-Only Login

**Decision**: Keycloak mode shows only "Continue with SSO" — no username/password form.

**Rationale**:
- Production uses Keycloak exclusively
- Reduces attack surface (no password form to phish)
- Simpler UX for enterprise users
- Legacy mode preserved for development only

## 6. No Glow Effects

**Decision**: Remove all `shadow-[0_0_*]` glow effects from the original design.

**Rationale**:
- Glows create visual noise without informational value
- They don't translate well to light mode
- Professional tools (Stripe, Linear, Datadog) don't use them
- Border + background contrast is sufficient for hierarchy

## 7. 200ms Animation Budget

**Decision**: Maximum 200ms for all transitions, fade/slide only.

**Rationale**:
- Animations should feel instant, not theatrical
- Bankers are power users — they want speed, not delight
- Reduces motion sickness concerns
- Measurable: all `transition` utilities use `duration-150` or `duration-200`
