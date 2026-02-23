#!/usr/bin/env bash
# =============================================================================
# LEGO Factory v3 — Comprehensive Endpoint Test Script
# =============================================================================
# Usage: ./test_all.sh [BASE_URL]
#   BASE_URL defaults to http://localhost:5000
#   Start the server with: python run.py (NOT flask run)
# =============================================================================

set -uo pipefail

BASE="${1:-http://localhost:5000}"
PASS=0
FAIL=0
SKIP=0
TOKEN=""

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Helpers ──────────────────────────────────────────────────────────────────

test_endpoint() {
    local method="$1"
    local path="$2"
    local expected="${3:-200}"
    local data="${4:-}"
    local url="${BASE}${path}"

    local args=(-s -o /dev/null -w "%{http_code}" --max-time 10 -X "$method")
    if [[ -n "$TOKEN" ]]; then
        args+=(-H "Authorization: Bearer $TOKEN")
    fi
    args+=(-H "Content-Type: application/json")
    if [[ -n "$data" ]]; then
        args+=(-d "$data")
    fi

    local status
    status=$(curl "${args[@]}" "$url" 2>/dev/null || echo "000")

    local matched=false
    IFS='|' read -ra codes <<< "$expected"
    for code in "${codes[@]}"; do
        if [[ "$status" == "$code" ]]; then
            matched=true
            break
        fi
    done

    if $matched; then
        printf "  ${GREEN}PASS${NC}  %-7s %-55s %s\n" "$method" "$path" "$status"
        ((PASS++)) || true
    else
        printf "  ${RED}FAIL${NC}  %-7s %-55s got %s (expected %s)\n" "$method" "$path" "$status" "$expected"
        ((FAIL++)) || true
    fi
}

test_get()  { test_endpoint GET  "$1" "${2:-200}"; }
test_post() { test_endpoint POST "$1" "${3:-200}" "${2:-}"; }

section() {
    echo ""
    printf "${CYAN}${BOLD}━━━ %s ━━━${NC}\n" "$1"
}

curl_json() {
    local method="$1" path="$2" data="${3:-}"
    local args=(-s --max-time 10 -X "$method" -H "Content-Type: application/json")
    if [[ -n "$TOKEN" ]]; then
        args+=(-H "Authorization: Bearer $TOKEN")
    fi
    if [[ -n "$data" ]]; then
        args+=(-d "$data")
    fi
    curl "${args[@]}" "${BASE}${path}" 2>/dev/null
}

# =============================================================================
echo ""
printf "${BOLD}LEGO Factory v3 — Test Suite${NC}\n"
printf "Target: ${BASE}\n"
echo ""

printf "Checking connectivity... "
if ! curl -s --max-time 5 -o /dev/null "${BASE}/live" 2>/dev/null; then
    printf "${RED}FAILED${NC} — cannot reach ${BASE}\n"
    printf "Make sure the app is running: flask run\n"
    exit 1
fi
printf "${GREEN}OK${NC}\n"

# =============================================================================
# 1. HEALTH & READINESS
# =============================================================================
section "1. Health & Readiness"
test_endpoint GET "/health" "200|503"
test_get  "/ready"
test_get  "/live"

# =============================================================================
# 2. AUTHENTICATION
# =============================================================================
section "2. Authentication"

# Register + Login to get JWT
REG_BODY='{"username":"testadmin","email":"admin@example.com","password":"Admin1234!","password_confirm":"Admin1234!","first_name":"Admin","last_name":"User"}'
test_endpoint POST "/api/auth/register" "200|201|400|409" "$REG_BODY"

LOGIN_RESP=$(curl_json POST "/api/auth/login" '{"username":"testadmin","password":"Admin1234!"}')
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")

if [[ -n "$TOKEN" && "$TOKEN" != "" ]]; then
    printf "  ${GREEN}PASS${NC}  POST    /api/auth/login                                     (got JWT)\n"
    ((PASS++)) || true
else
    printf "  ${RED}FAIL${NC}  POST    /api/auth/login                                     (no token returned)\n"
    ((FAIL++)) || true
    # Try to continue without auth — many endpoints use jwt_required(optional=True)
    TOKEN=""
fi

if [[ -n "$TOKEN" ]]; then
    test_get "/api/auth/me"
    test_get "/api/auth/protected"
