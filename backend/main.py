"""
Ultra minimal RAG backend server with pgvector integration.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import List, Dict
import json

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_IMPORT_ERROR = None
except Exception as e:
    psycopg2 = None
    RealDictCursor = None
    PSYCOPG2_IMPORT_ERROR = e

from language_model import load_model, load_tokenizer, RAGGenerator, sentence_transformers_embedding
from vllm import SamplingParams

app = FastAPI(title="RAG Backend API")

# Enable CORS for the frontend reverse proxy.
# The frontend server (not the browser) makes requests to this backend,
# so "*" is acceptable here — no browser ever talks to this host directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection.
# DB_HOST is the internal hostname Nuvolos assigns to the PostgreSQL pod.
# It is only reachable from other pods on the same Nuvolos-managed subnet.
DB_HOST = os.getenv("DB_HOST", "nv-service-d54c9117d23473fa7f28948da0635011")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nuvolos")
DB_USER = os.getenv("DB_USER", "nuvolos")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nuvolos")
CHAT_HISTORY_FILE = Path(os.getenv("CHAT_HISTORY_FILE", Path(__file__).with_name("chat_history.json")))

# Environment variables for vllm and huggingface cache directories.
VLLM_CACHE_ROOT=os.getenv("VLLM_CACHE_ROOT", "space_mounts/pars/vllm_cache")
DOWNLOAD_DIR=os.getenv("DOWNLOAD_DIR", "space_mounts/pars/hf_cache")
CHAT_MODEL_NAME = "Qwen/Qwen1.5-0.5B-Chat"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Embedding model configuration.
# TODO: Find a vllm alternative to this if possible.
EMB_MODEL = load_model(EMBEDDING_MODEL_NAME)
EMB_TOKENIZER = load_tokenizer(EMBEDDING_MODEL_NAME)
GENERATOR = None


def build_rag_generator(system_prompt):
    """Build the Qwen chat generator used by /generate."""
    return RAGGenerator(
        model_name=CHAT_MODEL_NAME,
        system_prompt=system_prompt,
        download_dir=DOWNLOAD_DIR,
    )

def get_db_connection():
    """Create a database connection."""
    if PSYCOPG2_IMPORT_ERROR:
        raise RuntimeError(f"PostgreSQL driver unavailable: {PSYCOPG2_IMPORT_ERROR}")
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )


def init_db():
    """Initialize the database with pgvector extension and create tables."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Enable pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Create documents table with vector embeddings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(384),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create index for vector similarity search
        # Using HNSW index for better performance with small datasets
        # Note: For very small datasets (<1000 rows), sequential scan might be faster
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx 
            ON documents USING hnsw (embedding vector_cosine_ops);
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")


