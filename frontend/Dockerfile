FROM python:3.11-slim

WORKDIR /app

# Copy frontend files
COPY index.html .
COPY server.py .

# Expose port
EXPOSE 3000

# Run the frontend server
CMD ["python", "server.py"]
