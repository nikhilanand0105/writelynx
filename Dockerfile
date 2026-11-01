# ==============================================================================
# WRITELYNX MULTI-STAGE PRODUCTION DOCKERFILE
# Stage 1: Build production React + TypeScript static assets
# Stage 2: Production Python 3.11 runtime with LibreOffice, Poppler & Uvicorn
# ==============================================================================

FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python Backend Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LIBREOFFICE_PATH=/usr/bin/soffice \
    STORAGE_DIR=/app/storage

# Install headless LibreOffice, Poppler utilities, and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-calc \
    default-jre-headless \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Download required spaCy academic NLP model
RUN python -m spacy download en_core_web_sm

# Copy backend application and sample documents
COPY backend/ ./backend/
COPY sample_documents/ ./sample_documents/

# Copy compiled frontend production assets
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Pre-create private storage directories
RUN mkdir -p /app/storage/documents \
             /app/storage/quarantine \
             /app/storage/sources \
             /app/storage/exports \
             /app/storage/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
