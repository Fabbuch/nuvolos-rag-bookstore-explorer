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

# Environment variables for the generation and embedding models.
CHAT_MODEL_NAME = "qwen3:1.7b"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Embedding model configuration.
EMB_MODEL = ...
EMB_TOKENIZER = ...
GENERATOR = None


def build_rag_generator(system_prompt):
    """Build the Qwen chat generator used by /generate."""
    return RAGGenerator(
        base_model=CHAT_MODEL_NAME,
        model_name="rag-generator",
        system_prompt=system_prompt
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
    """Initialize the database with a chats table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create a chats table that stores (shared) chats
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                chat_id VARCHAR(255) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                messages JSONB NOT NULL
            );
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


def write_chat_history(chat):
    """Write a chat to the chats database table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()      
        # Insert the chat
        cur.execute("""
            INSERT INTO chats (chat_id, title, updated_at, messages)
            VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    updated_at = EXCLUDED.updated_at,
                    messages = EXCLUDED.messages;
            """, (chat["id"], chat["title"], chat["updatedAt"], json.dumps(chat["messages"])))      
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to connect to the database: {str(e)}")
    
def delete_chat_history(chat_id):
    """Delete a chat from the chats database table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()      
        # Delete the chat
        cur.execute("DELETE FROM chats WHERE chat_id = %s;", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to connect to the database: {str(e)}")


def get_chat_or_404(chat_id):
    """Helper to find a chat by id or raise 404."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id, title, updated_at, messages FROM chats WHERE chat_id = %s;", (chat_id,))
        chat = cur.fetchone()
        cur.close()
        conn.close()
        if not chat:
            raise HTTPException(status_code=404, detail=f"Chat with id {chat_id} not found")
        return {"id": chat[0], "title": chat[1], "updatedAt": chat[2], "messages": chat[3]}
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")


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
    """List all shared chats from the chats database table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT chat_id, title, updated_at, messages FROM chats ORDER BY updated_at DESC;")
        chats = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return [{"id": chat[0], "title": chat[1], "updatedAt": chat[2], "messages": chat[3]} for chat in chats]
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to connect to the database: {str(e)}")


@app.post("/api/chats")
async def create_chat(payload: ChatCreate | None = Body(default=None)):
    """Create an empty shared chat."""
    timestamp = now_iso()
    title = payload.title.strip() if payload and payload.title and payload.title.strip() else "New book search"
    new_chat = {
        "id": new_id(),
        "title": title,
        "updatedAt": timestamp,
        "messages": [],
    }
    write_chat_history(new_chat)
    return new_chat

@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str):
    """Load one shared chat."""
    return get_chat_or_404(chat_id)

@app.patch("/api/chats/{chat_id}")
async def rename_chat(chat_id: str, payload: ChatRename):
    """Rename one shared chat."""
    chat = get_chat_or_404(chat_id)
    chat["title"] = payload.title
    chat["updatedAt"] = now_iso()
    write_chat_history(chat)
    return chat


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete one shared chat."""
    get_chat_or_404(chat_id)
    delete_chat_history(chat_id)
    return {"deleted": True, "chatId": chat_id}


@app.post("/api/chats/{chat_id}/messages")
async def add_chat_message(chat_id: str, payload: ChatMessage):
    """Append a user message and a temporary assistant response."""
    chat = get_chat_or_404(chat_id)
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

    write_chat_history(chat)
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
    
    # Generate a response with the LLM using a prompt that incorporates the user question and the retrieved documents
    response = GENERATOR.generate(
        history=[],  # No conversation history for now
        query=query.query,
        retrieved_docs=documents_strs,
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
    # Initiliaze database and create tables if they don't exist.
    init_db()
    
    # Initialize LLM generator
    system_prompt = \
        "You are a helpful assistant for answering questions about books. Use the provided documents to answer the question as best as you can. If you don't know the answer, say you don't know."

    GENERATOR = build_rag_generator(system_prompt)

    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8500"))
    uvicorn.run(app, host="0.0.0.0", port=port)
