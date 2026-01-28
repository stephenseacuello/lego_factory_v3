#!/bin/bash
# LEGO Factory v3 - Quick Start Script

set -e

echo "=========================================="
echo "  LEGO Factory v3 - Starting Up"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}Created .env - edit it to customize settings${NC}"
fi

# Check if Docker is available
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo ""
    echo "Docker detected. Starting with Docker Compose..."
    echo ""

    # Start services
    docker-compose up -d postgres redis mosquitto

    echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
    sleep 5

    # Check if database is ready
    until docker-compose exec -T postgres pg_isready -U lego -d lego_factory > /dev/null 2>&1; do
        echo "Waiting for database..."
        sleep 2
    done

    echo -e "${GREEN}Database is ready!${NC}"

    # Start the app
    docker-compose up -d app

    echo ""
    echo -e "${GREEN}=========================================="
    echo "  LEGO Factory v3 is running!"
    echo "==========================================${NC}"
    echo ""
    echo "  Dashboard:    http://localhost:5000"
    echo "  Alarms:       http://localhost:5000/scada/alarms"
    echo "  Work Orders:  http://localhost:5000/mes/work-orders"
    echo "  LEGO Catalog: http://localhost:5000/lego/catalog"
    echo ""
    echo "  View logs:    docker-compose logs -f app"
    echo "  Stop:         docker-compose down"
    echo ""

else
    echo ""
    echo "Docker not found. Starting locally..."
    echo ""

    # Check for virtual environment
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt -q

    echo ""
    echo -e "${YELLOW}NOTE: You need PostgreSQL + TimescaleDB running.${NC}"
    echo "Run this to start PostgreSQL with Docker:"
    echo ""
    echo "  docker run -d --name lego-postgres \\"
    echo "    -e POSTGRES_USER=lego \\"
    echo "    -e POSTGRES_PASSWORD=\$POSTGRES_PASSWORD \\"
    echo "    -e POSTGRES_DB=lego_factory \\"
    echo "    -p 5432:5432 \\"
    echo "    timescale/timescaledb:latest-pg15"
    echo ""
    echo "Make sure to set POSTGRES_PASSWORD in your .env file first!"
    echo ""

    # Start Flask
    echo -e "${GREEN}Starting Flask application...${NC}"
    echo ""
    flask run --host=0.0.0.0 --port=5000
fi
