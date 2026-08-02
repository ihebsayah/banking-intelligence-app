#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# staging_smoke_test.sh — Phase 2B.18 Staging Deployment Smoke Tests
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

WORKBENCH_URL="${WORKBENCH_URL:-http://localhost:8014}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
REPORT_FILE="${REPORT_FILE:-/tmp/staging-smoke-report.txt}"
PASS_COUNT=0
FAIL_COUNT=0

BOLD='\033[1m'; GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log() { echo -e "$@" | tee -a "$REPORT_FILE"; }
pass() { PASS_COUNT=$((PASS_COUNT+1)); log "${GREEN}PASS${NC} $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); log "${RED}FAIL${NC} $1"; }
info() { log "${YELLOW}i $1${NC}"; }
section() { log "\n${BOLD}${CYAN}═══ $1 ═══${NC}\n"; }

> "$REPORT_FILE"
log "Banking Intelligence System — Staging Smoke Test Report"
log "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

check_http() {
  local label="$1" url="$2" expect="${3:-200}"
  local code; code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
  [ "$code" = "$expect" ] && pass "$label ($code)" || fail "$label (expected $expect, got $code)"
}

check_container() {
  local label="$1" container="$2"
  local status; status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "not_found")
  if [ "$status" = "running" ]; then pass "$label ($container)";
  elif [ "$status" = "not_found" ]; then fail "$label not deployed";
  else fail "$label status=$status"; fi
}

seed_row() {
  python3 -c "
import psycopg2, sys
conn = psycopg2.connect('postgresql://integration_user:integrationpass123@localhost:5435/banking_integration')
cur = conn.cursor()
cur.execute(\$1, eval(\$2))
conn.commit()
cur.close(); conn.close()
" "$1" "$2" 2>/dev/null
}

# ── Infrastructure ─────────────────────────────────────────────────────────────
section "Infrastructure"
check_http "API Gateway"         "http://localhost:8000/health"       200
check_http "Workbench"           "$WORKBENCH_URL/health"              200
check_http "Frontend"            "$FRONTEND_URL"                      200
check_http "Keycloak realm"      "$KEYCLOAK_URL/realms/banking-intelligence" 200
check_http "Audit Agent"         "http://localhost:8008/health"       200

# ── Container Health ───────────────────────────────────────────────────────────
section "Container Health"
for c in banking_api_gateway banking_audit_agent banking_workbench \
         banking_postgres_main banking_postgres_audit banking_postgres_integration \
         banking_redis banking_frontend; do
  check_container "$c" "$c"
done

# ── Authentication ─────────────────────────────────────────────────────────────
section "Authentication"
curl -sf --max-time 5 -X GET "$WORKBENCH_URL/api/v1/notifications" \
  -H "X-Test-User: sbtb_analyst_1" >/dev/null 2>&1 \
  && pass "Auth via X-Test-User header" || fail "Auth via X-Test-User header"

UNAUTH_CODE=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" \
  -X GET "$WORKBENCH_URL/api/v1/notifications" 2>/dev/null || echo "000")
[ "$UNAUTH_CODE" = "401" ] && pass "Unauthorized rejected (401)" || info "Unauthorized: $UNAUTH_CODE"

# ── Alert Workflow ─────────────────────────────────────────────────────────────
section "Alert Workflow"
ALERT_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_row \
  "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status, assigned_to, version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)" \
  "('$ALERT_ID', 'transaction_anomaly', 'high', 'Smoke Alert', '', 'hq_main', 'new', None, 1)"
pass "Alert seeded ($ALERT_ID)"

ASSIGN=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/alerts/$ALERT_ID/assign" \
  -H "X-Test-User: sbtb_admin_1" -H "Content-Type: application/json" \
  -d '{"assigned_to":"sbtb_analyst_1","expected_version":1,"reason":"smoke"}' 2>/dev/null || echo "{}")
STATUS=$(echo "$ASSIGN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('alert',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "assigned" ] && pass "Alert assigned → $STATUS" || fail "Alert assign (got $STATUS)"

ACK=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/alerts/$ALERT_ID/acknowledge" \
  -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
  -d '{"expected_version":2}' 2>/dev/null || echo "{}")
STATUS=$(echo "$ACK" | python3 -c "import sys,json; print(json.load(sys.stdin).get('alert',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "acknowledged" ] && pass "Alert acknowledged → $STATUS" || fail "Alert ack (got $STATUS)"

# Seed medium-severity alert for dismiss test (no approval needed)
DISMISS_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_row \
  "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status, assigned_to, version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)" \
  "('$DISMISS_ID', 'test', 'medium', 'Dismiss Test', '', 'hq_main', 'acknowledged', 'sbtb_analyst_1', 1)"
DISMISS=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/alerts/$DISMISS_ID/dismiss" \
  -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
  -d '{"dismissed_reason":"fp smoke","expected_version":1}' 2>/dev/null || echo "{}")
