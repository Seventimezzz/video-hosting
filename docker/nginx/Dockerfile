# Multi-stage сборка: в итоговый образ попадает только собранная статика и nginx.
# Node, node_modules и исходники фронта остаются в первой стадии и выбрасываются.
# Контекст сборки — корень репозитория (см. docker-compose.yml).

# --- Стадия 1: сборка Angular ---
FROM node:24-alpine AS build
WORKDIR /app

# Зависимости отдельным слоем: npm ci повторяется, только если менялся lock-файл.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Стадия 2: nginx со статикой ---
FROM nginx:stable-alpine

COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/video-admin/browser /usr/share/nginx/html
