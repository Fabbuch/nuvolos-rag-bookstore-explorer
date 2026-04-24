# Frontend Server

A Python HTTP server that does two things:

1. **Serves static files** (`index.html`) to the browser.
2. **Reverse-proxies API requests** to the backend over the Nuvolos internal network.

## Why a reverse proxy?

The backend runs on an internal hostname that only Nuvolos pods can reach.
The browser (on the public internet) can't resolve that hostname, so this
server accepts the browser's request and forwards it to the backend.

```
Browser ──► Nuvolos VS Code proxy ──► this server (:3000) ──► backend (:8500)
                                        serves HTML             internal only
                                        proxies /documents,
                                        /query, /health
```

## Running

```bash
python server.py
# or
python start_frontend.py   # daemonizes, saves PID for stop_frontend.py
```

## Configuration

| Env var        | Default                           | Purpose                          |
|---------------|-----------------------------------|----------------------------------|
| `BACKEND_HOST`| `http://<your_hostname>:8500`     | Internal URL of the backend pod  |

## Proxied API paths

| Path          | Method(s)    | Forwarded to backend |
|--------------|-------------|----------------------|
| `/health`    | GET         | Yes                  |
| `/documents` | GET, POST   | Yes                  |
| `/query`     | POST        | Yes                  |

Everything else is served as a static file from this directory.
