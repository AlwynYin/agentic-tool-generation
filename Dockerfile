# Multi-stage build: Frontend + Backend
# Stage 1: Build frontend
FROM node:18-slim as frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package.json frontend/package-lock.json* ./

# Install frontend dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build frontend with environment variables pointing to same origin
# Empty VITE_WS_URL means use same host
ENV VITE_API_URL=/api/v1
ENV VITE_WS_URL=

RUN npm run build

# Stage 2: Backend with frontend included
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    ripgrep \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Codex CLI
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Codex CLI globally
RUN npm install -g @openai/codex

# Verify installations
RUN which rg && rg --version && which codex && codex --version

# Install uv for Python package management
RUN pip install uv

# Copy backend dependency files
COPY tool_generation_backend/pyproject.toml tool_generation_backend/uv.lock ./tool_generation_backend/

# Install Python dependencies
WORKDIR /app/tool_generation_backend
RUN uv sync --frozen

# Copy backend application code
COPY tool_generation_backend/ ./

# Copy frontend build from stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Create tool_service directory structure
RUN mkdir -p /app/tool_service/tools

# Copy schema template
COPY tool_generation_backend/templates/tool_schema.txt /app/tool_service/tools/schema.txt

# Create Codex config
RUN mkdir -p /root/.codex && \
    echo 'model = "gpt-5"' > /root/.codex/config.toml && \
    echo 'model_reasoning_effort = "low"' >> /root/.codex/config.toml && \
    echo '' >> /root/.codex/config.toml && \
    echo '[projects."/app/tool_service"]' >> /root/.codex/config.toml && \
    echo 'trust_level = "trusted"' >> /root/.codex/config.toml

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start server (working directory is already /app/tool_generation_backend)
# .env file should be in this directory
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]