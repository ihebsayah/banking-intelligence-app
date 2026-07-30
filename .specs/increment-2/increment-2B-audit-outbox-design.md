# Increment 2B — Audit Outbox Design

---

## Problem Statement

The previous architecture used fire-and-forget HTTP from the mutation handler to the audit agent. For sensitive banking mutations, audit delivery is not optional:

- If the audit agent is down, the HTTP call silently fails
- The mutation commits; the audit record never arrives
- No retry; no visibility; no reconciliation

The audit database (`postgres-audit`) is a separate PostgreSQL instance. Cross-database transactions are not supported. The solution is a **transactional outbox in `postgres-main`** with an async worker that delivers to the audit agent.

---

## Architecture

```
Mutation handler (API Gateway)
  ├── BEGIN postgres-main transaction
  │     ├── UPDATE/INSERT business entity
  │     ├── INSERT activity_timeline
  │     ├── INSERT notifications (if any)
  │     └── INSERT audit_outbox (status=pending, idempotency_key)
  └── COMMIT
         └── (outbox worker wakes on schedule or LISTEN/NOTIFY)
               ├── SELECT FOR UPDATE SKIP LOCKED (pending, failed with retry due)
               ├── status → delivering; locked_by = worker_id
               ├── POST /log_access to audit agent
               │     ├── Success: status → delivered; delivered_at = NOW()
               │     └── Failure: status → failed; attempt_count++; last_error
               └── COMMIT

Reconciliation worker (separate schedule, every 15 min)
  ├── SELECT outbox rows WHERE status='delivering' AND locked_at < NOW() - 5min
  │    (these are stuck deliveries — worker crashed mid-flight)
  └── SET status='pending', locked_by=NULL, locked_at=NULL

Poison handler (attempt_count >= MAX_ATTEMPTS)
  ├── SET status='poison', poison_reason = last_error
  └── INSERT notification for admin (admin:outbox_monitor)
```

---

## Schema

```sql
CREATE TYPE audit_outbox_status AS ENUM (
    'pending',
    'delivering',
    'delivered',
    'failed',
    'poison'
);

CREATE TABLE audit_outbox (
    outbox_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key     VARCHAR(255) NOT NULL UNIQUE,
    -- Deterministic format: {event_type}:{entity_id}:{actor_id}:{occurred_at_unix_ms}
    -- Example: "alert.acknowledged:3f9a...:analyst_001:1722300000000"
    event_type          VARCHAR(100) NOT NULL,
    entity_type         VARCHAR(50)  NOT NULL,
    entity_id           UUID         NOT NULL,
    actor_id            VARCHAR(100) NOT NULL,
    actor_role          VARCHAR(50)  NOT NULL,
    occurred_at         TIMESTAMPTZ  NOT NULL,
    payload             JSONB        NOT NULL,
    payload_schema_ver  SMALLINT     NOT NULL DEFAULT 1,
    status              audit_outbox_status NOT NULL DEFAULT 'pending',
    attempt_count       SMALLINT     NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    next_attempt_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_error          TEXT,
    locked_by           VARCHAR(100),
    locked_at           TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    poison_reason       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_outbox_pending
    ON audit_outbox(status, next_attempt_at)
    WHERE status IN ('pending','failed');

CREATE UNIQUE INDEX idx_audit_outbox_idem
    ON audit_outbox(idempotency_key);
```

---

## Payload Schema (v1)

```json
{
  "schema_version": 1,
  "event_type": "alert.acknowledged",
  "entity_type": "alert",
  "entity_id": "uuid",
  "actor_id": "user_id",
  "actor_role": "analyst",
  "occurred_at": "2026-07-30T03:00:00Z",
  "request_id": "uuid",
  "ip_address": "10.0.0.1",
  "before": {
    "status": "assigned",
    "version": 3
  },
  "after": {
    "status": "acknowledged",
    "version": 4
  },
  "metadata": {}
}
```

`before` and `after` contain only the fields changed by the mutation. Sensitive content (findings_text, rationale) is hashed in `before`/`after`, not included verbatim, to prevent audit log from becoming a data exfiltration vector.

```json
"before": { "findings_text_sha256": "abc123...", "version": 3 },
"after":  { "findings_text_sha256": "def456...", "version": 4 }
```

---

## Event Type Registry

