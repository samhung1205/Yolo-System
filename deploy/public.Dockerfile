# syntax=docker/dockerfile:1
# The deployment tool resolves these official tags to registry digests first.
ARG NODE_IMAGE=node:22-bookworm-slim
ARG CADDY_IMAGE=caddy:2.11.7-alpine
FROM ${NODE_IMAGE} AS frontend
WORKDIR /build
COPY web-frontend/package.json web-frontend/package-lock.json ./
RUN npm ci --include=dev
COPY web-frontend/index.html web-frontend/vite.config.js ./
COPY web-frontend/src/ ./src/
RUN VITE_API_BASE_URL="" npm run build

FROM ${CADDY_IMAGE}
COPY --from=frontend /build/dist/ /srv/
COPY deploy/Caddyfile.public /etc/caddy/Caddyfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD wget -q -O - "https://${YOLO_PUBLIC_IP}/api/health" | grep -q '"database":"connected"'
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
