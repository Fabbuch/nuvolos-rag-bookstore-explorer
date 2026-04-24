#!/usr/bin/env python3
"""
Startup script for RAG frontend server
This script:
1. Starts the frontend server
2. Saves PID for later teardown
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# Frontend configuration
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "3000")
BACKEND_HOST = os.getenv("BACKEND_HOST", "nv-service-8274117e85103f8c55c6f267d3e4eb1f:8500")

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PID_DIR = Path("/tmp")
FRONTEND_PID_FILE = PID_DIR / "rag_frontend.pid"
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


def check_if_running():
    """Check if frontend is already running."""
    if FRONTEND_PID_FILE.exists():
        try:
            pid = int(FRONTEND_PID_FILE.read_text().strip())
            # Check if process is actually running
            os.kill(pid, 0)
            print_error(f"Frontend server is already running (PID: {pid})")
            print(f"To stop it, run: python3 stop_frontend.py")
            return True
        except (OSError, ValueError):
            # Process not running, clean up stale PID file
            FRONTEND_PID_FILE.unlink()
    return False


def start_frontend():
    """Start the frontend server."""
    print_header("Starting frontend server...")
    
    # Create log file
    frontend_log = open(FRONTEND_LOG_FILE, 'w')
    
    # Start frontend server
    frontend_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=SCRIPT_DIR,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        env={**os.environ, **{
            "BACKEND_HOST": BACKEND_HOST
        }}
    )
    
    # Save PID
    FRONTEND_PID_FILE.write_text(str(frontend_process.pid))
    
    print_success(f"Frontend server started (PID: {frontend_process.pid})")
    print(f"Running on port {FRONTEND_PORT}")
    print()
    print(f"Logs: tail -f {FRONTEND_LOG_FILE}")
    
    # Wait a moment to check if process starts successfully
    time.sleep(2)
    
    if frontend_process.poll() is not None:
        print_error("Frontend server failed to start")
        print(f"Check logs at: {FRONTEND_LOG_FILE}")
        return False
    
    return True


def main():
    """Main startup function."""
    print_colored(GREEN, "=== RAG Frontend Startup ===\n")
    
    # Check if already running
    if check_if_running():
        sys.exit(1)
    
    # Start frontend server
    if not start_frontend():
        sys.exit(1)
    
    # Success message
    print_colored(GREEN, "\n=== Frontend Started! ===\n")
    print(f"Frontend UI: http://localhost:{FRONTEND_PORT}")
    print(f"Backend API: https://{BACKEND_HOST}")
    print()
    print("To stop the server, run: python3 stop_frontend.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStartup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
