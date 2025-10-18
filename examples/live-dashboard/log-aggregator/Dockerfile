FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0

# Copy server code
COPY server.py .

# Expose port
EXPOSE 9880

# Run server
CMD ["python", "server.py"]
