#!/bin/bash
# LEGO Factory v3 - Test Commands
# Run: chmod +x test_commands.sh && ./test_commands.sh
# Or run individual sections by copying the commands

set -e

echo "=============================================="
echo "LEGO Factory v3 - Comprehensive Test Suite"
echo "=============================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

section() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
    echo ""
}

test_cmd() {
    echo -e "${YELLOW}> $1${NC}"
    eval "$2"
    echo ""
}

# ============================================
# 1. HEALTH & INFRASTRUCTURE
# ============================================
section "1. Health & Infrastructure"

test_cmd "Health check" \
    'curl -s http://localhost:5000/health | jq'

test_cmd "Database version" \
    'docker exec lego-factory-postgres psql -U lego -d lego_factory -c "SELECT version();"'

test_cmd "TimescaleDB check" \
    'docker exec lego-factory-postgres psql -U lego -d lego_factory -c "SELECT extname, extversion FROM pg_extension WHERE extname = '\''timescaledb'\'';"'

test_cmd "Redis ping" \
    'docker exec lego-factory-redis redis-cli ping'

# ============================================
# 2. SCADA - ALARMS
# ============================================
section "2. SCADA - Alarms"

test_cmd "Get active alarms" \
    'curl -s http://localhost:5000/api/scada/alarms/active | jq'

test_cmd "Acknowledge alarm ALM-001" \
    'curl -s -X POST http://localhost:5000/api/scada/alarms/ALM-001/acknowledge -H "Content-Type: application/json" -d '\''{"user_id": "operator1"}'\'' | jq'

# ============================================
# 3. MES - WORK ORDERS
# ============================================
section "3. MES - Work Orders"

test_cmd "List work orders" \
    'curl -s http://localhost:5000/api/mes/work-orders | jq'

test_cmd "Create work order" \
    'curl -s -X POST http://localhost:5000/api/mes/work-orders -H "Content-Type: application/json" -d '\''{"product_id":"brick_2x4_yellow","quantity_ordered":250,"priority":2,"due_date":"2026-01-25","customer_id":"CUST003","description":"Custom yellow bricks"}'\'' | jq'

test_cmd "Release work order 1" \
    'curl -s -X POST http://localhost:5000/api/mes/work-orders/1/release | jq'

# ============================================
# 4. MES - RECIPES
# ============================================
section "4. MES - Recipes"

test_cmd "List recipes" \
    'curl -s http://localhost:5000/api/mes/recipes | jq'

test_cmd "Create recipe" \
    'curl -s -X POST http://localhost:5000/api/mes/recipes -H "Content-Type: application/json" -d '\''{"name":"1x1 Brick Fast","product_id":"brick_1x1","version":"1.0","operations":[{"sequence":10,"name":"Slice","type":"design","duration_min":2},{"sequence":20,"name":"Print","type":"printing_fdm","duration_min":15}],"parameters":{"infill":15,"layer_height":0.25}}'\'' | jq'

test_cmd "Get recipe RCP-001" \
    'curl -s http://localhost:5000/api/mes/recipes/RCP-001 | jq'

test_cmd "Download recipe to machine" \
    'curl -s "http://localhost:5000/api/mes/recipes/RCP-001/download?machine_id=prusa_mk4_1" | jq'

# ============================================
# 5. MES - SCHEDULING
# ============================================
section "5. MES - Scheduling"

test_cmd "Get Gantt data" \
    'curl -s http://localhost:5000/api/mes/scheduling/gantt | jq'

test_cmd "Get capacity" \
    'curl -s http://localhost:5000/api/mes/scheduling/capacity | jq'

test_cmd "Get jobs" \
    'curl -s http://localhost:5000/api/mes/jobs | jq'

# ============================================
# 6. MES - OEE
# ============================================
section "6. MES - OEE"

test_cmd "Get OEE metrics" \
    'curl -s http://localhost:5000/api/mes/oee | jq'

test_cmd "Get OEE for specific machine" \
    'curl -s "http://localhost:5000/api/mes/oee?machine_id=prusa_mk4_1" | jq'

# ============================================
# 7. ERP - CUSTOMERS
# ============================================
section "7. ERP - Customers"

test_cmd "List customers" \
    'curl -s http://localhost:5000/api/erp/customers | jq'

test_cmd "Create customer" \
    'curl -s -X POST http://localhost:5000/api/erp/customers -H "Content-Type: application/json" -d '\''{"customer_id":"CUST004","name":"Brick World Inc","email":"orders@brickworld.com","phone":"555-BRICK"}'\'' | jq'

# ============================================
# 8. ERP - SALES ORDERS
# ============================================
section "8. ERP - Sales Orders"

test_cmd "List sales orders" \
    'curl -s http://localhost:5000/api/erp/sales-orders | jq'

test_cmd "Create sales order" \
    'curl -s -X POST http://localhost:5000/api/erp/sales-orders -H "Content-Type: application/json" -d '\''{"customer_id":"CUST001","lines":[{"item_id":"brick_2x4_red","quantity":1000,"unit_price":0.35},{"item_id":"brick_2x2_blue","quantity":500,"unit_price":0.25}]}'\'' | jq'

test_cmd "Confirm sales order SO-001" \
    'curl -s -X POST http://localhost:5000/api/erp/sales-orders/SO-001/confirm | jq'

