FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/backend PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt "psycopg[binary]>=3.1"
COPY alembic.ini ./
COPY backend ./backend
COPY scripts ./scripts
COPY artifacts ./artifacts
COPY --from=web /web/dist ./frontend/dist
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec python -m uvicorn mediqueue.app:app \
     --app-dir backend --host 0.0.0.0 --port 8000"]
