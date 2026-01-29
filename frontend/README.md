# Frontend Server

This is a simple HTTP server for serving the frontend static files with built-in backend proxy support.

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

The frontend server acts as a reverse proxy to the backend API running on `localhost:8000`. This eliminates CORS issues and works seamlessly with dynamic session IDs in cloud environments.

**Environment Variables:**
- `BACKEND_HOST` (default: localhost) - Backend server host
- `BACKEND_PORT` (default: 8000) - Backend server port

Example:
```bash
BACKEND_HOST=localhost BACKEND_PORT=8000 python server.py
```

## How It Works

- Static files (HTML, JS, CSS) are served directly from the frontend directory
- API requests (`/health`, `/documents`, `/query`) are automatically proxied to the backend
- No URL configuration needed - works with changing session IDs in cloud environments

## Notes
- The server serves files from the current directory (where server.py is located).
- CORS is enabled for all origins for development. Restrict this in production if needed.
- To use a different port, modify the `run_server` call at the end of server.py.
