# RAG Backend API

A FastAPI server that stores documents in PostgreSQL (with pgvector) and
exposes endpoints for adding, listing, and querying documents via vector
similarity search.

## Running

```bash
pip install -r requirements.txt
python main.py                   # starts on port 8500
# or
python start_backend.py          # daemonizes, saves PID for stop_backend.py
```

Interactive docs: http://localhost:8500/docs

## Summary of Endpoints

| Method | Path         | Description              |
|--------|-------------|--------------------------|
| GET    | `/`         | Root / status            |
| GET    | `/api/chats` | List shared chats from JSON history |
| POST   | `/api/chats` | Create a shared chat |
| GET    | `/api/chats/{chat_id}` | Load a shared chat |
| PATCH  | `/api/chats/{chat_id}` | Rename a shared chat |
| DELETE | `/api/chats/{chat_id}` | Delete a shared chat |
| POST   | `/api/chats/{chat_id}/messages` | Append a message to a shared chat |
| GET    | `/api/health`   | Health check (DB ping)   |
| POST   | `/api/documents`| Add a document           |
| GET    | `/api/documents`| List all documents       |

### Example Usage

- `/api/chats/{chat_id}/messages`:
```bash
curl -X POST http://<BACKEND_HOST>:8500/api/chats/5fb6d4c1-3662-4387-a761-10a0611ae0e7/messages \
  -H 'Content-Type: application/json' \
  -d '{"content": "What is a good romance book set in france?"}'
```

## Configuration

All settings come from environment variables (with sensible defaults):

| Env var       | Default                                        | Purpose              |
|--------------|------------------------------------------------|----------------------|
| `DB_HOST`    | `nv-service-d54c9117d23473fa7f28948da0635011`  | PostgreSQL hostname  |
| `DB_PORT`    | `5432`                                         | PostgreSQL port      |
| `DB_NAME`    | `nuvolos`                                      | Database name        |
| `DB_USER`    | `nuvolos`                                      | Database user        |
| `DB_PASSWORD`| `nuvolos`                                      | Database password    |
| `CHAT_HISTORY_FILE` | `backend/chat_history.json` | Shared chat history JSON file |

The default `DB_HOST` is a Nuvolos-assigned internal hostname. On the Nuvolos
internal network every pod gets a hostname like `nv-service-<hash>`, which
other pods on the same subnet can resolve — but nothing outside can.

## Network position

This backend is **not** exposed to the internet. The frontend server
reverse-proxies API requests to it over the Nuvolos internal network:

```
Browser ──► Frontend (port 3000) ──► this backend (port 8500) ──► PostgreSQL
            public-facing              internal only                internal only
```

CORS is set to `allow_origins=["*"]` because the frontend proxy makes the
requests server-side, not from a browser origin.
