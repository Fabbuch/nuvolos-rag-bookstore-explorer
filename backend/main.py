"""
Ultra minimal RAG backend server with pgvector integration.
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict
import json

app = FastAPI(title="RAG Backend API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ragdb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


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


class Query(BaseModel):
    query: str
    top_k: int = 3


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RAG Backend API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")


@app.post("/documents")
async def add_document(document: Document):
    """Add a document to the database with a simple embedding."""
    try:
        # Create a simple embedding (bag of words representation)
        # In a real application, you would use a proper embedding model
        embedding = create_simple_embedding(document.content)
        
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
        raise HTTPException(status_code=500, detail=f"Error adding document: {str(e)}")


@app.get("/documents")
async def list_documents():
    """List all documents in the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, content, created_at FROM documents ORDER BY id;")
        documents = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@app.post("/query")
async def query_documents(query: Query):
    """Query documents using vector similarity search."""
    try:
        # Create embedding for the query
        query_embedding = create_simple_embedding(query.query)
        
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
        raise HTTPException(status_code=500, detail=f"Error querying documents: {str(e)}")


def create_simple_embedding(text: str) -> str:
    """
    Create a simple embedding vector from text.
    This is a placeholder for demonstration. In production, use a proper embedding model.
    """
    # Simple character frequency based embedding (384 dimensions)
    embedding = [0.0] * 384
    
    # Normalize text
    text = text.lower()
    
    # Use character codes and position to create a simple embedding
    for i, char in enumerate(text[:384]):
        embedding[i] = (ord(char) % 256) / 256.0
    
    # Add some word-based features
    words = text.split()
    for i, word in enumerate(words[:192]):
        idx = (hash(word) % 192) + 192
        embedding[idx] = min(embedding[idx] + 0.1, 1.0)
    
    return "[" + ",".join(map(str, embedding)) + "]"


def generate_simple_answer(query: str, results: List[Dict]) -> str:
    """
    Generate a simple answer based on the query and retrieved documents.
    This is a placeholder for demonstration. In production, use an LLM.
    """
    if not results:
        return "I don't have enough information to answer this question."
    
    # Extract key terms from query
    query_words = set(query.lower().split())
    
    # Find the most relevant document
    best_match = results[0]
    
    return f"Based on the documents, here's what I found: {best_match['content'][:200]}..."


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
