# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for Web frontend

# Base stage for dependencies
FROM node:20-alpine AS base

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

WORKDIR /app

# Copy package files first for better caching
COPY apps/web/package*.json ./
COPY packages/ts/common/package*.json ./packages/ts/common/

# Install dependencies with clean cache
RUN npm ci --only=production && npm cache clean --force

# Development stage
FROM base AS development
RUN npm ci
COPY apps/web/ .
COPY packages/ts/ ./packages/ts/
EXPOSE 5173
CMD ["dumb-init", "npm", "run", "dev", "--", "--host"]

# Build stage  
FROM base AS build
RUN npm ci
COPY apps/web/ .
COPY packages/ts/ ./packages/ts/
COPY contracts/ ./contracts/
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Install security updates
RUN apk update && apk upgrade && apk add --no-cache dumb-init

# Create nginx user for security
RUN addgroup -g 101 -S nginx && adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf.default

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
