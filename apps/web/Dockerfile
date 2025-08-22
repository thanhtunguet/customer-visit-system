# Multi-stage Dockerfile for Web frontend
FROM node:20-alpine AS base

# Install yarn globally
RUN npm install -g yarn

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install

# Copy source code
COPY . .

# Development stage
FROM base AS development
EXPOSE 5173
CMD ["yarn", "dev", "--host"]

# Build stage  
FROM base AS build
RUN yarn build

# Production stage
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]