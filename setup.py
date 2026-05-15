#!/usr/bin/env python3
"""
Setup script for RAG example application
This script:
1. Checks database status
2. Loads sample data if database is empty
3. Starts both backend and frontend servers
"""

import os
import sys
import time
import csv
import json
import subprocess
import signal
import requests
import psycopg2
from pathlib import Path

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# Database configuration from environment or defaults
DB_HOST = os.getenv("DB_HOST", "nv-service-d54c9117d23473fa7f28948da0635011")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nuvolos")
DB_USER = os.getenv("DB_USER", "nuvolos")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nuvolos")

# Backend configuration
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8500")

# Ollama configuration
OLLAMA_MODELS = os.getenv("OLLAMA_MODELS", "/space_mounts/pars/ollama_models")

# Frontend configuration
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "3000")

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
BACKEND_DIR = SCRIPT_DIR / "backend"
FRONTEND_DIR = SCRIPT_DIR / "frontend"
PID_DIR = Path("/tmp")
OLLAMA_PID_FILE = PID_DIR / "ollama.pid"
BACKEND_PID_FILE = PID_DIR / "rag_backend.pid"
FRONTEND_PID_FILE = PID_DIR / "rag_frontend.pid"
BACKEND_LOG_FILE = PID_DIR / "backend.log"
FRONTEND_LOG_FILE = PID_DIR / "frontend.log"


def print_colored(color, message):
    """Print colored message."""
    print(f"{color}{message}{NC}")


def print_header(message):
    """Print section header."""
    print_colored(YELLOW, f"\n{message}")


def print_success(message):
    """Print success message."""
    print_colored(GREEN, f"✓ {message}")


def print_error(message):
    """Print error message."""
    print_colored(RED, f"✗ {message}")


def check_database_connection():
    """Check if database is accessible."""
    print_header("Step 1: Checking database connection...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.close()
        print_success("Database connection successful\n")
        return True
    except Exception as e:
        print_error("Cannot connect to database")
        print(f"Error: {e}")
        print("Please ensure PostgreSQL is running and accessible at:")
        print(f"  Host: {DB_HOST}")
        print(f"  Port: {DB_PORT}")
        print(f"  Database: {DB_NAME}")
        print(f"  User: {DB_USER}")
        return False


def get_document_count():
    """Get the number of documents in the database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception as e:
        # Table might not exist yet
        return 0


def wait_for_backend(timeout=30):
    """Wait for backend to be ready."""
    print("Waiting for backend to be ready...")
    backend_url = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/health"
    
    for i in range(timeout):
        try:
            response = requests.get(backend_url, timeout=1)
            if response.status_code == 200:
                print_success("Backend is ready\n")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    
    print_error(f"Backend failed to start within {timeout} seconds")
    return False


def start_servers():
    """Start both backend and frontend servers."""
    print_header("Step 6: Starting servers...")
    
    print(f"Starting backend server on port {BACKEND_PORT}...")
    backend_log = open(BACKEND_LOG_FILE, 'w')
    
    # Start ollama server
    ollama_process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        env={**os.environ, **{
            "OLLAMA_MODELS": OLLAMA_MODELS
        }}
    )
    
    # Start backend server
    backend_process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=BACKEND_DIR,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        env={**os.environ, **{
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "DB_NAME": DB_NAME,
            "DB_USER": DB_USER,
            "DB_PASSWORD": DB_PASSWORD
        }}
    )
    
    # Save PID for ollama
    OLLAMA_PID_FILE.write_text(str(ollama_process.pid))
    # Save PID for backend
    BACKEND_PID_FILE.write_text(str(backend_process.pid))
    
    print_success(f"Ollama server started (PID: {ollama_process.pid})")
    print_success(f"Backend server started (PID: {backend_process.pid})")
    
    # Wait for backend to be ready
    if not wait_for_backend():
        return False
    
    # Start frontend server
    print(f"Starting frontend server on port {FRONTEND_PORT}...")
    frontend_log = open(FRONTEND_LOG_FILE, 'w')
    frontend_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=FRONTEND_DIR,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        env=os.environ.copy()
    )
    
    # Save PID
    FRONTEND_PID_FILE.write_text(str(frontend_process.pid))
    
    # Wait a moment for frontend to start
    time.sleep(2)
    
    # Check if frontend is still running
    if frontend_process.poll() is None:
        print_success(f"Frontend server started (PID: {frontend_process.pid})\n")
    else:
        print_error("Frontend failed to start")
        return False
    
    return True


def main():
    """Main setup function."""
    print_colored(GREEN, "=== RAG Application Setup ===\n")
    
    # Step 1: Check database connection
    if not check_database_connection():
        sys.exit(1)
    
    # Step 2: Check database status
    print_header("Step 2: Checking database status...")
    doc_count = get_document_count()
    print(f"Current document count: {doc_count}")
    
    # Step 3: Start servers
    if not start_servers():
        sys.exit(1)
    
    # Success message
    print_colored(GREEN, "\n=== Setup Complete! ===\n")
    print(f"Backend API: http://{BACKEND_HOST}:{BACKEND_PORT}")
    print(f"API Documentation: http://{BACKEND_HOST}:{BACKEND_PORT}/docs")
    print(f"Frontend UI: http://localhost:{FRONTEND_PORT}")
    print()
    print(f"Backend logs: tail -f {BACKEND_LOG_FILE}")
    print(f"Frontend logs: tail -f {FRONTEND_LOG_FILE}")
    print()
    print("To stop the servers, run: python3 cleanup.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
