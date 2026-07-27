#!/bin/bash
# Keycloak 1A.5 Validation Script
# Obtains real tokens and stores them for subsequent API calls

set -e

KEYCLOAK_URL="http://localhost:8080"
REALM="banking-intelligence"
CLIENT_ID="banking-portal-api"
API_URL="http://localhost:8000"

# Token storage
TOKENS_DIR="/tmp/keycloak-1a5-tokens"
mkdir -p "$TOKENS_DIR"

echo "=== Obtaining Keycloak tokens ==="

# Analyst token
echo "Obtaining analyst token..."
curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=$CLIENT_ID&username=kc_analyst_001&password=Analyst123!&scope=openid" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" \
  > "$TOKENS_DIR/analyst.token"

# Manager token
echo "Obtaining manager token..."
curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=$CLIENT_ID&username=kc_manager_001&password=Manager123!&scope=openid" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" \
  > "$TOKENS_DIR/manager.token"

# Compliance token
echo "Obtaining compliance token..."
curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=$CLIENT_ID&username=kc_compliance_001&password=Compliance123!&scope=openid" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" \
  > "$TOKENS_DIR/compliance.token"

# Admin token
echo "Obtaining admin token..."
curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=$CLIENT_ID&username=kc_admin_001&password=Admin123!&scope=openid" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" \
  > "$TOKENS_DIR/admin.token"

echo "=== Tokens stored in $TOKENS_DIR ==="
ls -la "$TOKENS_DIR"
