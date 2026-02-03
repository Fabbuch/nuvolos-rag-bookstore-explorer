# Frontend Server

This is a simple HTTP server for serving the frontend static files. The frontend makes direct requests to the backend API using its hostname.

## Requirements

- Python 3.7+

## Running the Frontend

1. Open a terminal and navigate to this directory:
   ```bash
   cd frontend
   ```
2. Start the server:
   ```bash
   python server.py
   ```
   By default, the server runs on port 3000.

3. Open your browser and go to:
   - http://localhost:3000 (local development)
   - Or use your cloud provider's URL (e.g., Nuvolos application URL)

## Backend Configuration

The frontend server injects the backend URL into the HTML at runtime. Set the backend hostname using environment variables:

**Environment Variables:**
- `BACKEND_HOST` (default: http://localhost:8000) - Full URL to the backend API server

Example:
```bash
BACKEND_HOST=http://backend.example.com python server.py
```

Or for cloud environments with separate service hostnames:
```bash
BACKEND_HOST=http://nv-service-abc123.nuvolos.cloud python server.py
```

## How It Works

- Static files (HTML, JS, CSS) are served directly from the frontend directory
- The `BACKEND_HOST` environment variable is injected into HTML files at request time
- Frontend JavaScript makes direct fetch() calls to the backend API
- CORS headers in the backend allow cross-origin requests from the frontend

## Notes
- The server serves files from the current directory (where server.py is located).
- The backend URL is dynamically injected, making it easy to configure for different environments.
- To use a different port, modify the `run_server` call at the end of server.py.
