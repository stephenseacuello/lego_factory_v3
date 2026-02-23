#!/bin/bash
# =============================================================================
# LEGO MCP v8.0 Smoke Test Script
# DoD/ONR-Class Manufacturing System
# =============================================================================
#
# Runs basic smoke tests to verify deployment health.
#
# Usage:
#   ./scripts/smoke_test.sh [environment]
#
# Environments:
#   development (default) - http://localhost:5000
#   staging               - https://staging.lego-mcp.example.com
#   production            - https://lego-mcp.example.com
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ENVIRONMENT="${1:-development}"
TIMEOUT=10
PASSED=0
FAILED=0
TOTAL=0

# Set base URL based on environment
case $ENVIRONMENT in
    development)
        BASE_URL="http://localhost:5000"
        MCP_URL="http://localhost:3000"
        SLICER_URL="http://localhost:8081"
        ;;
    staging)
        BASE_URL="https://staging.lego-mcp.example.com"
        MCP_URL="https://staging.lego-mcp.example.com/mcp"
        SLICER_URL="https://staging.lego-mcp.example.com/slicer"
        ;;
    production)
        BASE_URL="https://lego-mcp.example.com"
        MCP_URL="https://lego-mcp.example.com/mcp"
        SLICER_URL="https://lego-mcp.example.com/slicer"
        ;;
    *)
        echo -e "${RED}Unknown environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Test functions
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local method="${4:-GET}"

    TOTAL=$((TOTAL + 1))

    local response
    local status

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null || echo "000")
    else
        response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" -X "$method" "$url" 2>/dev/null || echo "000")
    fi

    status=$(echo "$response" | tail -1)

    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $name (HTTP $status)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $name (Expected HTTP $expected_status, got $status)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_json_response() {
    local name="$1"
    local url="$2"
    local json_key="$3"

    TOTAL=$((TOTAL + 1))

    local response
    response=$(curl -s --max-time "$TIMEOUT" "$url" 2>/dev/null || echo "{}")

    if echo "$response" | jq -e ".$json_key" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name (JSON key '$json_key' present)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $name (JSON key '$json_key' missing)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_latency() {
    local name="$1"
    local url="$2"
    local max_latency_ms="$3"

    TOTAL=$((TOTAL + 1))

    local latency
    latency=$(curl -s -w "%{time_total}" -o /dev/null --max-time "$TIMEOUT" "$url" 2>/dev/null || echo "999")
    latency_ms=$(echo "$latency * 1000" | bc | cut -d. -f1)

    if [ "$latency_ms" -lt "$max_latency_ms" ]; then
        echo -e "${GREEN}✓${NC} $name (${latency_ms}ms < ${max_latency_ms}ms)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $name (${latency_ms}ms >= ${max_latency_ms}ms)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Header
echo ""
echo "=========================================="
echo "  LEGO MCP v8.0 Smoke Tests"
echo "  Environment: $ENVIRONMENT"
echo "  Base URL: $BASE_URL"
echo "=========================================="
echo ""

# =============================================================================
# Dashboard Service Tests
# =============================================================================

echo -e "${BLUE}--- Dashboard Service ---${NC}"

test_endpoint "Dashboard Health" "$BASE_URL/health"
test_endpoint "Dashboard Root" "$BASE_URL/"
test_latency "Dashboard Latency" "$BASE_URL/health" 500

# API v8 endpoints
echo ""
echo -e "${BLUE}--- API v8 Endpoints ---${NC}"

test_endpoint "API Health" "$BASE_URL/api/v8/health"
test_endpoint "Equipment List" "$BASE_URL/api/v8/equipment"
test_endpoint "Manufacturing Orders" "$BASE_URL/api/v8/manufacturing/orders"
test_endpoint "Digital Twin Status" "$BASE_URL/api/v8/digital-twin/status"
test_endpoint "AI Predictions" "$BASE_URL/api/v8/ai/predictions"
test_endpoint "Command Center" "$BASE_URL/api/v8/command-center/kpis"
test_endpoint "Compliance CMMC" "$BASE_URL/api/v8/compliance/cmmc/status"

# JSON response validation
echo ""
echo -e "${BLUE}--- JSON Response Validation ---${NC}"

test_json_response "Health Response" "$BASE_URL/api/v8/health" "status"
test_json_response "Equipment Response" "$BASE_URL/api/v8/equipment" "data"

# =============================================================================
# MCP Server Tests
# =============================================================================

echo ""
echo -e "${BLUE}--- MCP Server ---${NC}"

test_endpoint "MCP Health" "$MCP_URL/health"
test_endpoint "MCP Tools List" "$MCP_URL/tools"

# =============================================================================
# Slicer Service Tests
# =============================================================================

echo ""
echo -e "${BLUE}--- Slicer Service ---${NC}"

test_endpoint "Slicer Health" "$SLICER_URL/health"
test_endpoint "Slicer Profiles" "$SLICER_URL/profiles"

# =============================================================================
# Security Tests
# =============================================================================

echo ""
echo -e "${BLUE}--- Security Checks ---${NC}"

# Check HTTPS redirect (production only)
if [ "$ENVIRONMENT" != "development" ]; then
    test_endpoint "HTTPS Redirect" "${BASE_URL/https:/http:}/" "301"
fi

# Check security headers
check_security_headers() {
    local url="$1"
    TOTAL=$((TOTAL + 1))

    local headers
    headers=$(curl -s -I --max-time "$TIMEOUT" "$url" 2>/dev/null || echo "")

    local missing=""

    if ! echo "$headers" | grep -qi "X-Frame-Options"; then
        missing="$missing X-Frame-Options"
    fi
    if ! echo "$headers" | grep -qi "X-Content-Type-Options"; then
        missing="$missing X-Content-Type-Options"
    fi
    if ! echo "$headers" | grep -qi "X-XSS-Protection"; then
        missing="$missing X-XSS-Protection"
    fi

    if [ -z "$missing" ]; then
        echo -e "${GREEN}✓${NC} Security Headers present"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${YELLOW}⚠${NC} Missing security headers:$missing"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

check_security_headers "$BASE_URL/health"

# =============================================================================
# Performance Tests
# =============================================================================

echo ""
echo -e "${BLUE}--- Performance Checks ---${NC}"

test_latency "API Response Time" "$BASE_URL/api/v8/health" 200
test_latency "Equipment Query Time" "$BASE_URL/api/v8/equipment" 500
test_latency "Digital Twin Time" "$BASE_URL/api/v8/digital-twin/status" 1000

# =============================================================================
# WebSocket Test
# =============================================================================

echo ""
echo -e "${BLUE}--- WebSocket Check ---${NC}"

check_websocket() {
    TOTAL=$((TOTAL + 1))

    # Simple check if WebSocket endpoint responds
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" \
        -H "Upgrade: websocket" \
        -H "Connection: Upgrade" \
        -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
        -H "Sec-WebSocket-Version: 13" \
        "$BASE_URL/ws" 2>/dev/null || echo "000")

    # WebSocket upgrade should return 101 or connection refused (000) is also ok for basic check
    if [ "$response" = "101" ] || [ "$response" = "400" ]; then
        echo -e "${GREEN}✓${NC} WebSocket endpoint accessible"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${YELLOW}⚠${NC} WebSocket endpoint returned $response"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

check_websocket

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "=========================================="
echo "  Test Summary"
echo "=========================================="
echo ""
echo -e "  Total:  $TOTAL"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"
echo ""

# Calculate pass rate
if [ "$TOTAL" -gt 0 ]; then
    PASS_RATE=$((PASSED * 100 / TOTAL))
    echo "  Pass Rate: ${PASS_RATE}%"
fi

echo ""

# Exit with appropriate code
if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}Smoke tests FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}All smoke tests PASSED${NC}"
    exit 0
fi