fi

# =============================================================================
# 3. SCADA (Level 1 & 2)
# =============================================================================
section "3. SCADA — Machine Control & Monitoring"

# Core SCADA API (jwt_required(optional=True) — should work without token)
test_get  "/api/scada/machines"
test_get  "/api/scada/alarms"
test_get  "/api/scada/alarms/active"
test_get  "/api/scada/alarms/summary"
test_get  "/api/scada/health"
test_get  "/api/scada/gcode/files"
test_get  "/api/scada/utilization"
test_get  "/api/scada/downtime/pareto"
test_get  "/api/scada/downtime/top-losses"
test_get  "/api/scada/tags"
test_get  "/api/scada/recipes"
test_get  "/api/scada/serial-ports"
test_get  "/api/scada/printers"
test_get  "/api/scada/robots"

# SCADA Sub-Blueprints (under /api/v1/scada/)
test_get  "/api/v1/scada/machines"
test_get  "/api/v1/scada/alarms/summary"
test_get  "/api/v1/scada/alarms/history"
test_get  "/api/v1/scada/tags"
test_get  "/api/v1/scada/historian/stats"
test_get  "/api/v1/scada/recipes/master"

# =============================================================================
# 4. MES (Level 3 — MESA-11)
# =============================================================================
section "4. MES — Manufacturing Execution"

test_get  "/api/mes/work-orders"
test_get  "/api/mes/jobs"
test_get  "/api/mes/scheduling/gantt"
test_get  "/api/mes/scheduling/algorithms"
test_get  "/api/mes/oee"
test_get  "/api/mes/oee/summary"
test_get  "/api/mes/labor/workers"
test_get  "/api/mes/labor/time-entries"
test_get  "/api/mes/timeclock/active"
test_get  "/api/mes/recipes"
test_get  "/api/mes/resources"
test_get  "/api/mes/materials"
test_get  "/api/mes/tools"
test_get  "/api/mes/capacity"
test_get  "/api/mes/bottlenecks"
test_get  "/api/mes/wip/levels"
test_get  "/api/mes/kanban/board"
test_get  "/api/mes/data/events"

# POST: Create work order
test_endpoint POST "/api/mes/work-orders" "200|201|400" '{"product_sku":"BRICK-2x4-RED","quantity":100,"priority":1}'

# =============================================================================
# 5. ERP (Level 4)
# =============================================================================
section "5. ERP — Enterprise Resource Planning"

test_get  "/api/erp/gl/accounts"
test_get  "/api/erp/gl/journal-entries"
test_get  "/api/erp/ap/invoices"
test_get  "/api/erp/ap/aging"
test_get  "/api/erp/ar/invoices"
test_get  "/api/erp/ar/aging"
test_get  "/api/erp/reports/trial-balance"
test_get  "/api/erp/reports/income-statement"
test_get  "/api/erp/reports/dashboard"
test_get  "/api/erp/sales-orders"
test_get  "/api/erp/customers"
test_get  "/api/erp/items"
test_get  "/api/erp/mrp/runs"
test_get  "/api/erp/mrp/shortages"
test_get  "/api/erp/partners"
test_get  "/api/erp/costing/products"
test_get  "/api/erp/costing/variance"
test_get  "/api/erp/profitability"
test_get  "/api/erp/budget?period=2026"
test_get  "/api/erp/cashflow?period=30"
test_get  "/api/erp/cashflow/forecast"
test_get  "/api/erp/fixed-assets"

# POST: Create sales order
test_endpoint POST "/api/erp/sales-orders" "200|201|400" '{"customer_id":"CUST-001","items":[{"item_id":"BRICK-2x4","quantity":50,"unit_price":0.10}]}'

# =============================================================================
# 6. QMS — Quality Management
# =============================================================================
section "6. QMS — Quality Management"

test_get  "/api/qms/documents"
test_get  "/api/qms/pending-approvals"
test_get  "/api/qms/ncrs"
test_get  "/api/qms/capas"
test_get  "/api/qms/spc/charts"
test_get  "/api/qms/spc/capability/summary"
test_get  "/api/qms/inspections"
test_get  "/api/qms/inspections/plans"
test_get  "/api/qms/suppliers/rankings"
test_get  "/api/qms/suppliers/at-risk"
test_get  "/api/qms/dashboard"

