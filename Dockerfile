# ==============================================================================
# WRITELYNX MULTI-STAGE PRODUCTION DOCKERFILE
# Stage 1: Build production React + TypeScript static assets
# Stage 2: Hardened Python 3.11 runtime (non-root, minimal headless LibreOffice)
# ==============================================================================

FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Python Backend Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LIBREOFFICE_PATH=/usr/bin/soffice \
    STORAGE_DIR=/app/storage

# Install headless LibreOffice Writer, Poppler utilities, and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root dedicated application user
RUN groupadd -g 1001 writelynx && \
    useradd -u 1001 -g writelynx -m -s /bin/bash writelynx

WORKDIR /app

# Install Python production requirements
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application source only (sample documents strictly excluded)
COPY backend/ ./backend/

# Copy compiled frontend production assets
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Pre-create private storage directories and assign ownership to non-root user
RUN mkdir -p /app/storage/documents \
             /app/storage/quarantine \
             /app/storage/sources \
             /app/storage/exports \
             /app/storage/reports && \
    chown -R writelynx:writelynx /app

USER writelynx

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
