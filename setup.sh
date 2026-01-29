#!/bin/bash
# Setup script for RAG example application
# This script:
# 1. Checks database status
# 2. Loads sample data if database is empty
# 3. Starts both backend and frontend servers

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== RAG Application Setup ===${NC}\n"

# Database configuration from environment or defaults
DB_HOST="${DB_HOST:-nv-service-d54c9117d23473fa7f28948da0635011}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-nuvolos}"
DB_USER="${DB_USER:-nuvolos}"
DB_PASSWORD="${DB_PASSWORD:-nuvolos}"

# Backend configuration
BACKEND_HOST="${BACKEND_HOST:-localhost}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

# Frontend configuration
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Export for subprocesses
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
export BACKEND_HOST BACKEND_PORT

echo -e "${YELLOW}Step 1: Checking database connection...${NC}"
# Check if database is accessible
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database connection successful${NC}\n"
else
    echo -e "${RED}✗ Cannot connect to database${NC}"
    echo "Please ensure PostgreSQL is running and accessible at:"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    exit 1
fi

echo -e "${YELLOW}Step 2: Checking database status...${NC}"
# Check if documents table exists and has data
DOC_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*) FROM documents WHERE TRUE
    " 2>/dev/null | tr -d ' ' || echo "0")

echo "Current document count: $DOC_COUNT"

if [ "$DOC_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}Database is empty. Loading sample data...${NC}\n"
    
    echo -e "${YELLOW}Step 3: Reading sample data from CSV file...${NC}"
    # Path to sample data CSV file
    SAMPLE_FILE="$(dirname "$0")/sample_data.csv"
    
    # Check if CSV file exists
    if [ ! -f "$SAMPLE_FILE" ]; then
        echo -e "${RED}✗ Sample data file not found: $SAMPLE_FILE${NC}"
        echo "Please ensure sample_data.csv exists in the project directory"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Sample data file found${NC}\n"
    
    echo -e "${YELLOW}Step 4: Starting backend server (temporarily) to load data...${NC}"
    # Start backend in background
    cd backend
    python main.py > /tmp/backend_setup.log 2>&1 &
    BACKEND_PID=$!
    cd ..
    
    # Wait for backend to be ready
    echo "Waiting for backend to start..."
    for i in {1..30}; do
        if curl -s "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Backend is ready${NC}\n"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}✗ Backend failed to start within 30 seconds${NC}"
            kill $BACKEND_PID 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done
    
    echo -e "${YELLOW}Step 5: Loading documents into database...${NC}"
    # Read and load each document from CSV
    DOC_NUM=0
    # Skip header line and read CSV
    tail -n +2 "$SAMPLE_FILE" | while IFS=',' read -r id content; do
        # Remove quotes from content field (CSV format)
        content=$(echo "$content" | sed 's/^"//;s/"$//')
        
        if [ -n "$content" ]; then
            DOC_NUM=$((DOC_NUM + 1))
            # Escape quotes and backslashes for JSON
            ESCAPED_CONTENT=$(echo "$content" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
            
            # Add document via API
            RESPONSE=$(curl -s -X POST "http://$BACKEND_HOST:$BACKEND_PORT/documents" \
                -H "Content-Type: application/json" \
                -d "{\"content\": \"$ESCAPED_CONTENT\"}")
            
            if echo "$RESPONSE" | grep -q "\"id\""; then
                echo "  ✓ Loaded document $DOC_NUM"
            else
                echo "  ✗ Failed to load document $DOC_NUM: $RESPONSE"
            fi
        fi
    done
    
    # Count loaded documents (since subshell variable doesn't persist)
    DOC_NUM=$(tail -n +2 "$SAMPLE_FILE" | wc -l)
    
    echo -e "\n${GREEN}✓ Loaded $DOC_NUM documents successfully${NC}\n"
    
    # Stop the temporary backend
    kill $BACKEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    sleep 2
else
    echo -e "${GREEN}✓ Database already contains $DOC_COUNT documents${NC}\n"
fi

echo -e "${YELLOW}Step 6: Starting servers...${NC}"

# Start backend server
echo "Starting backend server on port $BACKEND_PORT..."
cd backend
python main.py > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/rag_backend.pid
cd ..

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend server started (PID: $BACKEND_PID)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Backend failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Start frontend server
echo "Starting frontend server on port $FRONTEND_PORT..."
cd frontend
python server.py > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/rag_frontend.pid
cd ..

# Wait a moment for frontend to start
sleep 2

if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${GREEN}✓ Frontend server started (PID: $FRONTEND_PID)${NC}\n"
else
    echo -e "${RED}✗ Frontend failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}=== Setup Complete! ===${NC}\n"
echo "Backend API: http://$BACKEND_HOST:$BACKEND_PORT"
echo "API Documentation: http://$BACKEND_HOST:$BACKEND_PORT/docs"
echo "Frontend UI: http://localhost:$FRONTEND_PORT"
echo ""
echo "Backend logs: tail -f /tmp/backend.log"
echo "Frontend logs: tail -f /tmp/frontend.log"
echo ""
echo "To stop the servers, run: ./cleanup.sh"
