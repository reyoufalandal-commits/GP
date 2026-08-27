# Hawk-Eye API + static dashboard (multi-stage).
# Build: docker build -t hawk-eye:latest .
# Run:  see docker-compose.yml
FROM node:20-bookworm-slim AS frontend
WORKDIR /fe
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json ./
RUN npm ci
COPY dashboard/frontend/ ./
RUN npm run build

FROM python:3.12-slim AS api
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY --from=frontend /fe/dist ./static-dashboard
ENV HAWK_EYE_DASHBOARD_STATIC=/app/static-dashboard
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "hawk_eye.api_service:app", "--host", "0.0.0.0", "--port", "8000"]
