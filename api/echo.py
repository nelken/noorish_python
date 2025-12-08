import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        content = ""
        try:
            data = json.loads(body.decode("utf-8"))
            content = data.get("content", "")
        except json.JSONDecodeError:
            content = ""

        self._set_headers(200)
        self.wfile.write(json.dumps({"content": content}).encode("utf-8"))
