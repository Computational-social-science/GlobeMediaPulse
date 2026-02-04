# Backend API
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for psycopg2, etc.)
RUN (sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list || true) && \
    (sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources || true) && \
    (sed -i 's|http://security.debian.org|https://security.debian.org|g' /etc/apt/sources.list || true) && \
    (sed -i 's|http://security.debian.org|https://security.debian.org|g' /etc/apt/sources.list.d/debian.sources || true) && \
    apt-get update -o Acquire::Retries=3 && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    git \
    curl \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend ./backend

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