# ============================================
# 9. ERP - INVENTORY
# ============================================
section "9. ERP - Inventory"

test_cmd "List items" \
    'curl -s http://localhost:5000/api/erp/items | jq'

test_cmd "Create item" \
    'curl -s -X POST http://localhost:5000/api/erp/items -H "Content-Type: application/json" -d '\''{"item_id":"brick_2x6_green","name":"2x6 Brick Green","category":"standard_brick","unit_cost":0.20,"unit_price":0.45,"quantity_on_hand":500}'\'' | jq'

# ============================================
# 10. ERP - MRP
# ============================================
section "10. ERP - MRP"

test_cmd "Run MRP" \
    'curl -s -X POST http://localhost:5000/api/erp/mrp/run -H "Content-Type: application/json" -d '\''{"horizon_days":90,"include_safety_stock":true}'\'' | jq'

test_cmd "Get MRP runs" \
    'curl -s http://localhost:5000/api/erp/mrp/runs | jq'

test_cmd "Get shortages" \
    'curl -s http://localhost:5000/api/erp/mrp/shortages | jq'

# ============================================
# 11. LEGO - BRICK DESIGN
# ============================================
section "11. LEGO - Brick Design"

test_cmd "Get brick catalog" \
    'curl -s http://localhost:5000/api/lego/catalog | jq'

test_cmd "Get brick dimensions 2x4" \
    'curl -s http://localhost:5000/api/lego/dimensions/2x4 | jq'

test_cmd "Create custom design" \
    'curl -s -X POST http://localhost:5000/api/lego/design -H "Content-Type: application/json" -d '\''{"brick_type":"custom","width_studs":3,"length_studs":5,"height_plates":3,"color":"#FF6600","name":"Custom 3x5 Orange"}'\'' | jq'

# ============================================
# 12. ROS2 / ROBOTICS
# ============================================
section "12. ROS2 / Robotics"

test_cmd "Bridge status" \
    'curl -s http://localhost:5000/api/ros2/bridge/status | jq'

test_cmd "List robots" \
    'curl -s http://localhost:5000/api/ros2/robots | jq'

test_cmd "Create pick-place task" \
    'curl -s -X POST http://localhost:5000/api/ros2/tasks -H "Content-Type: application/json" -d '\''{"task_type":"pick_and_place","robot_id":"niryo_ned2","pick_position":{"x":0.3,"y":0.1,"z":0.05},"place_position":{"x":0.3,"y":-0.1,"z":0.05}}'\'' | jq'

# ============================================
# 13. UNITY DIGITAL TWIN
# ============================================
section "13. Unity Digital Twin"

test_cmd "Get scene state" \
    'curl -s http://localhost:5000/api/unity/scene | jq'

test_cmd "List entities" \
    'curl -s http://localhost:5000/api/unity/entities | jq'

# ============================================
# 14. QMS - QUALITY
# ============================================
section "14. QMS - Quality Management"

test_cmd "List documents" \
    'curl -s http://localhost:5000/api/qms/documents | jq'

test_cmd "Create NCR" \
    'curl -s -X POST http://localhost:5000/api/qms/ncr -H "Content-Type: application/json" -d '\''{"title":"Dimensional variance","description":"Studs measuring 4.82mm instead of 4.8mm","severity":"minor","work_order_id":"WO-20240115-001","detected_by":"QC_Inspector_1","quantity_affected":50}'\'' | jq'

# ============================================
# 15. ML - ANOMALY DETECTION
# ============================================
section "15. ML - Anomaly Detection"

test_cmd "ML status" \
    'curl -s http://localhost:5000/api/ml/status | jq'

test_cmd "Detect anomaly" \
    'curl -s -X POST http://localhost:5000/api/ml/anomaly/detect -H "Content-Type: application/json" -d '\''{"sensor_data":{"temperature":215.5,"vibration_x":0.02,"vibration_y":0.03,"current_draw":2.5}}'\'' | jq'

# ============================================
# 16. MCP - AI TOOLS
# ============================================
section "16. MCP - AI Tools"

test_cmd "List MCP tools" \
    'curl -s http://localhost:5000/api/mcp/tools | jq'

test_cmd "Execute MCP tool" \
    'curl -s -X POST http://localhost:5000/api/mcp/execute -H "Content-Type: application/json" -d '\''{"tool":"get_active_alarms","arguments":{}}'\'' | jq'

# ============================================
# 17. WEB INTERFACES
# ============================================
section "17. Web Interface Status"

test_cmd "Flask App (5000)" \
    'curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5000/'

test_cmd "Grafana (3000)" \
    'curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/'

test_cmd "noVNC (6080)" \
    'curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:6080/'

test_cmd "Slicer (8766)" \
    'curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8766/ || echo "May not have root endpoint"'

echo ""
echo -e "${GREEN}=============================================="
echo "All tests completed!"
echo "=============================================="
echo ""
echo "Web Interfaces:"
echo "  - Main App:    http://localhost:5000"
echo "  - Grafana:     http://localhost:3000  (admin/admin)"
echo "  - noVNC/ROS2:  http://localhost:6080  (password: lego)"
echo -e "==============================================${NC}"
