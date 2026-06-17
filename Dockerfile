# RepoLens Dockerfile — skeleton.
# The full multi-stage build (frontend build → wheel build → slim runtime) is completed in
# Step 10. This placeholder documents the intended stages and keeps the build context valid.

# --- Stage 1: build the React frontend -------------------------------------
# FROM node:20-slim AS frontend
# WORKDIR /app/frontend
# COPY frontend/package*.json ./
# RUN npm ci
# COPY frontend/ ./
# RUN npm run build

# --- Stage 2: build the Python wheel ---------------------------------------
# FROM python:3.12-slim AS wheel
# ...

# --- Stage 3: slim runtime image -------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Placeholder runtime. Step 10 installs the built wheel and the static frontend,
# then runs `repolens serve`.
CMD ["python", "-c", "print('RepoLens image skeleton — completed in Step 10')"]
