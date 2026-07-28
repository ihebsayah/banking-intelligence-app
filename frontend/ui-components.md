# UI Components

## Reusable Components

### Avatar
- **File**: `src/components/ui/Avatar.tsx`
- **Props**: `name`, `size` (sm/md/lg), `className`
- Renders first initial in a circle with blue-600/15 background

### StatusBadge
- **File**: `src/components/ui/StatusBadge.tsx`
- **Props**: `variant` (blue/green/red/yellow/purple/gray), `children`
- Pill-shaped badge with colored background and border

### RoleBadge
- **File**: `src/components/ui/StatusBadge.tsx`
- **Props**: `role` (admin/compliance/manager/analyst)
- Maps role to appropriate StatusBadge variant

### LoadingState
- **File**: `src/components/ui/LoadingState.tsx`
- **Props**: `message` (optional)
- Centered loading indicator with animated dots and message

### ErrorState
- **File**: `src/components/ui/ErrorState.tsx`
- **Props**: `title`, `message`, `onRetry`, `retryLabel`
- Centered error display with optional retry button

### EmptyState
- **File**: `src/components/ui/EmptyState.tsx`
- **Props**: `icon`, `title`, `description`, `action`
- Centered empty state with icon, text, and optional action button

### PageHeader
- **File**: `src/components/ui/PageHeader.tsx`
- **Props**: `title`, `subtitle`, `actions`
- Standard page header with title/subtitle and optional action buttons

## Layout Components

### TopBar
- **File**: `src/components/Layout/TopBar.tsx`
- Global top navigation bar with search, notifications, user menu

### BankingSidebar
- **File**: `src/components/Layout/BankingSidebar.tsx`
- Role-filtered navigation sidebar with collapse support

### BankingHeader
- **File**: `src/components/Layout/BankingHeader.tsx`
- In-page header with title, subtitle, refresh, last-updated

## Auth Components

### LoginPage
- **File**: `src/components/auth/LoginPage.tsx`
- SSO-first landing (Keycloak) or legacy email/password form

### ProtectedRoute
- **File**: `src/components/auth/ProtectedRoute.tsx`
- Auth gate with loading, error, unlinked, expired, forbidden screens

## CSS Classes (index.css)

| Class | Purpose |
|-------|---------|
| `.glass-card` | Card with subtle border hover |
| `.glass-card-static` | Card without hover effect |
| `.btn-primary/secondary/ghost/danger` | Button variants |
| `.input` | Styled text input |
| `.badge-*` | Coloured status badges |
| `.nav-item-active/inactive` | Navigation items |
| `.status-dot-*` | Coloured status indicators |
| `.data-table` | Table with consistent styling |
| `.tab-active/inactive` | Tab navigation |
