#!/bin/bash
# Load Testing Runner Script
# Usage: ./run_load_test.sh [mode] [users] [spawn_rate] [duration]

set -e

# Default values
MODE="${1:-local}"
USERS="${2:-100}"
SPAWN_RATE="${3:-10}"
DURATION="${4:-60}"
HOST="${HOST:-http://localhost:5000}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== LEGO Factory Load Testing ===${NC}"
echo "Mode: $MODE"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE/sec"
echo "Duration: ${DURATION}s"
echo "Target Host: $HOST"
echo ""

# Check if locust is installed
if ! command -v locust &> /dev/null; then
    echo -e "${RED}Error: locust is not installed${NC}"
    echo "Install with: pip install locust"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCUST_FILE="$SCRIPT_DIR/locustfile.py"

if [ ! -f "$LOCUST_FILE" ]; then
    echo -e "${RED}Error: locustfile.py not found at $LOCUST_FILE${NC}"
    exit 1
fi

# Create results directory
RESULTS_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULT_PREFIX="$RESULTS_DIR/load_test_$TIMESTAMP"

case $MODE in
    "local")
        echo -e "${YELLOW}Running local load test...${NC}"
        locust \
            -f "$LOCUST_FILE" \
            --host="$HOST" \
            --users="$USERS" \
            --spawn-rate="$SPAWN_RATE" \
            --run-time="${DURATION}s" \
            --headless \
            --html="${RESULT_PREFIX}_report.html" \
            --csv="${RESULT_PREFIX}"
        ;;

    "web")
        echo -e "${YELLOW}Starting Locust web UI...${NC}"
        echo "Open http://localhost:8089 in your browser"
        locust \
            -f "$LOCUST_FILE" \
            --host="$HOST" \
            --web-port=8089
        ;;

    "distributed-master")
        echo -e "${YELLOW}Starting Locust master node...${NC}"
        locust \
            -f "$LOCUST_FILE" \
            --host="$HOST" \
            --master \
            --expect-workers="${WORKERS:-4}"
        ;;

    "distributed-worker")
        echo -e "${YELLOW}Starting Locust worker node...${NC}"
        MASTER_HOST="${MASTER_HOST:-localhost}"
        locust \
            -f "$LOCUST_FILE" \
            --worker \
            --master-host="$MASTER_HOST"
        ;;

    "quick")
        echo -e "${YELLOW}Running quick smoke test...${NC}"
        locust \
            -f "$LOCUST_FILE" \
            --host="$HOST" \
            --users=10 \
            --spawn-rate=5 \
            --run-time="30s" \
            --headless \
            --html="${RESULT_PREFIX}_quick_report.html"
        ;;

    "stress")
        echo -e "${YELLOW}Running stress test (high load)...${NC}"
        locust \
            -f "$LOCUST_FILE" \
            --host="$HOST" \
            --users=500 \
            --spawn-rate=50 \
            --run-time="120s" \
            --headless \
            --html="${RESULT_PREFIX}_stress_report.html" \
            --csv="${RESULT_PREFIX}_stress"
        ;;

    "soak")
        echo -e "${YELLOW}Running soak test (extended duration)...${NC}"
        locust \
            -f "$LOCUST_FILE" \
            --host="$HOST" \
            --users=50 \
            --spawn-rate=5 \
            --run-time="3600s" \
            --headless \
            --html="${RESULT_PREFIX}_soak_report.html" \
            --csv="${RESULT_PREFIX}_soak"
        ;;

    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo ""
        echo "Usage: $0 [mode] [users] [spawn_rate] [duration]"
        echo ""
        echo "Modes:"
        echo "  local              - Run headless load test (default)"
        echo "  web                - Start web UI for interactive testing"
        echo "  distributed-master - Start as master node for distributed testing"
        echo "  distributed-worker - Start as worker node"
        echo "  quick              - Quick smoke test (10 users, 30s)"
        echo "  stress             - High load stress test (500 users, 2min)"
        echo "  soak               - Extended soak test (50 users, 1hr)"
        echo ""
        echo "Environment variables:"
        echo "  HOST         - Target host URL (default: http://localhost:5000)"
        echo "  MASTER_HOST  - Master node host for workers (default: localhost)"
        echo "  WORKERS      - Expected worker count for master (default: 4)"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Load test complete!${NC}"

if [ -f "${RESULT_PREFIX}_report.html" ]; then
    echo "Report saved to: ${RESULT_PREFIX}_report.html"
fi

if [ -f "${RESULT_PREFIX}_stats.csv" ]; then
    echo ""
    echo "=== Summary Statistics ==="
    echo ""
    # Print summary from CSV
    if command -v column &> /dev/null; then
        head -20 "${RESULT_PREFIX}_stats.csv" | column -t -s,
    else
        head -20 "${RESULT_PREFIX}_stats.csv"
    fi
fi
