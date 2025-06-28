FROM python:3.10-slim-buster

WORKDIR /app

# Install dependencies
RUN pip install --upgrade pip
RUN pip install mcp aiohttp

# Copy MCP server
COPY tests/mcp/utils/mcp_bot_server.py .

# Run MCP server
CMD ["python", "mcp_bot_server.py"]