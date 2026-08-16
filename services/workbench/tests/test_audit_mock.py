"""Real HTTP Audit Agent mock for integration tests."""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import uuid
from datetime import datetime, timezone


class AuditMockHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Audit Agent mock."""
    
    received_events = []
    
    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Parse the request
        event = {
            'path': self.path,
            'method': self.command,
            'headers': dict(self.headers),
            'body': json.loads(body.decode('utf-8')),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        
        # Store the event
        AuditMockHandler.received_events.append(event)
        
        # Respond with success
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def reset_audit_mock():
    """Reset the audit mock's received events."""
    AuditMockHandler.received_events.clear()


def get_received_events():
    """Get the audit mock's received events."""
    return AuditMockHandler.received_events


def start_audit_mock(port=18008):
    """Start the audit mock server in a background thread."""
    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    try:
        server = ReusableHTTPServer(('0.0.0.0', port), AuditMockHandler)
    except OSError:
        # If server is already running on port, reuse existing
        return None, None

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread