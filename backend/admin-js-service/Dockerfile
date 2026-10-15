# -------------------------
# Build
# -------------------------
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# -------------------------
# Runtime (production dependencies only, non-root)
# -------------------------
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

RUN mkdir -p /app/.adminjs && chown node:node /app/.adminjs

COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder --chown=node:node /app/dist ./dist
# AdminJS bundles its TSX components from src/ at startup and writes the
# bundle to .adminjs/, so both must exist and be writable at runtime.
COPY --from=builder --chown=node:node /app/src ./src

# The official image's unprivileged user (uid/gid 1000).
USER node

EXPOSE 3000

# Configuration comes from the container environment (compose env_file);
# no .env file is copied in, so the start script's dotenv step is skipped.
CMD ["node", "dist/app.js"]
