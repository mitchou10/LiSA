# syntax=docker/dockerfile:1

# Build stage
FROM node:25-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# nginxinc/nginx-unprivileged already runs as the unprivileged `nginx` user
# (uid 101) and listens on 8080 instead of 80, so no extra USER/port setup
# is required to get a non-root container.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
# The base image only gets rebuilt now and then: pull in the Alpine fixes published since (openssl,
# zlib, musl...). It needs root, which the base image doesn't run as - dropped again right after.
USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=nginx:nginx --from=build /app/dist /usr/share/nginx/html
# Explicit rather than inherited from the base image: same user as before (nginx, uid 101), but
# visible to scanners (Trivy DS-0002 can't see an inherited USER).
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:8080/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
