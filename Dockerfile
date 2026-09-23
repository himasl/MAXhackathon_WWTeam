# One image: FastAPI serves the API, the MAX webhook and the built Mini App (single HTTPS URL).

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SCENARIO_DATA_DIR=/app/data/scenarios \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    PORT=8000

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/certs ./certs
COPY backend/app ./app
COPY data /app/data
COPY --from=frontend /build/dist /app/frontend/dist

RUN useradd --system --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# Migrations and scenario sync are idempotent and run before the API starts.
CMD ["sh", "-c", "alembic upgrade head && python -m app.scenarios.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