### Pydantic model definitions for request validation.
class Document(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError('Content cannot be empty')
        if len(v) > 10000:  # 10KB limit
            raise ValueError('Content exceeds maximum length of 10000 characters')
        return v


class Query(BaseModel):
    query: str
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v
    
class DocumentList(BaseModel):
    documents: List[Document]


class ChatCreate(BaseModel):
    title: str | None = None


class ChatRename(BaseModel):
    title: str

    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()


class ChatMessage(BaseModel):
    content: str

    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()


def now_iso():
    """Return a frontend-friendly UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id():
    """Create a stable JSON-friendly id."""
    return str(uuid4())


def make_chat_title(text):
    """Use the first few words as a readable default title."""
    words = text.strip().split()
    title = " ".join(words[:7])
    return f"{title}..." if len(words) > 7 else title


def read_chat_history():
    """Read all chats from one JSON file."""
    if not CHAT_HISTORY_FILE.exists():
        return []

    with CHAT_HISTORY_FILE.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []

    if isinstance(data, dict):
        return data.get("chats", [])
    if isinstance(data, list):
        return data
    return []


def write_chat_history(chats):
    """Persist all chats atomically enough for this small demo."""
    CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = CHAT_HISTORY_FILE.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(chats, f, indent=2)
    tmp_file.replace(CHAT_HISTORY_FILE)


def sort_chats(chats):
    return sorted(chats, key=lambda chat: chat.get("updatedAt", ""), reverse=True)


def get_chat_or_404(chats, chat_id):
    for chat in chats:
        if chat.get("id") == chat_id:
            return chat
    raise HTTPException(status_code=404, detail="Chat not found")


def create_placeholder_assistant_message():
    """Temporary assistant reply until the RAG recommendation endpoint is connected."""
    return {
        "id": new_id(),
        "role": "assistant",
        "content": "I saved your request. Book recommendations are not connected yet.",
        "recommendations": [],
        "createdAt": now_iso(),
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RAG Backend API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")


@app.get("/api/chats")
async def list_chats():
    """List all shared chats from the JSON history file."""
    return sort_chats(read_chat_history())


@app.post("/api/chats")
async def create_chat(payload: ChatCreate | None = Body(default=None)):
    """Create an empty shared chat."""
    timestamp = now_iso()
    title = payload.title.strip() if payload and payload.title and payload.title.strip() else "New book search"
    chat = {
        "id": new_id(),
        "title": title,
        "updatedAt": timestamp,
        "messages": [],
    }
    chats = [chat, *read_chat_history()]
    write_chat_history(sort_chats(chats))
    return chat


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str):
    """Load one shared chat."""
    chats = read_chat_history()
    return get_chat_or_404(chats, chat_id)


@app.patch("/api/chats/{chat_id}")
async def rename_chat(chat_id: str, payload: ChatRename):
    """Rename one shared chat."""
    chats = read_chat_history()
    chat = get_chat_or_404(chats, chat_id)
    chat["title"] = payload.title
    chat["updatedAt"] = now_iso()
    write_chat_history(sort_chats(chats))
    return chat


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete one shared chat."""
    chats = read_chat_history()
    get_chat_or_404(chats, chat_id)
    write_chat_history([chat for chat in chats if chat.get("id") != chat_id])
    return {"deleted": True, "chatId": chat_id}


@app.post("/api/chats/{chat_id}/messages")
async def add_chat_message(chat_id: str, payload: ChatMessage):
    """Append a user message and a temporary assistant response."""
    chats = read_chat_history()
    chat = get_chat_or_404(chats, chat_id)
    timestamp = now_iso()
    has_user_message = any(message.get("role") == "user" for message in chat.get("messages", []))

    user_message = {
        "id": new_id(),
        "role": "user",
        "content": payload.content,
        "createdAt": timestamp,
    }

    chat.setdefault("messages", []).extend([
        user_message,
        create_placeholder_assistant_message(),
    ])
    if not has_user_message or chat.get("title") == "New book search":
        chat["title"] = make_chat_title(payload.content)
    chat["updatedAt"] = now_iso()

    write_chat_history(sort_chats(chats))
    return chat


@app.post("/documents")
async def add_document(document: Document):
    """Add a document to the database with a simple embedding."""
    conn = None
    try:
        embedding = get_embedding(document.content)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO documents (content, embedding) VALUES (%s, %s) RETURNING id;",
            (document.content, embedding)
        )
        doc_id = cur.fetchone()["id"]
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"id": doc_id, "message": "Document added successfully"}
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error adding document: {str(e)}")


@app.get("/documents")
async def list_documents():
    """List all documents in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, content, created_at FROM documents ORDER BY id;")
        documents = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {"documents": documents}
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@app.post("/query")
async def query_documents(query: Query):
    """Query documents using vector similarity search."""
    # TODO: Implement this.
    
@app.post("/generate")
async def generate(query: Query, documents: DocumentList):
    """Generate an LLM response from a query and a list of retrieved documents."""
    global GENERATOR

    # Get document contents as a list of strings
    documents_strs = [doc.content for doc in documents.documents]
    
    # Further sampling parameters such as temperature, top_p etc. can be added here.
    sampling_params=SamplingParams(
        max_tokens=512,
        )
    
    # Generate a response with the LLM using a prompt that incorporates the user question and the retrieved documents
    response = GENERATOR.generate(
        history=[],  # No conversation history for now
        query=query.query,
        retrieved_docs=documents_strs,
        sampling_params=sampling_params
    )
    
    return {
        "query": query.query,
        "documents": documents.documents,
        "output": response
        }

def get_embedding(text: str) -> str:
    """Create a sentence transformer embedding for the text."""
    embedding = sentence_transformers_embedding(EMB_MODEL, EMB_TOKENIZER, text)
    return "[" + ",".join(map(str, embedding)) + "]"


if __name__ == "__main__":
    # Initialize LLM generator
    system_prompt = \
        "You are a helpful assistant for answering questions about books. Use the provided documents to answer the question as best as you can. If you don't know the answer, say you don't know."

    GENERATOR = RAGGenerator(
        model_name=CHAT_MODEL_NAME,
        system_prompt=system_prompt,
        download_dir=DOWNLOAD_DIR,
    )

    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8500"))
    uvicorn.run(app, host="0.0.0.0", port=port)
