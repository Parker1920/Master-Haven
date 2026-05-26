# ============================================================
# Stage 1: Build the React frontend
# ============================================================
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Python backend with the built frontend bundled in
# ============================================================
FROM python:3.11-slim AS runtime
WORKDIR /app

# System deps: Pillow (jpeg/webp/zlib) + CA certs for outbound HTTPS
# (the backend fetches the schedule from Google Sheets).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libjpeg-dev zlib1g-dev libwebp-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /build/dist ./frontend/dist

# Data dir is mounted at runtime from the host (outside the repo / image).
ENV DATA_DIR=/data
ENV DB_PATH=/data/grand_festival.db
ENV UPLOAD_DIR=/data/uploads
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status==200 else 1)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
