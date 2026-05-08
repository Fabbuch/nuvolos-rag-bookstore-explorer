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

# Environment variables for vllm and huggingface cache directories.
VLLM_CACHE_ROOT=os.getenv("VLLM_CACHE_ROOT", "space_mounts/pars/vllm_cache")
DOWNLOAD_DIR=os.getenv("DOWNLOAD_DIR", "space_mounts/pars/hf_cache")

# Embedding model configuration.
# TODO: Find a vllm alternative to this if possible.
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
    # TODO: Implement this.
    
@app.post("/generate")
async def generate(query: Query, documents: DocumentList):
    """Generate an LLM response from a query and a list of retrieved documents."""
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
        model_name="Qwen/Qwen1.5-0.5B-Chat",
        system_prompt=system_prompt,
        download_dir=DOWNLOAD_DIR,
        )
    
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8500"))
    uvicorn.run(app, host="0.0.0.0", port=port)
