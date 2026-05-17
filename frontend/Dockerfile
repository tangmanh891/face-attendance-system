# Multi-stage build cho Frontend React
# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

ARG VITE_API_URL=/api
ARG VITE_WS_URL=ws://localhost:8000/api/recognition/stream
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

# Build production bundle
RUN npm run build

# Stage 2: Serve với Nginx
FROM nginx:1.27-alpine AS runtime

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Cấu hình Nginx cho React Router (SPA)
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    # Security headers \
    add_header X-Frame-Options "DENY" always; \
    add_header X-Content-Type-Options "nosniff" always; \
    add_header X-XSS-Protection "1; mode=block" always; \
    add_header Referrer-Policy "strict-origin-when-cross-origin" always; \
    \
    # Gzip compression \
    gzip on; \
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml; \
    \
    # Cache static assets \
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ { \
        expires 1y; \
        add_header Cache-Control "public, immutable"; \
    } \
    \
    # API proxy \
    location /api { \
        proxy_pass http://backend:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
    } \
    \
    # SPA fallback \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
