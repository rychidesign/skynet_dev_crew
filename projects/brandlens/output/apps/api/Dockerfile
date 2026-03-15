FROM python:3.12-slim

WORKDIR /app

# Upgrade pip and install curl (for potential health checks)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip

# Install dependencies first (to leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway overrides this via $PORT at runtime, but we expose default 8000)
EXPOSE 8000

# Start Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