| Event Type | Trigger |
|------------|---------|
| `alert.assigned` | Alert transition new→assigned |
| `alert.acknowledged` | Alert transition assigned→acknowledged |
| `alert.dismissed` | Alert transition →dismissed |
| `alert.investigation_created` | Investigation created from alert |
| `alert.resolved` | Alert resolved |
| `alert.reopened` | Alert reopened by admin |
| `investigation.started` | Investigation open→active |
| `investigation.findings_updated` | findings_text/refs updated |
| `investigation.submitted` | Investigation active→submitted |
| `investigation.completed` | Investigation completed |
| `investigation.returned` | Investigation returned |
| `investigation.cancelled` | Investigation cancelled |
| `case.created` | ComplianceCase created |
| `case.assigned` | Case assigned |
| `case.under_review` | Case review started |
| `case.awaiting_information` | IR created, case awaiting |
| `case.decision_recorded` | Decision inserted |
| `case.resolved` | Case resolved |
| `case.closed` | Case closed |
| `case.reopened` | Case reopened |
| `case.cancelled` | Case cancelled |
| `ir.created` | InformationRequest created |
| `ir.acknowledged` | IR acknowledged by analyst |
| `ir.responded` | IR response submitted |
| `ir.accepted` | IR response accepted |
| `ir.returned` | IR response returned |
| `ir.cancelled` | IR cancelled |
| `approval.created` | ApprovalRequest created |
| `approval.vote` | ApprovalDecision cast |
| `approval.approved` | ApprovalRequest approved |
| `approval.rejected` | ApprovalRequest rejected |
| `approval.expired` | ApprovalRequest expired |
| `approval.consumed` | Gated action executed |
| `comment.created` | Comment created |
| `comment.redacted` | Comment redacted by admin |
| `user.assigned_scope` | User scope granted |

---

## Idempotency Key Construction

```python
def build_idempotency_key(
    event_type: str,
    entity_id: UUID,
    actor_id: str,
    occurred_at: datetime,
) -> str:
    ts_ms = int(occurred_at.timestamp() * 1000)
    return f"{event_type}:{entity_id}:{actor_id}:{ts_ms}"
```

Key is computed before the transaction begins. If the transaction commits and the INSERT fails with UNIQUE violation (duplicate key), the outbox record already exists — idempotent; proceed. If INSERT fails for any other reason, the transaction rolls back — correct.

---

## Delivery Worker

**Implementation:** background `asyncio` task inside the API Gateway service (existing service, no new process). Runs every 5 seconds.

```python
MAX_ATTEMPTS = 5
RETRY_BACKOFF_SECONDS = [10, 30, 120, 600, 1800]  # per attempt index
LOCK_TIMEOUT_SECONDS = 300  # 5 min; reconciliation resets stuck deliveries

def _compute_next_attempt_at(attempt_count: int) -> datetime:
    """Compute next_attempt_at based on attempt index into RETRY_BACKOFF_SECONDS."""
    idx = min(attempt_count, len(RETRY_BACKOFF_SECONDS) - 1)
    return datetime.utcnow() + timedelta(seconds=RETRY_BACKOFF_SECONDS[idx])

async def outbox_worker(db: DatabaseConnector, audit_http: httpx.AsyncClient):
    while True:
        await asyncio.sleep(5)
        try:
            await deliver_pending(db, audit_http)
        except Exception as e:
            logger.error("Outbox worker error", extra={"error": str(e)})

async def deliver_pending(db, audit_http):
    # --- Transaction 1: Claim rows (short, no HTTP) ---
    async with db.transaction():
        rows = await db.fetch("""
            SELECT outbox_id, payload, idempotency_key, attempt_count
            FROM audit_outbox
            WHERE status IN ('pending', 'failed')
              AND next_attempt_at <= NOW()
            ORDER BY next_attempt_at
            LIMIT 10
            FOR UPDATE SKIP LOCKED
        """)
        if not rows:
            return

        worker_id = os.environ.get('HOSTNAME', 'worker_default')
        for row in rows:
            await db.execute("""
                UPDATE audit_outbox
                SET status='delivering', locked_by=$1, locked_at=NOW()
                WHERE outbox_id=$2
            """, [worker_id, row['outbox_id']])
    # --- Transaction 1 commits here; locks released ---

    # --- HTTP delivery outside any lock transaction ---
    for row in rows:
        try:
            resp = await audit_http.post(
                "/log_access",
                json=row['payload'],
                headers={"X-Idempotency-Key": row['idempotency_key']},
                timeout=10.0,
            )
            resp.raise_for_status()
        except Exception as e:
            attempt = row['attempt_count'] + 1
            new_status = 'poison' if attempt >= MAX_ATTEMPTS else 'failed'
            # --- Transaction 2: Record failure (short, no HTTP) ---
            async with db.transaction():
                await db.execute("""
                    UPDATE audit_outbox
                    SET status=$1, attempt_count=$2, last_attempt_at=NOW(),
                        next_attempt_at=$3, last_error=$4,
                        locked_by=NULL, locked_at=NULL,
                        poison_reason=CASE WHEN $1='poison' THEN $4 ELSE poison_reason END
                    WHERE outbox_id=$5
                """, [new_status, attempt, _compute_next_attempt_at(attempt), str(e), row['outbox_id']])
            if new_status == 'poison':
                await notify_admin_poison_event(db, row['outbox_id'])
            continue

        # --- Transaction 2: Record success (short, no HTTP) ---
        async with db.transaction():
            await db.execute("""
                UPDATE audit_outbox
                SET status='delivered', delivered_at=NOW(), locked_by=NULL, locked_at=NULL
                WHERE outbox_id=$1
            """, [row['outbox_id']])
```

