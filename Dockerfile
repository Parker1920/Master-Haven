# ============================================================
# Haven Control Room — Dockerfile
# ============================================================
# This file tells Docker how to build a container image for Haven.
# Think of it as a recipe: each line is a step that builds on the last.
# The final result is a lightweight, portable package that runs Haven
# the same way everywhere — your desktop, the Pi, anywhere.
# ============================================================

# --- BASE IMAGE ---
# Start from an official Python image built for ARM64 (Pi 5 compatible).
# "slim" means it's a minimal Debian install — no extras we don't need.
# This keeps the image small (~150MB instead of ~900MB for the full version).
FROM python:3.11-slim

# --- METADATA ---
# Labels are just tags on the image — they don't affect how it runs.
# Useful for `docker inspect` to see who made this and what it is.
LABEL maintainer="Parker1920"
LABEL description="Haven Control Room — Voyager's Haven community web app"

# --- WORKING DIRECTORY ---
# Creates /app inside the container and makes it the default folder.
# Every command after this runs from /app (like doing `cd /app`).
WORKDIR /app

# --- INSTALL DEPENDENCIES FIRST ---
# We copy requirements.txt BEFORE copying the rest of the code.
# Why? Docker caches each step. If your code changes but requirements
# don't, Docker reuses the cached pip install (saves minutes on rebuilds).
COPY requirements.txt .

# Install Python packages.
# --no-cache-dir: Don't store pip's download cache (saves ~50MB in image)
# --no-compile: Skip generating .pyc files (saves a bit of space)
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# --- COPY APPLICATION CODE ---
# Now copy everything else into the container.
# The .dockerignore file (we'll create next) controls what gets excluded.
COPY . .

# --- EXPOSE PORT ---
# Documents that this container listens on port 8005.
# This doesn't actually open the port — that happens in docker-compose.yml.
# Think of it as a note to anyone reading this file: "Haven uses 8005."
EXPOSE 8005

# --- HEALTH CHECK ---
# Docker will ping this endpoint every 30 seconds to check if Haven is alive.
# If it fails 3 times in a row, Docker marks the container as "unhealthy."
# This is what lets Uptime Kuma and Watchtower know something's wrong.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/api/status')" || exit 1

# --- START COMMAND ---
# The command that runs when the container starts.
# This is exactly what you typed manually: python server.py
CMD ["python", "server.py"]
