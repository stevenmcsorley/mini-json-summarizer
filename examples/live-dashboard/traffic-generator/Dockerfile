FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir httpx

# Copy generator script
COPY generator.py .

# Run generator
CMD ["python", "generator.py"]