---

## Audit Agent Idempotency

The audit agent at `POST /log_access` must be idempotent on `X-Idempotency-Key`. Add to `audit_log`:

```sql
ALTER TABLE audit_log
  ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_log_idempotency
  ON audit_log(idempotency_key)
  WHERE idempotency_key IS NOT NULL;
```

On duplicate key insert: return 200 with existing record (not 409). Worker treats 200 as success.

---

## Reconciliation

A separate periodic task (every 15 minutes):

```python
async def reconcile_stuck_deliveries(db):
    await db.execute("""
        UPDATE audit_outbox
        SET status='pending', locked_by=NULL, locked_at=NULL
        WHERE status='delivering'
          AND locked_at < NOW() - INTERVAL '5 minutes'
    """)
```

---

## Retry Policy

| Attempt | Wait before retry |
|---------|-----------------|
| 1 | 10 seconds |
| 2 | 30 seconds |
| 3 | 2 minutes |
| 4 | 10 minutes |
| 5 (→ poison) | 30 minutes; then poison |

---

## Poison Event Handling

When `attempt_count >= MAX_ATTEMPTS`:
- status → `poison`
- `poison_reason` = last error message
- Notification inserted for admin users with `admin:outbox_monitor`
- Admin can read via `GET /api/v1/admin/outbox?status=poison`
- Admin can trigger manual retry via `POST /api/v1/admin/outbox/{id}/retry`
- Poison events are never silently discarded; they remain in table until manually resolved or expired by retention job

---

## Observability

| Metric | How |
|--------|-----|
| Pending count | `SELECT COUNT(*) FROM audit_outbox WHERE status='pending'` |
| Failed count | `SELECT COUNT(*) FROM audit_outbox WHERE status='failed'` |
| Poison count | `SELECT COUNT(*) FROM audit_outbox WHERE status='poison'` |
| Delivery lag | `SELECT AVG(delivered_at - occurred_at) FROM audit_outbox WHERE status='delivered' AND delivered_at > NOW() - INTERVAL '1 hour'` |
| Admin endpoint | `GET /api/v1/admin/outbox` — paginated; filterable by status |

---

## Retention

| Status | Retention |
|--------|-----------|
| delivered | 90 days (retention worker deletes) |
| poison | 1 year (visibility and incident investigation) |
| failed | Until delivered or manual poison promotion |

---

## Failure Modes and Guarantees

| Scenario | Result |
|----------|--------|
| Audit agent down during mutation | Mutation commits; outbox row pending; delivery retries until agent recovers |
| Audit agent down for 30+ minutes | Rows accumulate in `failed`; eventually `poison`; admin notified |
| Worker crashes mid-delivery | Reconciliation resets stuck `delivering` rows to `pending` within 5 min |
| Network timeout on delivery | Failed; retry with backoff |
| Duplicate delivery (worker restart) | Audit agent idempotency key prevents duplicate `audit_log` row |
| postgres-main transaction rolled back | Outbox row not inserted; no audit event (correct: mutation did not occur) |
| Outbox table full | Extremely unlikely; retention worker prevents accumulation; alarm on pending > 1000 |
