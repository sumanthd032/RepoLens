# RepoLens — multi-stage build.
#   1. frontend : build the React SPA
#   2. builder  : bake the SPA into the package and build the wheel
#   3. runtime  : slim image with only the installed wheel + its deps

# --- Stage 1: build the React frontend -------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: build the Python wheel ---------------------------------------
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY . .
# Drop the built SPA into the package so it ships inside the wheel (Invariant 7).
COPY --from=frontend /app/frontend/dist ./src/repolens/static
RUN uv build --wheel --out-dir /dist

# --- Stage 3: slim runtime image -------------------------------------------
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 app
WORKDIR /home/app

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

ENV REPOLENS_DATA_DIR=/data \
    REPOLENS_LOG_LEVEL=INFO \
    HF_HOME=/data/.cache/huggingface
RUN mkdir -p /data && chown -R app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8000

CMD ["repolens", "serve", "--host", "0.0.0.0", "--port", "8000"]
