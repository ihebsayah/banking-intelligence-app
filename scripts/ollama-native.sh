#!/bin/bash
# scripts/ollama-native.sh
# Development helper: verify the NATIVE macOS Ollama runtime that the banking
# stack expects, and confirm the configured Insights model is present.
#
# It only CHECKS — it never installs or downloads models automatically.
#
# Usage:
#   scripts/ollama-native.sh          # check host + Docker-reachable endpoint
#   scripts/ollama-native.sh --start  # also start native Ollama if not running

set -euo pipefail
cd "$(dirname "$0")/.."

START=0
if [[ "${1:-}" == "--start" ]]; then
    START=1
fi

MODEL="${INSIGHTS_LLM_MODEL:-mistral}"

echo "== Native Ollama binary =="
if ! command -v ollama >/dev/null 2>&1; then
    echo "ERROR: 'ollama' not found on PATH."
    echo "  Install native macOS Ollama (https://ollama.com or `brew install ollama`),"
    echo "  then re-run this helper."
    exit 1
fi
OBIN="$(command -v ollama)"
echo "  binary: $OBIN"
VERSION="$(ollama --version 2>/dev/null || echo 'n/a')"
echo "  version: $VERSION"

echo
echo "== Native Ollama server (localhost:11434) =="
if curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  server: UP"
else
    echo "  server: DOWN"
    if [ "$START" -eq 1 ]; then
        echo "  starting native Ollama (OLLAMA_HOST=0.0.0.0:11434) ..."
        nohup env OLLAMA_HOST=0.0.0.0:11434 ollama serve >/tmp/native_ollama.log 2>&1 &
        sleep 4
        curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1 \
            && echo "  server: UP (started)" || { echo "  ERROR: still down"; exit 1; }
    else
        echo "  hint: start it with:  scripts/ollama-native.sh --start"
    fi
fi

echo
echo "== Model check (INSIGHTS_LLM_MODEL=${MODEL}) =="
FOUND="$(curl -s --max-time 5 "http://localhost:11434/api/tags" | python3 -c "import sys,json; d=json.load(sys.stdin); print([m['name'] for m in d.get('models',[])] if 'models' in d else [])" 2>/dev/null || echo '[]')"
if echo "$FOUND" | grep -q "$MODEL"; then
    echo "  model '$MODEL' present: YES"
else
    echo "  model '$MODEL' present: NO  (available: $FOUND)"
    echo "  pull it with:  ollama pull $MODEL"
fi

echo
echo "== Docker-reachable endpoint (host.docker.internal:11434) =="
# host.docker.internal only resolves INSIDE a container, so test from a
# lightweight running container if one exists (e.g. the orchestrator).
CONTAINERS="$(docker ps --format '{{.Names}}' 2>/dev/null || true)"
TEST_CTN=""
for c in banking_orchestrator banking_sql_agent banking_api_gateway; do
    if echo "$CONTAINERS" | grep -qx "$c"; then TEST_CTN="$c"; break; fi
done
if [ -n "$TEST_CTN" ]; then
    if docker exec "$TEST_CTN" python3 -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5)" >/dev/null 2>&1; then
        echo "  reachable from Docker (via $TEST_CTN): YES (container -> host native Ollama)"
    else
        echo "  reachable from Docker (via $TEST_CTN): NO"
        echo "  hint: Ollama must bind 0.0.0.0 (OLLAMA_HOST=0.0.0.0:11434) for Docker Desktop."
    fi
else
    echo "  container check skipped (no running banking container found)"
fi
