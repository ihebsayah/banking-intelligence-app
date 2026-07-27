# WebSocket Security Assessment — Increment 1A

**Date**: 2026-07-26
**Status**: Assessment complete — no changes in this increment

## Endpoints Assessed

### 1. Orchestrator `/ws/monitoring` (port 8001)

- **Route**: `ws://orchestrator-agent:8001/ws/monitoring`
- **Currently authenticated**: No
- **WebSocket authentication**: No JWT validation on connection upgrade
- **Sensitive data exposed**: Agent status, pipeline progress, potentially query content
- **Frontend usage**: Used by the debug/monitoring panel (not the main portal)
- **Risk**: Medium — exposes internal pipeline state but only on the Docker network

### 2. Debug Service WebSocket (port 8099)

- **Route**: `ws://debug-service:8099`
- **Currently authenticated**: No
- **WebSocket authentication**: None
- **Sensitive data exposed**: Debug information, potentially database queries
- **Frontend usage**: Dev-only debug tool, accessed via nginx `/debug/stream`
- **Risk**: Low in development — the debug-service has no restart policy and is not exposed in production-oriented configurations

## Assessment Summary

| Endpoint | Auth Required | Frontend Used | Sensitive | Risk | Action Required |
|----------|:------------:|:------------:|:---------:|:----:|:---------------:|
| `/ws/monitoring` | No | Debug panel | Yes | Medium | Deferred to Increment 2 |
| Debug WS | No | Dev tool only | Yes | Low | Deferred to Increment 2 |

## Recommendation

- Do NOT add Keycloak WebSocket authentication in Increment 1A
- WebSocket authentication requires token-in-query or subprotocol header approach, which is a frontend change
- Increment 1B (frontend Keycloak integration) should address WebSocket auth
- The monitoring WebSocket should accept a token query parameter: `ws://host/ws/monitoring?token=<access_token>`
- The debug service should remain unauthenticated in development but gated by network in production

## What Must Change Later

1. Orchestrator WebSocket must validate Keycloak tokens on connection upgrade
2. Frontend must pass access tokens when opening WebSocket connections
3. Consider a dedicated WebSocket auth middleware
4. Debug service should be excluded from production deployments
