# BookBot Frontend

A static one-page chatbot UI for human-language book discovery.

The current frontend is intentionally self-contained:

- `index.html` renders the BookBot interface.
- `server.py` serves static files and reverse-proxies `/api/*` to the backend.
- Chat history is loaded from backend JSON storage, not browser local storage.

## Running

```bash
python3 server.py
# or
python3 start_frontend.py
```

Open:

```text
http://localhost:3000
```

## Backend API

The UI uses these routes:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/chats` | List shared chats |
| POST | `/api/chats` | Create a new chat |
| GET | `/api/chats/{chat_id}` | Load one chat with messages |
| PATCH | `/api/chats/{chat_id}` | Rename a chat |
| DELETE | `/api/chats/{chat_id}` | Delete a chat |
| POST | `/api/chats/{chat_id}/messages` | Send user text and receive assistant recommendations |

The backend can store this in one JSON file for now. No accounts are expected;
all users share the same chat list.
