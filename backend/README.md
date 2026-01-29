# RAG Backend API

This is an ultra-minimal Retrieval-Augmented Generation (RAG) backend server with pgvector integration, built using FastAPI and PostgreSQL.

## Requirements

- Python 3.8+
- PostgreSQL server with pgvector extension

## Installation

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database connection:**

   The backend uses the following environment variables (with defaults):

   - `DB_HOST` (default: nv-service-d54c9117d23473fa7f28948da0635011)
   - `DB_PORT` (default: 5432)
   - `DB_NAME` (default: nuvolos)
   - `DB_USER` (default: nuvolos)
   - `DB_PASSWORD` (default: nuvolos)

   You can set these in your shell or a `.env` file.

## Running the Backend

Start the FastAPI server using Uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- The API will be available at: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

## Notes
- CORS is enabled for all origins for development. Restrict this in production.
- Ensure your PostgreSQL server is running and accessible with the configured credentials.

