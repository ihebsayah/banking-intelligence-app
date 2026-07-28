# Empty State Guidelines

## When to Show Empty States

1. **No data yet**: User hasn't created any items
2. **No search results**: Filter/search returns nothing
3. **API unavailable**: Backend service is down
4. **Permission denied**: User lacks access to data
5. **Loading complete, zero results**: Confirmed empty, not just loading

## Empty State Patterns

### Pattern 1: No Data (Primary)
```tsx
<div className="flex flex-col items-center justify-center py-16 text-center"
  style={{ border: '1px dashed var(--bg-border)' }}>
  <Icon size={32} style={{ color: 'var(--text-muted)' }} />
  <h3 className="text-sm font-semibold mt-3" style={{ color: 'var(--text-primary)' }}>
    No data available
  </h3>
  <p className="text-xs mt-1 max-w-sm" style={{ color: 'var(--text-muted)' }}>
    Description of what should appear here.
  </p>
</div>
```

### Pattern 2: Service Unavailable
```tsx
<ServiceUnavailable
  serviceName="Branches"
  missingEndpoint="GET /banking/branches"
  method="GET"
  requiredRole="banking.view"
/>
```

Shows:
- Service name
- Missing endpoint
- HTTP method
- Required RBAC role

### Pattern 3: Search/Filter Empty
```tsx
<div className="text-center py-12 text-xs"
  style={{ border: '1px dashed var(--bg-border)', color: 'var(--text-muted)' }}>
  No results match your search.
</div>
```

### Pattern 4: Skeleton Loading
```tsx
<div className="h-10 rounded-lg animate-pulse"
  style={{ background: 'var(--bg-tertiary)' }} />
```

Use during initial load. Never show empty state + skeleton simultaneously.

## Copy Guidelines

### Do
- Be specific: "No branches found" not "No data"
- Suggest action: "Create a branch to get started"
- Be honest: "Service unavailable" not "Something went wrong"

### Don't
- Blame the user: "You haven't created anything"
- Use jargon: "404 Not Found"
- Be vague: "Oops!" or "Something went wrong"

## Placement

- Centered vertically and horizontally in the container
- Max width: 400px for text
- Icon: 32px, `var(--text-muted)` color
- Title: 14px, bold, `var(--text-primary)`
- Description: 12px, `var(--text-muted)`, max 2 lines
