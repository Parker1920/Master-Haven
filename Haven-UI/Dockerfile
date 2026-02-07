# ============================================================
# Haven Control Room — Dockerfile
# ============================================================
# This file tells Docker how to build a container image for Haven.
# Uses multi-stage build: Node.js builds frontend, Python runs backend.
# The final image only contains Python (no Node.js bloat).
# ============================================================

# ============================================================
# STAGE 1: Build Frontend
# ============================================================
FROM node:20-slim AS frontend-builder

WORKDIR /build

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source files needed for build
COPY src/ ./src/
COPY public/ ./public/
COPY index.html vite.config.js tailwind.config.js postcss.config.js ./

# Build the frontend
RUN npm run build

# ============================================================
# STAGE 2: Production Image
# ============================================================
FROM python:3.11-slim

# --- METADATA ---
LABEL maintainer="Parker1920"
LABEL description="Haven Control Room — Voyager's Haven community web app"

# --- WORKING DIRECTORY ---
WORKDIR /app

# --- INSTALL PYTHON DEPENDENCIES ---
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# --- COPY APPLICATION CODE ---
COPY . .

# --- COPY BUILT FRONTEND FROM STAGE 1 ---
# This overwrites any pre-built dist with freshly compiled version
COPY --from=frontend-builder /build/dist ./dist/

# --- EXPOSE PORT ---
EXPOSE 8005

# --- HEALTH CHECK ---
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/api/status')" || exit 1

# --- PERSISTENT DATA VOLUMES ---
RUN mkdir -p Haven-UI/data Haven-UI/photos

# --- START COMMAND ---
CMD ["python", "Haven-UI/server.py"]
