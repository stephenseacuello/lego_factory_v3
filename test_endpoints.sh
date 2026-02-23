#!/bin/bash
# LEGO Factory - Endpoint Test Script
# Usage: bash test_endpoints.sh

BASE="http://localhost:5000"
PASS=0
FAIL=0
ERRORS=""

test_url() {
    local label="$1"
    local url="$2"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null)
    if [ "$code" = "200" ]; then
        echo "  PASS  $label ($url)"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  $label ($url) -> HTTP $code"
        FAIL=$((FAIL + 1))
        ERRORS="$ERRORS\n  - $label: $url (HTTP $code)"
    fi
}

echo "============================================"
echo " LEGO Factory v3 - Endpoint Tests"
echo "============================================"
echo ""

echo "--- Health ---"
test_url "Health Check" "$BASE/health"

echo ""
echo "--- Web Pages ---"
test_url "Dashboard" "$BASE/"
test_url "Scheduling" "$BASE/mes/scheduling"
test_url "Work Orders" "$BASE/mes/work-orders"
test_url "Dispatch" "$BASE/mes/dispatch"
test_url "Process Monitor" "$BASE/mes/process-monitor"
test_url "OEE" "$BASE/mes/oee"
test_url "Resources" "$BASE/mes/resources"
test_url "Materials" "$BASE/mes/materials"
test_url "Genealogy" "$BASE/mes/genealogy"
test_url "Performance" "$BASE/mes/performance"
test_url "Shift Report" "$BASE/mes/shift-report"
test_url "Operator View" "$BASE/mes/operator"
test_url "Algorithm Compare" "$BASE/mes/algorithm-compare"
test_url "SPC Charts" "$BASE/qms/spc"
test_url "Inspections" "$BASE/qms/inspections"
test_url "Documents" "$BASE/qms/documents"
test_url "NCR/CAPA" "$BASE/qms/ncr"
test_url "CMMS Assets" "$BASE/cmms/assets"
test_url "CMMS Work Orders" "$BASE/cmms/work-orders"
test_url "SCADA Machines" "$BASE/scada/machines"
test_url "SCADA Alarms" "$BASE/scada/alarms"
test_url "SCADA Historian" "$BASE/scada/historian"
test_url "SCADA Sensors" "$BASE/scada/sensors"
test_url "SCADA Recipes" "$BASE/scada/recipes"
test_url "SCADA GCode" "$BASE/scada/gcode"
test_url "Lego Catalog" "$BASE/lego/catalog"
test_url "Lego Designer" "$BASE/lego/designer"
test_url "Unity Viewer" "$BASE/unity/viewer"
test_url "ML Fingerprint" "$BASE/ml/fingerprint"
test_url "ML Anomaly" "$BASE/ml/anomaly"
test_url "Login" "$BASE/login"
test_url "ERP Sales Orders" "$BASE/erp/sales-orders"
test_url "ERP Inventory" "$BASE/erp/inventory"
test_url "ERP MRP" "$BASE/erp/mrp"
test_url "ERP Costing" "$BASE/erp/costing"
test_url "ERP Vendors" "$BASE/erp/vendors"
test_url "ERP Budget" "$BASE/erp/budget"
test_url "ERP Job Costing" "$BASE/erp/job-costing"
test_url "ERP Cash Flow" "$BASE/erp/cashflow"
test_url "ERP Fixed Assets" "$BASE/erp/fixed-assets"
test_url "SCADA Downtime" "$BASE/scada/downtime"
test_url "CMMS Reliability" "$BASE/cmms/reliability"
test_url "CMMS PM Calendar" "$BASE/cmms/pm-calendar"
test_url "QMS Supplier Scorecard" "$BASE/qms/supplier-scorecard"
test_url "MES Capacity" "$BASE/mes/capacity"
test_url "MES Kanban" "$BASE/mes/kanban"
test_url "MES Time Clock" "$BASE/mes/timeclock"
test_url "MES Line Balance" "$BASE/mes/line-balance"
test_url "MES Setup Analysis" "$BASE/mes/setup-analysis"
test_url "MES Rework" "$BASE/mes/rework"
test_url "MES Shift Handover" "$BASE/mes/shift-handover"

echo ""
echo "--- API Endpoints ---"
test_url "API: Machines" "$BASE/api/scada/machines"
test_url "API: Work Orders" "$BASE/api/mes/work-orders"
test_url "API: Scheduling Gantt" "$BASE/api/mes/scheduling/gantt"
test_url "API: Resources" "$BASE/api/mes/resources"
test_url "API: Materials" "$BASE/api/mes/materials"
test_url "API: SPC Charts" "$BASE/api/qms/spc/charts"
test_url "API: Inspections" "$BASE/api/qms/inspections"
test_url "API: NCRs" "$BASE/api/qms/ncrs"
test_url "API: Documents" "$BASE/api/qms/documents"
test_url "API: Assets" "$BASE/api/cmms/assets"
test_url "API: Sales Orders" "$BASE/api/erp/sales-orders"
test_url "API: Inventory" "$BASE/api/erp/inventory"

echo ""
echo "============================================"
echo " Results: $PASS passed, $FAIL failed"
echo "============================================"
if [ $FAIL -gt 0 ]; then
    echo ""
    echo "Failed endpoints:"
    echo -e "$ERRORS"
fi
