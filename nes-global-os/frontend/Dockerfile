# Build the static UI, then serve it with Caddy (which also reverse-proxies /api to FastAPI).
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /web/out /srv
