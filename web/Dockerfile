# syntax=docker/dockerfile:1

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# The /api proxy target is fixed when the image is built; override with --build-arg for another topology.
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
# Largest request body the /api proxy accepts (admin CSV uploads). Lower it for a small server: bodies are buffered in memory.
ARG PROXY_BODY_LIMIT=520mb
ENV PROXY_BODY_LIMIT=$PROXY_BODY_LIMIT
RUN npm run build

# ── runtime: only the standalone server, non-root, read-only friendly ──────────────────────────────
FROM node:22-alpine AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S -g 10001 app && adduser -S -u 10001 -G app app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/login >/dev/null || exit 1
CMD ["node", "server.js"]