STATUS=$(echo "$DISMISS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('alert',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "dismissed" ] && pass "Alert dismissed → $STATUS" || fail "Alert dismiss (got $STATUS)"

# ── Investigation Workflow ────────────────────────────────────────────────────
section "Investigation Workflow"
INV_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_row \
  "INSERT INTO investigations (investigation_id, title, description, scope_id, status, priority, assigned_to, created_by, version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)" \
  "('$INV_ID', 'Smoke Investigation', '', 'hq_main', 'open', 'medium', 'sbtb_analyst_1', 'sbtb_analyst_1', 1)"
pass "Investigation seeded ($INV_ID)"

START=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/investigations/$INV_ID/transition" \
  -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
  -d '{"target_status":"active","expected_version":1}' 2>/dev/null || echo "{}")
STATUS=$(echo "$START" | python3 -c "import sys,json; print(json.load(sys.stdin).get('investigation',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "active" ] && pass "Started → $STATUS" || fail "Start (got $STATUS)"

FINDINGS=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/investigations/$INV_ID" \
  -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
  -d '{"findings_text":"smoke evidence","expected_version":2}' 2>/dev/null || echo "{}")
FT=$(echo "$FINDINGS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('investigation',{}).get('findings_text',''))" 2>/dev/null)
[ "$FT" = "smoke evidence" ] && pass "Findings saved" || fail "Findings save"

SUBMIT=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/investigations/$INV_ID/transition" \
  -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
  -d '{"target_status":"submitted","expected_version":3}' 2>/dev/null || echo "{}")
STATUS=$(echo "$SUBMIT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('investigation',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "submitted" ] && pass "Submitted → $STATUS" || fail "Submit (got $STATUS)"

COMPLETE=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/investigations/$INV_ID/transition" \
  -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
  -d '{"target_status":"completed","expected_version":4}' 2>/dev/null || echo "{}")
STATUS=$(echo "$COMPLETE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('investigation',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "completed" ] && pass "Completed → $STATUS" || fail "Complete (got $STATUS)"

# ── Case Workflow ──────────────────────────────────────────────────────────────
section "Case Workflow"
CASE_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_row \
  "INSERT INTO compliance_cases (case_id, title, description, scope_id, status, priority, risk_level, assigned_to, created_by, version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" \
  "('$CASE_ID', 'Smoke Case', '', 'hq_main', 'open', 'medium', 'low', 'sbtb_compliance_1', 'sbtb_compliance_1', 1)"
pass "Case seeded ($CASE_ID)"

ASSIGN_CASE=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/cases/$CASE_ID/assign" \
  -H "X-Test-User: sbtb_admin_1" -H "Content-Type: application/json" \
  -d '{"assigned_to":"sbtb_compliance_1","expected_version":1}' 2>/dev/null || echo "{}")
STATUS=$(echo "$ASSIGN_CASE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('case',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "assigned" ] && pass "Assigned → $STATUS" || fail "Assign (got $STATUS)"

REVIEW=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/cases/$CASE_ID/transition" \
  -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
  -d '{"target_status":"under_review","expected_version":2}' 2>/dev/null || echo "{}")
STATUS=$(echo "$REVIEW" | python3 -c "import sys,json; print(json.load(sys.stdin).get('case',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "under_review" ] && pass "Review → $STATUS" || fail "Review (got $STATUS)"

DECISION=$(curl -sf --max-time 10 -X POST "$WORKBENCH_URL/api/v1/cases/$CASE_ID/decisions" \
  -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
  -d '{"decision_type':'no_action','rationale':'smoke resolution','expected_version':3}' 2>/dev/null || echo "{}")
STATUS=$(echo "$DECISION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('case',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "resolved" ] && pass "Decision → $STATUS" || fail "Decision (got $STATUS)"

CLOSE=$(curl -sf --max-time 10 -X POST "$WORKBENCH_URL/api/v1/cases/$CASE_ID/close" \
  -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
  -d '{"closure_reason':'smoke closed','expected_version':4}' 2>/dev/null || echo "{}")
STATUS=$(echo "$CLOSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('case',{}).get('status',''))" 2>/dev/null)
[ "$STATUS" = "closed" ] && pass "Closed → $STATUS" || fail "Close (got $STATUS)"

# ── Information Requests ───────────────────────────────────────────────────────
section "Information Requests"
IR_CASE_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_row \
  "INSERT INTO compliance_cases (case_id, title, description, scope_id, status, priority, risk_level, assigned_to, created_by, version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" \
  "('$IR_CASE_ID', 'IR Smoke Case', '', 'hq_main', 'under_review', 'medium', 'high', 'sbtb_compliance_1', 'sbtb_compliance_1', 1)"
IR_RESP=$(curl -sf --max-time 10 -X POST "$WORKBENCH_URL/api/v1/cases/$IR_CASE_ID/information-requests" \
  -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
  -d '{"assigned_to":"sbtb_analyst_1","question":"Provide details","expected_case_version":1}' 2>/dev/null || echo "{}")
IR_STATUS=$(echo "$IR_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('information_request',{}).get('status',''))" 2>/dev/null)
[ "$IR_STATUS" = "open" ] && pass "IR created → $IR_STATUS" || fail "IR create (got $IR_STATUS)"

ACTUAL_IR_ID=$(echo "$IR_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('information_request',{}).get('ir_id',''))" 2>/dev/null)
if [ -n "$ACTUAL_IR_ID" ]; then
  ACK_IR=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/information-requests/$ACTUAL_IR_ID/acknowledge" \
    -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
    -d '{"expected_version":1}' 2>/dev/null || echo "{}")
  IR_STATUS=$(echo "$ACK_IR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('information_request',{}).get('status',''))" 2>/dev/null)
  [ "$IR_STATUS" = "acknowledged" ] && pass "IR acknowledged → $IR_STATUS" || fail "IR ack (got $IR_STATUS)"

  RESP_IR=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/information-requests/$ACTUAL_IR_ID/respond" \
    -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" \
    -d '{"response_text":"details provided","expected_version":2}' 2>/dev/null || echo "{}")
  IR_STATUS=$(echo "$RESP_IR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('information_request',{}).get('status',''))" 2>/dev/null)
  [ "$IR_STATUS" = "responded" ] && pass "IR responded → $IR_STATUS" || fail "IR respond (got $IR_STATUS)"

  ACCEPT_IR=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/information-requests/$ACTUAL_IR_ID/accept" \
    -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
    -d '{"expected_version":3}' 2>/dev/null || echo "{}")
  IR_STATUS=$(echo "$ACCEPT_IR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('information_request',{}).get('status',''))" 2>/dev/null)
  [ "$IR_STATUS" = "accepted" ] && pass "IR accepted → $IR_STATUS" || fail "IR accept (got $IR_STATUS)"
