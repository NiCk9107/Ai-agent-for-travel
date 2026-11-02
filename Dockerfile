# syntax=docker/dockerfile:1

# ---------- 1. Сборка фронта (React + Vite) ----------
FROM node:22.16.0-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Фронт и API живут на одном порту 8080 — фронт ходит туда же
ARG VITE_API_URL=http://localhost:8080
ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCKS=false
RUN npm run build

# ---------- 2. Зависимости Python ----------
FROM python:3.12.7-slim-bookworm AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY backend/requirements.txt .
RUN /opt/venv/bin/pip install -r requirements.txt

# ---------- 3. Рантайм: только venv, код и собранный фронт ----------
FROM python:3.12.7-slim-bookworm
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_DIR=/app/static
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app backend/ ./
COPY --from=frontend --chown=app:app /app/dist ./static
USER app
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]