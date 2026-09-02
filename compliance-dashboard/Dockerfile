# ==============================================================================
# React Frontend Dockerfile (Multi-Stage Build)
# ==============================================================================

# Stage 1: Build static web bundle
FROM node:22-alpine AS build-stage

WORKDIR /app

COPY package*.json ./
RUN npm ci --quiet

COPY . .
RUN npm run build

# Stage 2: Production Nginx Server
FROM nginx:alpine AS production-stage

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
