FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY src ./src
COPY pyproject.toml README.md ./

# Default to the HTTP transport for container deployments.
ENV MCP_TRANSPORT=http \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8000

EXPOSE 8000

# Run the streamable-HTTP MCP server. The MCP endpoint is served at /mcp.
CMD ["python", "-m", "src.server", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
