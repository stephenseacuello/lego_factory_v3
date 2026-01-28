# LEGO MCP Server - Optional Docker Container
#
# This Dockerfile is optional - you can run the MCP server
# directly on your host machine with Python.
#
# Use this if you want full containerization of the MCP server.

FROM python:3.11-slim

LABEL maintainer="LegoMCP Project"
LABEL description="MCP Server for LEGO brick generation with Fusion 360"

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FUSION_API_URL=http://host.docker.internal:8765
ENV SLICER_API_URL=http://slicer:8766

# The MCP server communicates via stdio, so no port exposure needed
# It's typically run via Claude Desktop's process spawning

CMD ["python", "-m", "src.server"]