# =============================================================================
# 7. CMMS — Maintenance Management
# =============================================================================
section "7. CMMS — Computerized Maintenance"

test_get  "/api/cmms/assets"
test_get  "/api/cmms/work-orders"
test_get  "/api/cmms/pm-schedules"
test_get  "/api/cmms/pm-schedules/compliance"
test_get  "/api/cmms/pm-calendar"
test_get  "/api/cmms/spares"
test_get  "/api/cmms/spares/low-stock"
test_get  "/api/cmms/reliability/worst-performers"
test_get  "/api/cmms/backlog"

# POST: Create maintenance work order
test_endpoint POST "/api/cmms/work-orders" "200|201|400" '{"asset_id":"AST-001","description":"Test maintenance","work_type":"corrective","priority":"medium"}'

# =============================================================================
# 8. LEGO Design
# =============================================================================
section "8. LEGO — Design & Catalog"

test_get  "/api/lego/catalog"
test_get  "/api/lego/catalog/stats"
test_get  "/api/lego/catalog/categories"
test_get  "/api/lego/colors"
test_get  "/api/lego/colors-catalog"
test_get  "/api/lego/parts-catalog"
test_get  "/api/lego/materials-catalog"
test_get  "/api/lego/designs"
test_get  "/api/lego/specs"
test_get  "/api/lego/products"
test_get  "/api/lego/routings"
test_get  "/api/lego/exports"
test_get  "/api/lego/presets"

# =============================================================================
# 9. Unity Digital Twin
# =============================================================================
section "9. Unity — Digital Twin"

test_get  "/api/unity/scene"
test_get  "/api/unity/scenes"
test_get  "/api/unity/entities"
test_get  "/api/unity/service/status"
test_get  "/api/unity/playback/sessions"

# =============================================================================
# 10. ML / Analytics
# =============================================================================
section "10. ML — Machine Learning & Analytics"

test_get  "/api/ml/status"
test_get  "/api/ml/models"
test_get  "/api/ml/anomalies"
test_get  "/api/ml/anomalies/config"
test_get  "/api/ml/config"

# =============================================================================
# 11. ROS2 Robotics
# =============================================================================
section "11. ROS2 — Robotics Bridge"

test_get  "/api/ros2/bridge/status"
test_get  "/api/ros2/topics"
test_get  "/api/ros2/services"
test_get  "/api/ros2/orchestrator/status"
test_get  "/api/ros2/cells"
test_get  "/api/ros2/robots"

# =============================================================================
# 12. CRM
# =============================================================================
section "12. CRM — Customer Relationship Management"

test_get  "/api/crm/dashboard"
test_get  "/api/crm/customers"
test_get  "/api/crm/contacts"
test_get  "/api/crm/activities"

# =============================================================================
# 13. Simulation
# =============================================================================
section "13. Simulation"

test_get  "/api/simulation/parameters"
test_get  "/api/simulation/machines"

# =============================================================================
# 14. Web Pages
# =============================================================================
section "14. Web Pages (HTML)"

SAVED_TOKEN="$TOKEN"
TOKEN=""

test_get  "/"
test_get  "/scada/machines"
test_get  "/scada/alarms"
test_get  "/scada/historian"
test_get  "/scada/recipes"
test_get  "/mes/work-orders"
test_get  "/mes/scheduling"
test_get  "/mes/oee"
test_get  "/mes/kanban"
test_get  "/erp/sales-orders"
test_get  "/erp/inventory"
test_get  "/erp/budget"
test_get  "/qms/documents"
test_get  "/qms/ncr"
test_get  "/qms/spc"
test_get  "/cmms/assets"
test_get  "/cmms/work-orders"
test_get  "/cmms/pm-calendar"
test_get  "/lego/catalog"
test_get  "/lego/designer"
test_get  "/unity/viewer"
test_get  "/ml/anomaly"

TOKEN="$SAVED_TOKEN"

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
printf "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
TOTAL=$((PASS + FAIL + SKIP))
printf "${BOLD}Results:${NC}  "
printf "${GREEN}%d passed${NC}  " "$PASS"
printf "${RED}%d failed${NC}  " "$FAIL"
printf "(%d total)\n" "$TOTAL"
printf "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