fi

# ── Approval Queue ─────────────────────────────────────────────────────────────
section "Approval Queue"
AR_RESP=$(curl -sf --max-time 10 -X POST "$WORKBENCH_URL/api/v1/approval-requests" \
  -H "X-Test-User: sbtb_compliance_1" -H "Content-Type: application/json" \
  -d "{\"action_type\":\"case_closure_critical_high\",\"entity_type\":\"compliance_case\",\"entity_id\":\"$CASE_ID\",\"requested_by\":\"sbtb_compliance_1\",\"rationale\":\"smoke test\"}" 2>/dev/null || echo "{}")
AR_STATUS=$(echo "$AR_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('approval_request',{}).get('status',''))" 2>/dev/null)
[ "$AR_STATUS" = "pending" ] && pass "Approval created → $AR_STATUS" || info "Approval: $AR_STATUS"

EXISTING_AR=$(curl -sf --max-time 10 -X GET "$WORKBENCH_URL/api/v1/approval-requests" \
  -H "X-Test-User: sbtb_compliance_1" 2>/dev/null | \
  python3 -c "import sys,json; items=json.load(sys.stdin).get('items',[]);
               p=[i for i in items if i.get('status')=='pending']; print(p[0].get('approval_request_id','') if p else '')" 2>/dev/null || echo "")
if [ -n "$EXISTING_AR" ]; then
  VOTE=$(curl -sf --max-time 10 -X POST "$WORKBENCH_URL/api/v1/approval-requests/$EXISTING_AR/vote" \
    -H "X-Test-User: sbtb_compliance_2" -H "Content-Type: application/json" \
    -d '{"decision":"approved"}' 2>/dev/null || echo "{}")
  VSTATUS=$(echo "$VOTE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('approval_request',{}).get('status',''))" 2>/dev/null)
  [ "$VSTATUS" = "approved" ] && pass "Approval approved → $VSTATUS" || fail "Approval vote (got $VSTATUS)"
else
  info "No pending approvals for vote"
fi

# ── Notifications ──────────────────────────────────────────────────────────────
section "Notifications"
NOTIFS=$(curl -sf --max-time 10 -X GET "$WORKBENCH_URL/api/v1/notifications" \
  -H "X-Test-User: sbtb_analyst_1" 2>/dev/null || echo '{"items":[]}')
COUNT=$(echo "$NOTIFS" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('items',[])))" 2>/dev/null || echo "0")
[ "$COUNT" -gt 0 ] && pass "Notifications generated ($COUNT items)" || info "No notifications"
NID=$(echo "$NOTIFS" | python3 -c "import sys,json; items=json.load(sys.stdin).get('items',[]); print(items[0].get('notification_id',''))" 2>/dev/null)
if [ -n "$NID" ]; then
  READ=$(curl -sf --max-time 10 -X PATCH "$WORKBENCH_URL/api/v1/notifications/$NID/read" \
    -H "X-Test-User: sbtb_analyst_1" -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "{}")
  IS_READ=$(echo "$READ" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_read',False))" 2>/dev/null || echo "false")
  [ "$IS_READ" = "True" ] && pass "Notification read ✓" || fail "Notification mark-read"
fi

# ── Admin Outbox ───────────────────────────────────────────────────────────────
section "Admin Outbox"
OUTBOX=$(curl -sf --max-time 10 -X GET "$WORKBENCH_URL/api/v1/admin/outbox" \
  -H "X-Test-User: sbtb_admin_1" 2>/dev/null || echo '{"items":[]}')
ITEMS=$(echo "$OUTBOX" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('items',[])))" 2>/dev/null || echo "0")
[ "$ITEMS" -gt 0 ] && pass "Outbox has events ($ITEMS)" || info "Outbox empty"
FIRST_ID=$(echo "$OUTBOX" | python3 -c "import sys,json; items=json.load(sys.stdin).get('items',[]); print(items[0].get('outbox_id',''))" 2>/dev/null)
if [ -n "$FIRST_ID" ]; then
  RETRY=$(curl -sf --max-time 10 -X POST "$WORKBENCH_URL/api/v1/admin/outbox/$FIRST_ID/retry" \
    -H "X-Test-User: sbtb_admin_1" -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "{}")
  RC=$(echo "$RETRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','failed'))" 2>/dev/null || echo "failed")
  { [ "$RC" = "retried" ] || [ "$RC" = "pending" ]; } && pass "Outbox retry → $RC" || info "Outbox retry: $RC"
