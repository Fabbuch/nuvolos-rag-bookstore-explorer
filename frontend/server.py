"""
Simple HTTP server for serving the frontend static files.
The frontend makes direct requests to the backend via its hostname.
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

# Backend configuration - will be injected into the HTML
BACKEND_HOST = os.getenv('BACKEND_HOST', 'http://localhost:8000')
if not BACKEND_HOST.startswith('http'):
    BACKEND_HOST = f'http://{BACKEND_HOST}'

class StaticFileHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for serving static files with backend URL injection."""
    
    def end_headers(self):
        """Add cache control headers for HTML files."""
        # Disable caching for HTML files to ensure fresh content
        if self.path.endswith('.html') or self.path == '/':
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        SimpleHTTPRequestHandler.end_headers(self)
    
    def do_GET(self):
        """Handle GET requests - serve static files with backend URL injection for HTML."""
        print(f"GET request for: {self.path}")
        
        # Handle root path
        if self.path == '/':
            self.path = '/index.html'
        
        # For HTML files, inject the backend URL
        if self.path.endswith('.html'):
            try:
                file_path = self.path.lstrip('/')
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Inject backend hostname into the HTML
                    content = content.replace('%BACKEND_HOST%', BACKEND_HOST)
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', len(content.encode('utf-8')))
                    self.end_headers()
                    self.wfile.write(content.encode('utf-8'))
                else:
                    self.send_error(404, "File not found")
            except Exception as e:
                print(f"Error serving HTML file: {e}")
                self.send_error(500, str(e))
        else:
            # For non-HTML files, serve normally
            super().do_GET()


def run_server(port=3000):
    """Run the frontend server."""
    # Change to the frontend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, StaticFileHandler)
    
    print(f"Frontend server running on http://localhost:{port}")
    print(f"Backend URL: {BACKEND_HOST}")
    print(f"Serving files from: {os.getcwd()}")
    print("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    run_server()
