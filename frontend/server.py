"""
Simple HTTP server for serving the frontend static files with backend proxy support.
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import urllib.request
import urllib.error
import json

# Backend configuration
BACKEND_HOST = os.getenv('BACKEND_HOST', 'localhost')
BACKEND_PORT = os.getenv('BACKEND_PORT', '8000')
BACKEND_URL = f'http://{BACKEND_HOST}:{BACKEND_PORT}'

class CORSRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with CORS support and backend proxy."""
    
    def end_headers(self):
        """
        Add CORS headers to all responses.
        WARNING: In production, restrict Access-Control-Allow-Origin to specific domains.
        This is configured for development/example purposes only.
        """
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Disable caching for HTML files to ensure fresh content
        if self.path.endswith('.html') or self.path == '/':
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        SimpleHTTPRequestHandler.end_headers(self)
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.end_headers()
    
    def proxy_to_backend(self, method='GET'):
        """Proxy requests to the backend API."""
        print(f"Proxying {method} {self.path} to {BACKEND_URL}{self.path}")
        try:
            # Read request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Build backend URL
            backend_path = self.path
            url = f'{BACKEND_URL}{backend_path}'
            
            # Create request
            headers = {'Content-Type': 'application/json'} if body else {}
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            
            # Make request to backend
            with urllib.request.urlopen(req, timeout=30) as response:
                response_body = response.read()
                
                # Send response back to client
                self.send_response(response.status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response_body)
                print(f"Successfully proxied to backend: {response.status}")
                
        except urllib.error.HTTPError as e:
            # Forward HTTP errors from backend
            print(f"Backend HTTP error: {e.code}")
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            # Handle connection errors
            print(f"Proxy error: {e}")
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({'error': f'Backend connection failed: {str(e)}'})
            self.wfile.write(error_response.encode())
    
    def do_GET(self):
        """Handle GET requests - proxy API calls, serve static files otherwise."""
        print(f"GET request for: {self.path}")
        # Check if this is an API endpoint
        path_without_query = self.path.split('?')[0]
        if (path_without_query == '/health' or 
            path_without_query.startswith('/documents') or 
            path_without_query.startswith('/query')):
            self.proxy_to_backend('GET')
        else:
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests - proxy to backend API."""
        print(f"POST request for: {self.path}")
        path_without_query = self.path.split('?')[0]
        if (path_without_query.startswith('/documents') or 
            path_without_query.startswith('/query')):
            self.proxy_to_backend('POST')
        else:
            self.send_error(404, "Not Found")


def run_server(port=3000):
    """Run the frontend server."""
    # Change to the frontend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    
    print(f"Frontend server running on http://localhost:{port}")
    print(f"Serving files from: {os.getcwd()}")
    print("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    run_server()
