# WebSocket Impact Assessment — Increment 1B

## Current WebSocket Usage

The frontend has a single WebSocket connection in `src/hooks/useWebSocket.ts`:

- **Endpoint**: `ws://{host}/ws/monitoring`
- **Authentication**: None (unauthenticated)
- **Protocol**: Plain WebSocket (not Socket.IO despite `socket.io-client` being installed)
- **Purpose**: Real-time agent health updates and communication log streaming
- **Data**: `agent_log`, `health_update`, `query_event`, `ping` message types
- **Scope**: Dev-only agent monitoring (visible only in `/dev/*` routes, gated to admin users via frontend route guards)

## Impact Analysis

| Aspect | Impact |
|--------|--------|
| Authentication requirement | None — unauthenticated monitoring endpoint |
| Token passing | None — no auth token in query string or headers |
| Backend changes needed | None |
| Frontend changes needed | None |
| Security risk | Medium — unauthenticated endpoint accessible to any network client |

## Security Note

Frontend route guards are **UX only** — they hide the UI but do NOT protect the backend WebSocket endpoint. If `ws://{host}/ws/monitoring` is reachable from the network, any client can connect regardless of frontend route guards or authentication state.

**Current mitigation**: The WebSocket is proxied through Vite dev server only (`/ws` → `ws://localhost:8001`). In production, the WebSocket endpoint is not exposed through the frontend build.

**Recommendation for production**: If the monitoring WebSocket is deployed beyond dev, add token authentication on the backend WebSocket handler or restrict access via network isolation (VPN/internal network only).

## Keycloak Mode Behaviour

In Keycloak mode, the WebSocket connection remains unauthenticated. This is acceptable for development because the monitoring endpoint is internal-only. No frontend changes are needed.

## Remaining Risk

If the monitoring WebSocket is later exposed in production (outside dev routes), it must be authenticated or network-isolated. This is a known limitation deferred to a future increment.

## Recommendation

No changes required for this increment. Document the unauthenticated WebSocket as a deferred security item for production hardening.
