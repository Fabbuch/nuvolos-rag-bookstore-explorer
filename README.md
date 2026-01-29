# nuvolos-examples-rag

An ultra minimal Retrieval Augmented Generation (RAG) example application with a frontend, backend, and pgvector database.

## Architecture

This application consists of three main components:

1. **Frontend Server** (Port 3000) - A simple web interface for interacting with the RAG system
2. **Backend API Server** (Port 8000) - FastAPI server handling document storage and RAG queries
3. **PostgreSQL Database** (Port 5432) - Database with pgvector extension for vector similarity search

## Features

- 📝 Add documents to the knowledge base
- 🔍 Query documents using vector similarity search
- 💬 Get AI-powered responses based on retrieved documents
- 🗄️ pgvector integration for efficient vector storage and retrieval

## Quick Start

### Using Setup Script (Easiest)

The easiest way to get started is using the provided setup script:

```bash
cd nuvolos-examples-rag
./setup.sh
```

This will:
1. Check database connectivity
2. Load sample documents if the database is empty
3. Start both backend and frontend servers

Access the application:
- Frontend UI: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

To stop and clean up:
```bash
./cleanup.sh
```

This will:
1. Stop all running servers
2. Remove all documents from the database
3. Clean up temporary files

### Using Docker Compose (Alternative)

1. Make sure you have Docker and Docker Compose installed

2. Start all services:
```bash
docker-compose up -d
```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

4. Stop all services:
```bash
docker-compose down
```

### Manual Setup

#### Prerequisites
- Python 3.11+
- PostgreSQL with pgvector extension

#### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables (or use defaults):
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=ragdb
export DB_USER=postgres
export DB_PASSWORD=postgres
```

4. Start the backend server:
```bash
python main.py
```

The backend will be available at http://localhost:8000

#### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Start the frontend server:
```bash
python server.py
```

The frontend will be available at http://localhost:3000

#### Database Setup

Install PostgreSQL with pgvector extension:

```bash
# Using Docker
docker run -d \
  --name rag-postgres \
  -e POSTGRES_DB=ragdb \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

## Usage

1. **Add Documents**: Use the "Add Document" form to add documents to your knowledge base
2. **Query Documents**: Enter a question in the "Query Documents" form
3. **View Results**: The system will retrieve relevant documents and generate a response
4. **Monitor Status**: Check the system status at the bottom of the page

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /documents` - Add a document
- `GET /documents` - List all documents
- `POST /query` - Query documents with RAG

## Technical Details

### Vector Embeddings

This example uses a simple embedding approach for demonstration purposes. In a production environment, you should replace the `create_simple_embedding()` function with a proper embedding model like:
- OpenAI's text-embedding models
- Sentence Transformers (e.g., all-MiniLM-L6-v2)
- Google's Universal Sentence Encoder

### RAG Response Generation

The current implementation uses a simple template-based response generation. For production use, integrate with an LLM API:
- OpenAI GPT models
- Anthropic Claude
- Google PaLM
- Open-source models via Hugging Face

## Development

### Project Structure

```
.
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   ├── index.html
│   └── server.py
├── docker-compose.yml
└── README.md
```

### Testing the API

You can test the API using curl:

```bash
# Health check
curl http://localhost:8000/health

# Add a document
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"content":"Python is a high-level programming language."}'

# Query documents
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is Python?","top_k":3}'
```

## License

MIT
