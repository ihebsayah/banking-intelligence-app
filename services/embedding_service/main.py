"""
services/embedding_service/main.py
Embedding Service stub — Schema vector computation — Week 2.
Full implementation comes in its scheduled week.
Port: 8009
"""
import sys
sys.path.insert(0, "/app"); sys.path.insert(0, "/app/shared")

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 8009))


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({
                "status": "healthy",
                "service": "embedding_service",
                "note": "Schema vector computation — Week 2"
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(content_length)
        body = json.dumps({"status": "not_implemented", "service": "embedding_service", "note": "Schema vector computation — Week 2"}).encode()
        self.send_response(501)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"[embedding_service] Stub server starting on port {PORT}")
    server = HTTPServer((HOST, PORT), HealthHandler)
    server.serve_forever()
