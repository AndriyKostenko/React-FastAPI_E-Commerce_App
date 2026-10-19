# -------------------------
# Dependencies
# -------------------------
FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# -------------------------
# Build
# -------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# NEXT_PUBLIC_* values are inlined into the JavaScript bundle at build time,
# so they are build arguments, not runtime environment. The publishable Stripe
# key has no default: the build fails (lib/config.ts validates it) rather than
# shipping a bundle without a payment key.
ARG NEXT_PUBLIC_APP_URL=http://localhost:30000
ARG NEXT_PUBLIC_API_ORIGIN
ARG NEXT_PUBLIC_API_VERSION=v1
ARG NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY
ARG CATALOGUE_IMAGE_HOST
# Optional: a social link is shown only when its URL is set.
ARG NEXT_PUBLIC_INSTAGRAM_URL
ARG NEXT_PUBLIC_FACEBOOK_URL

ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# -------------------------
# Runtime
# -------------------------
FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Next's standalone output carries its own minimal node_modules and server.js.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

# The official image's unprivileged user (uid/gid 1000).
USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]
