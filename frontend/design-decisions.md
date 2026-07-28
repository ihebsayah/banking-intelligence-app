# Design Decisions

## 1. SSO-First Authentication

**Decision**: Remove all local authentication UI in Keycloak mode. No password fields, no remember-me, no forgot-password.

**Why**: Authentication belongs to Keycloak. Showing local auth UI when Keycloak is configured creates confusion and security risk. The application never handles credentials directly.

## 2. TopBar + Sidebar Layout

**Decision**: Global TopBar (search, notifications, user menu) paired with role-filtered Sidebar navigation.

**Why**: Enterprise standard pattern (Azure Portal, GitHub, Linear). Separates global actions (TopBar) from navigation (Sidebar). User menu in TopBar is universally accessible regardless of sidebar state.

## 3. Neutral Colour Palette

**Decision**: Slate-dominant palette with blue accents only for interactive elements. No gradients, no glows, no multi-coloured backgrounds.

**Why**: Data-dense financial dashboards need visual calm. Coloured backgrounds compete with data for attention. Blue accents guide the eye to actionable elements without distraction.

## 4. Minimal Animation

**Decision**: 150ms transitions, no bouncing, no glowing, no flowing animations. Only fade-in and slide-up for screen transitions.

**Why**: Enterprise users interact with this tool for hours. Subtle motion reduces cognitive load. Animated effects designed for marketing sites are distracting in operational tools.

## 5. Inline Auth Screens (No Separate Routes)

**Decision**: Auth state screens (loading, unlinked, expired, error) render inline via ProtectedRoute rather than separate routes.

**Why**: Simplifies routing. Auth states are transient — they resolve to either the app or the login page. Making them routes creates URL history pollution and complicates the back button.

## 6. Role-Badged User Menu

**Decision**: User menu shows name, email, and role badge. No token, no ID, no Keycloak subject.

**Why**: Users need to know their role for context. They should never see or need to interact with tokens, JWTs, or system IDs. Security by obscurity is not the goal — these are simply not useful to end users.

## 7. Sidebar Collapse Persistence

**Decision**: Sidebar collapsed state persisted to localStorage via Zustand.

**Why**: Users have strong preferences about sidebar width. Losing this preference on refresh is a friction point. Persisting it is one line of code with high UX payoff.

## 8. Kept Legacy Auth Mode

**Decision**: Preserve the legacy email/password login for non-Keycloak deployments.

**Why**: The application supports both Keycloak and legacy auth modes via `VITE_AUTH_PROVIDER`. Removing the legacy mode would break deployments that haven't migrated to Keycloak yet.

## 9. BankingHeader as In-Page Component

**Decision**: BankingHeader became an in-page header component (title + refresh) rather than a layout component.

**Why**: TopBar now handles the global header role. BankingHeader provides page-specific context (title, subtitle, refresh controls) that varies per page. Keeping it as a page-level component avoids prop-drilling page-specific data through the layout.

## 10. No New Dependencies

**Decision**: Zero new packages added. All components built with existing deps (React, Tailwind, lucide-react, clsx, zustand).

**Why**: Every new dependency is a maintenance surface. The existing stack covers all UI needs. A button, a badge, and a dropdown don't require a component library.
