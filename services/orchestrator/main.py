"""
services/orchestrator/main.py
Orchestrator Agent stub — Week 2 implementation.

Currently: starts a minimal HTTP server that responds to /health.
Week 2+: will coordinate the full 8-agent pipeline using Claude.
"""
import sys
sys.path.insert(0, "/app"); sys.path.insert(0, "/app/shared")

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 8001))


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access logs

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "healthy", "service": "orchestrator-agent", "week": 1, "note": "Full implementation in Week 2"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    print(f"[orchestrator-agent] Stub server starting on port {PORT}")
    server = HTTPServer((HOST, PORT), HealthHandler)
    server.serve_forever()
