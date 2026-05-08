"""
Ultra minimal RAG backend server with pgvector integration.
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict
import json

from language_model import load_model, load_tokenizer, RAGSystem, sentence_transformers_embedding

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

# Load a Qwen model and tokenizer for generation.
QWEN_MODEL = load_model("ckpt-full")
QWEN_TOKENIZER = load_tokenizer("Qwen/Qwen1.5-0.5B")
RAG_SYSTEM = RAGSystem(
    QWEN_MODEL, 
    QWEN_TOKENIZER
    )

# Load an embedding model for creating vector embeddings.
EMB_MODEL = load_model("sentence-transformers/all-MiniLM-L6-v2")
EMB_TOKENIZER = load_tokenizer("sentence-transformers/all-MiniLM-L6-v2")

def get_db_connection():
    """Create a database connection."""
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
    top_k: int = 3
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v
    
    @validator('top_k')
    def validate_top_k(cls, v):
        if v < 1 or v > 100:
            raise ValueError('top_k must be between 1 and 100')
        return v
    
class DocumentList(BaseModel):
    documents: List[Document]


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
    conn = None
    try:
        # Create embedding for the query
        query_embedding = get_embedding(query.query)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Find similar documents using cosine similarity
        cur.execute(
            """
            SELECT id, content, 
                   1 - (embedding <=> %s::vector) as similarity
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_embedding, query_embedding, query.top_k)
        )
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Generate a simple RAG response
        if results:
            context = "\n\n".join([f"Document {r['id']}: {r['content']}" for r in results])
            response = f"Based on the retrieved documents:\n\n{context}\n\nAnswer: {generate_simple_answer(query.query, results)}"
        else:
            response = "No relevant documents found in the database."
        
        return {
            "query": query.query,
            "results": results,
            "response": response
        }
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error querying documents: {str(e)}")
    
@app.post("/generate")
async def generate(query: Query, documents: DocumentList):
    documents_strs = [doc.content for doc in documents.documents]
    response = RAG_SYSTEM.generate(query.query, documents_strs)
    return {"query": query.query, "response": response}

def get_embedding(text: str) -> str:
    """Create a sentence transformer embedding for the text."""
    embedding = sentence_transformers_embedding(EMB_MODEL, EMB_TOKENIZER, text)
    return "[" + ",".join(map(str, embedding)) + "]"


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8500"))
    uvicorn.run(app, host="0.0.0.0", port=port)
