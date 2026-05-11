"""
Static frontend server for the BookBot UI.

This serves index.html and reverse-proxies /api requests to the backend, so
the browser can call same-origin URLs while the backend remains internal.
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
import urllib.error
import urllib.request


BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost:8500")
if not BACKEND_HOST.startswith("http"):
    BACKEND_HOST = f"http://{BACKEND_HOST}"


class StaticFileHandler(SimpleHTTPRequestHandler):
    """Serve static files and proxy API requests to the backend."""

    def end_headers(self):
        if self.path.endswith(".html") or self.path == "/":
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_PATCH(self):
        self.handle_request("PATCH")

    def do_DELETE(self):
        self.handle_request("DELETE")

    def handle_request(self, method):
        path_without_query = self.path.split("?")[0]
        if path_without_query.startswith("/api/"):
            self.proxy_to_backend(method)
            return

        if method != "GET":
            self.send_json(404, {"error": "Not found"})
            return

        if self.path == "/":
            self.path = "/index.html"

        super().do_GET()

    def proxy_to_backend(self, method):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            req = urllib.request.Request(f"{BACKEND_HOST}{self.path}", data=body, method=method)
            if "Content-Type" in self.headers:
                req.add_header("Content-Type", self.headers["Content-Type"])

            with urllib.request.urlopen(req) as response:
                response_body = response.read()
                self.send_response(response.status)
                for header, value in response.headers.items():
                    if header.lower() not in ["connection", "transfer-encoding"]:
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response_body)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_json(502, {"error": "Bad Gateway", "detail": str(e)})

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(port=None):
    """Run the frontend server."""
    if port is None:
        port = int(os.getenv("FRONTEND_PORT", "3000"))

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    server_address = ("", port)
    httpd = HTTPServer(server_address, StaticFileHandler)

    print(f"BookBot frontend running on http://localhost:{port}")
    print(f"Backend API: {BACKEND_HOST}")
    print(f"Serving files from: {os.getcwd()}")
    print("Press Ctrl+C to stop the server")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
