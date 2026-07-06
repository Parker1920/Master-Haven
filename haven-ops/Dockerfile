# ── Stage 1: build the frontend ─────────────────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: backend + built bundle, single serving container ───────────────
FROM python:3.12-slim

# WeasyPrint system libraries (Debian bookworm names). libharfbuzz-subset0 and
# libpangoft2 are hard runtime requirements of WeasyPrint >= 61 that pango's
# own deps don't always pull in; fonts-dejavu-core gives PDFs a real font on
# a slim image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libharfbuzz-subset0 \
        libffi-dev \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /build/dist ./static

# PYTHONUNBUFFERED so migrate/seed startup lines actually reach `docker logs`
ENV DATA_DIR=/data \
    PYTHONUNBUFFERED=1
EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
