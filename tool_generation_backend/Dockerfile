# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory to match local structure
WORKDIR /app/tool_generation_backend

# Install system dependencies including ripgrep
RUN apt-get update && apt-get install -y \
    curl \
    git \
    ripgrep \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Verify ripgrep installation
RUN which rg && rg --version

# Install Node.js for Codex CLI
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install Codex CLI globally via npm
RUN npm install -g @openai/codex

# Verify Codex CLI installation
RUN which codex && codex --version

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen

# Copy application code
COPY . .

# Create tool_service directory structure
RUN mkdir -p /app/tool_service/tools

# Copy schema template for code generation
COPY templates/tool_schema.txt /app/tool_service/tools/schema.txt

# Create Codex config directory and add trusted project config
RUN mkdir -p /root/.codex
RUN echo 'model = "gpt-5"' > /root/.codex/config.toml && \
    echo 'model_reasoning_effort = "low"' >> /root/.codex/config.toml && \
    echo '' >> /root/.codex/config.toml && \
    echo '[projects."/app/tool_service"]' >> /root/.codex/config.toml && \
    echo 'trust_level = "trusted"' >> /root/.codex/config.toml

# Note: Codex authentication will happen at app startup

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start command (from within tool_generation_backend)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]