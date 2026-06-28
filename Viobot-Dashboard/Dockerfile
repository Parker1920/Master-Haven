# ============================================================
# Viobot Dashboard — single-container image
# Stage 1 builds the React SPA; stage 2 runs the Node API and
# serves the built SPA from the same origin.
# ============================================================

# --- Stage 1: build the frontend ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Stage 2: runtime (API + static SPA) ---
FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
# better-sqlite3 installs a prebuilt arm64 binary here (same base image Viobot uses on the Pi).
COPY server/package.json server/package-lock.json ./
RUN npm ci --omit=dev
COPY server/ ./
COPY --from=web /web/dist ./public
ENV WEB_DIST=/app/public
EXPOSE 8090
CMD ["node", "src/index.js"]
