# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for Web frontend

# Base stage for dependencies
FROM node:20-alpine AS base

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

WORKDIR /app

# Copy package files first for better caching
COPY apps/web/package*.json ./apps/web/
COPY packages/ts/common/package*.json ./packages/ts/common/

# Set working directory to web app
WORKDIR /app/apps/web

# Install dependencies with clean cache
RUN npm ci --only=production && npm cache clean --force

# Development stage
FROM base AS development
RUN npm ci
WORKDIR /app
COPY apps/web/ ./apps/web/
COPY packages/ts/ ./packages/ts/
WORKDIR /app/apps/web
EXPOSE 5173
CMD ["dumb-init", "npm", "run", "dev", "--", "--host"]

# Build stage  
FROM base AS build
RUN npm ci
WORKDIR /app
COPY apps/web/ ./apps/web/
COPY packages/ts/ ./packages/ts/
COPY contracts/ ./contracts/
WORKDIR /app/apps/web
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Install security updates
RUN apk update && apk upgrade && apk add --no-cache dumb-init

# nginx:alpine already ships with an nginx user/group; no need to recreate

# Copy built assets
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

# Copy nginx configuration
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf.default || true

# Fix permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

USER nginx

EXPOSE 80

CMD ["dumb-init", "nginx", "-g", "daemon off;"]
