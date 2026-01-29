#!/bin/bash
# Cleanup script for RAG example application
# This script:
# 1. Stops running servers
# 2. Restores database to initial state (removes all documents)

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== RAG Application Cleanup ===${NC}\n"

# Database configuration from environment or defaults
DB_HOST="${DB_HOST:-nv-service-d54c9117d23473fa7f28948da0635011}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-nuvolos}"
DB_USER="${DB_USER:-nuvolos}"
DB_PASSWORD="${DB_PASSWORD:-nuvolos}"

echo -e "${YELLOW}Step 1: Stopping servers...${NC}"

# Stop backend server
if [ -f /tmp/rag_backend.pid ]; then
    BACKEND_PID=$(cat /tmp/rag_backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo "Stopping backend server (PID: $BACKEND_PID)..."
        kill $BACKEND_PID
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        # Force kill if still running
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            kill -9 $BACKEND_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ Backend server stopped${NC}"
    else
        echo "Backend server is not running"
    fi
    rm -f /tmp/rag_backend.pid
else
    echo "No backend PID file found, checking for running processes..."
    # Try to find and kill backend process
    pkill -f "python.*main.py" 2>/dev/null && echo -e "${GREEN}✓ Backend server stopped${NC}" || echo "No backend server found"
fi

# Stop frontend server
if [ -f /tmp/rag_frontend.pid ]; then
    FRONTEND_PID=$(cat /tmp/rag_frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! ps -p $FRONTEND_PID > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        # Force kill if still running
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            kill -9 $FRONTEND_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ Frontend server stopped${NC}"
    else
        echo "Frontend server is not running"
    fi
    rm -f /tmp/rag_frontend.pid
else
    echo "No frontend PID file found, checking for running processes..."
    # Try to find and kill frontend process
    pkill -f "python.*frontend.*server.py" 2>/dev/null && echo -e "${GREEN}✓ Frontend server stopped${NC}" || echo "No frontend server found"
fi

echo ""
echo -e "${YELLOW}Step 2: Restoring database to initial state...${NC}"

# Check if database is accessible
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "Database connection successful"
    
    # Get current document count
    DOC_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT COUNT(*) FROM documents WHERE TRUE
        " 2>/dev/null | tr -d ' ' || echo "0")
    
    echo "Current documents in database: $DOC_COUNT"
    
    if [ "$DOC_COUNT" -gt 0 ]; then
        # Delete all documents
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
DELETE FROM documents;
EOF
        echo -e "${GREEN}✓ Deleted all documents from database${NC}"
    else
        echo "Database is already empty"
    fi
    
    # Optionally drop the table and index (uncomment if you want full cleanup)
    # PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
# DROP TABLE IF EXISTS documents CASCADE;
# EOF
    # echo -e "${GREEN}✓ Dropped documents table${NC}"
    
else
    echo -e "${RED}✗ Cannot connect to database${NC}"
    echo "Database cleanup skipped. Please check database connection."
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
fi

echo ""
echo -e "${YELLOW}Step 3: Cleaning up temporary files...${NC}"

# Remove log files
rm -f /tmp/backend.log /tmp/frontend.log /tmp/backend_setup.log
echo -e "${GREEN}✓ Removed log files${NC}"

echo ""
echo -e "${GREEN}=== Cleanup Complete! ===${NC}\n"
echo "All servers stopped and database restored to initial state."
echo "To start the application again, run: ./setup.sh"
