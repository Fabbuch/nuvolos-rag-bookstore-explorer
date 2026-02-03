#!/usr/bin/env python3
"""
Cleanup script for RAG example application
This script:
1. Stops running servers
2. Restores database to initial state (removes all documents)
"""

import os
import sys
import time
import signal
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

# Paths
PID_DIR = Path("/tmp")
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


def stop_process(pid_file, process_name):
    """Stop a process given its PID file."""
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            print(f"Stopping {process_name} (PID: {pid})...")
            
            # Check if process exists
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
            except OSError:
                print(f"{process_name} is not running")
                pid_file.unlink()
                return
            
            # Try graceful shutdown first
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            
            # Wait for graceful shutdown
            for i in range(10):
                try:
                    os.kill(pid, 0)
                    time.sleep(1)
                except OSError:
                    # Process is dead
                    break
            
            # Force kill if still running
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            
            print_success(f"{process_name} stopped")
            pid_file.unlink()
            
        except (ValueError, FileNotFoundError) as e:
            print(f"Error reading PID file: {e}")
    else:
        print(f"No {process_name} PID file found")


def cleanup_database():
    """Clean up database by removing all documents."""
    print_header("Step 2: Restoring database to initial state...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Get current document count
        cur.execute("SELECT COUNT(*) FROM documents")
        count = cur.fetchone()[0]
        print(f"Current documents in database: {count}")
        
        if count > 0:
            # Delete all documents
            cur.execute("DELETE FROM documents")
            conn.commit()
            print_success("Deleted all documents from database")
        else:
            print("Database is already empty")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print_error("Cannot connect to database")
        print(f"Error: {e}")
        print("Database cleanup skipped. Please check database connection.")
        print(f"  Host: {DB_HOST}")
        print(f"  Port: {DB_PORT}")
        print(f"  Database: {DB_NAME}")
        print(f"  User: {DB_USER}")


def cleanup_files():
    """Clean up temporary files."""
    print_header("Step 3: Cleaning up temporary files...")
    
    # Remove log files
    for log_file in [BACKEND_LOG_FILE, FRONTEND_LOG_FILE]:
        if log_file.exists():
            log_file.unlink()
    
    print_success("Removed log files")


def main():
    """Main cleanup function."""
    print_colored(YELLOW, "=== RAG Application Cleanup ===\n")
    
    # Step 1: Stop servers
    print_header("Step 1: Stopping servers...")
    stop_process(BACKEND_PID_FILE, "backend server")
    stop_process(FRONTEND_PID_FILE, "frontend server")
    
    # Step 2: Clean database
    cleanup_database()
    
    # Step 3: Clean up files
    cleanup_files()
    
    # Success message
    print_colored(GREEN, "\n=== Cleanup Complete! ===\n")
    print("All servers stopped and database restored to initial state.")
    print("To start the application again, run: python3 setup.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
