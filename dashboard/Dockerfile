# LEGO MCP Dashboard - Docker Image
# Flask web dashboard for LEGO brick management
#
# Build from project root with:
#   docker build -f dashboard/Dockerfile -t lego-mcp-dashboard .
#
# Or use docker-compose from project root:
#   docker-compose -f dashboard/docker-compose.yml up

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_APP=app.py \
    PYTHONPATH=/app:/app/shared:/app/tools

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    # OpenCV dependencies (for YOLO vision detection)
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (v5.0 World-Class Manufacturing Platform)
RUN pip install --no-cache-dir \
    Flask>=2.3.0 \
    Flask-SocketIO>=5.3.0 \
    python-socketio>=5.8.0 \
    python-engineio>=4.5.0 \
    requests>=2.28.0 \
    gunicorn>=21.0.0 \
    eventlet>=0.33.0 \
    celery[redis]>=5.3.0 \
    python-dotenv>=1.0.0 \
    psutil>=5.9.0 \
    # v5.0 Database and ORM (ISA-95 data model)
    SQLAlchemy>=2.0.0 \
    psycopg2-binary>=2.9.0 \
    alembic>=1.12.0 \
    # v5.0 Manufacturing services
    redis>=5.0.0 \
    numpy>=1.24.0 \
    scipy>=1.11.0 \
    # v5.0 Equipment controllers (async)
    aiohttp>=3.9.0 \
    pyserial>=3.5 \
    opencv-python-headless>=4.8.0 \
    # v8.0 ML Detection (YOLO11 for real brick detection)
    ultralytics>=8.0.0 \
    torch>=2.0.0 \
    torchvision>=0.15.0 \
    # Roboflow SDK (for LEGO-specific brick detection)
    inference-sdk>=0.9.0 \
    roboflow>=1.1.0

# Copy dashboard application
COPY dashboard/ /app/

# Copy shared modules and tools (from project root context)
COPY shared/ /app/shared/
COPY mcp-server/src/tools/ /app/tools/

# Create output directory
RUN mkdir -p /output

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "app:create_app()"]