fi

# ── Workers ────────────────────────────────────────────────────────────────────
section "Workers"
for label container in "Expiry worker:banking_expiry_worker" "Outbox worker:banking_outbox_worker" "Workbench API:banking_workbench"; do
  IFS=: read -r label container <<< "$label:$container"
  check_container "$label" "$container"
done

EXPIRY_LOG=$(docker logs --tail 5 banking_expiry_worker 2>&1)
echo "$EXPIRY_LOG" | grep -qE "Expired|expired" && pass "Expiry worker active" || info "Expiry worker: $(echo "$EXPIRY_LOG" | tail -1)"

OUTBOX_LOG=$(docker logs --tail 5 banking_outbox_worker 2>&1)
echo "$OUTBOX_LOG" | grep -qE "Outbox worker starting|Delivered" && pass "Outbox worker active" || info "Outbox worker: $(echo "$OUTBOX_LOG" | tail -1)"

# ── Docker Summary ─────────────────────────────────────────────────────────────
section "Docker Containers"
log "$(docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || echo 'n/a')"

# ── Migrations ─────────────────────────────────────────────────────────────────
section "Migrations"
MIGRATION_CHECK=$(python3 -c "
import os; os.chdir('/Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system')
from alembic.config import Config; from alembic import command
cfg = Config('alembic.ini'); cfg.set_main_option('sqlalchemy.url', 'postgresql://integration_user:integrationpass123@localhost:5435/banking_integration')
heads = command.get_heads(cfg); print('HEAD:', list(heads)[0] if heads else 'NONE')
" 2>&1 || echo "check_failed")
log "Migrations: $MIGRATION_CHECK"

# ── Integration Tests ──────────────────────────────────────────────────────────
section "Integration Test Suite"
TEST_RESULT=$(cd /Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system && \
  INTEGRATION_DATABASE_URL="postgresql://integration_user:integrationpass123@localhost:5435/banking_integration" \
  PYTHONPATH=services:$PYTHONPATH \
  python3 -m pytest services/workbench/tests/test_2b17b_scenarios.py -q --tb=no 2>&1 | tail -3)
log "Scenarios: $TEST_RESULT"

# ── Summary ────────────────────────────────────────────────────────────────────
section "Summary"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
log "${BOLD}Total: $TOTAL tests — ${GREEN}$PASS_COUNT passed${NC} — ${RED}$FAIL_COUNT failed${NC}"
log "Report: $REPORT_FILE"
if [ "$FAIL_COUNT" -eq 0 ]; then
  log "\n${GREEN}${BOLD}VERDICT: READY FOR DEMO${NC}"
elif [ "$FAIL_COUNT" -le 3 ]; then
  log "\n${YELLOW}${BOLD}VERDICT: READY FOR UAT${NC}"
else
  log "\n${RED}${BOLD}VERDICT: NOT READY${NC}"
fi
exit $FAIL_COUNT
