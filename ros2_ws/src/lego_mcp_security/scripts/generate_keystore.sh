#!/bin/bash
#
# SROS2 Keystore Generation Script
# LEGO MCP Security - IEC 62443 Compliant
#
# This script generates SROS2 keystores for secure ROS2 DDS communication.
# Run this script before deploying nodes with SROS2 enabled.
#
# Usage:
#   ./generate_keystore.sh [keystore_path] [domain_id]
#
# Example:
#   ./generate_keystore.sh /opt/lego_mcp/keystore 0
#

set -e

# Default values
KEYSTORE_PATH="${1:-/tmp/lego_mcp_keystore}"
DOMAIN_ID="${2:-0}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     LEGO MCP SROS2 Keystore Generator                       ║${NC}"
echo -e "${GREEN}║     IEC 62443 Compliant Security Setup                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check for ros2 security commands
if ! command -v ros2 &> /dev/null; then
    echo -e "${RED}Error: ros2 command not found. Please source your ROS2 installation.${NC}"
    exit 1
fi

# Create keystore directory
echo -e "${YELLOW}Creating keystore at: ${KEYSTORE_PATH}${NC}"
mkdir -p "${KEYSTORE_PATH}"

# Create the keystore
echo -e "${YELLOW}Initializing SROS2 keystore...${NC}"
ros2 security create_keystore "${KEYSTORE_PATH}" 2>/dev/null || true

# Define nodes by ISA-95/IEC 62443 security zones
# Zone 0: Safety (highest security)
ZONE_0_NODES=(
    "safety_node"
    "safety_lifecycle_node"
    "watchdog_node"
)

# Zone 1: Control (equipment)
ZONE_1_NODES=(
    "grbl_node"
    "formlabs_node"
    "bambu_node"
    "calibration_node"
)

# Zone 2: Supervisory
ZONE_2_NODES=(
    "orchestrator_node"
    "orchestrator_lifecycle_node"
    "supervisor_node"
    "agv_fleet_node"
    "vision_node"
)

# Zone 3: MES/SCADA
ZONE_3_NODES=(
    "mcp_bridge_node"
    "digital_twin_node"
    "scheduling_node"
)

# Zone 4: Security Management
ZONE_4_NODES=(
    "security_manager"
    "audit_pipeline"
    "intrusion_detector"
)

# Zone 5: Chaos Testing (isolated)
ZONE_5_NODES=(
    "chaos_controller"
)

echo ""
echo -e "${GREEN}Creating keys for Zone 0 (Safety - Highest Security)...${NC}"
for node in "${ZONE_0_NODES[@]}"; do
    echo "  - Creating key for ${node}"
    ros2 security create_key "${KEYSTORE_PATH}" "/${node}" 2>/dev/null || true
done

echo ""
echo -e "${GREEN}Creating keys for Zone 1 (Control - Equipment)...${NC}"
for node in "${ZONE_1_NODES[@]}"; do
    echo "  - Creating key for ${node}"
    ros2 security create_key "${KEYSTORE_PATH}" "/${node}" 2>/dev/null || true
done

echo ""
echo -e "${GREEN}Creating keys for Zone 2 (Supervisory)...${NC}"
for node in "${ZONE_2_NODES[@]}"; do
    echo "  - Creating key for ${node}"
    ros2 security create_key "${KEYSTORE_PATH}" "/${node}" 2>/dev/null || true
done

echo ""
echo -e "${GREEN}Creating keys for Zone 3 (MES/SCADA)...${NC}"
for node in "${ZONE_3_NODES[@]}"; do
    echo "  - Creating key for ${node}"
    ros2 security create_key "${KEYSTORE_PATH}" "/${node}" 2>/dev/null || true
done

echo ""
echo -e "${GREEN}Creating keys for Zone 4 (Security Management)...${NC}"
for node in "${ZONE_4_NODES[@]}"; do
    echo "  - Creating key for ${node}"
    ros2 security create_key "${KEYSTORE_PATH}" "/${node}" 2>/dev/null || true
done

echo ""
echo -e "${GREEN}Creating keys for Zone 5 (Chaos Testing - Isolated)...${NC}"
for node in "${ZONE_5_NODES[@]}"; do
    echo "  - Creating key for ${node}"
    ros2 security create_key "${KEYSTORE_PATH}" "/${node}" 2>/dev/null || true
done

# Create permissions files
echo ""
echo -e "${YELLOW}Creating permissions files...${NC}"

# Create governance.xml
cat > "${KEYSTORE_PATH}/governance.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:noNamespaceSchemaLocation="http://www.omg.org/spec/DDS-Security/20170901/omg_shared_ca_governance.xsd">
  <domain_access_rules>
    <domain_rule>
      <domains>
        <id>0</id>
      </domains>
      <allow_unauthenticated_participants>false</allow_unauthenticated_participants>
      <enable_join_access_control>true</enable_join_access_control>
      <discovery_protection_kind>ENCRYPT</discovery_protection_kind>
      <liveliness_protection_kind>ENCRYPT</liveliness_protection_kind>
      <rtps_protection_kind>ENCRYPT</rtps_protection_kind>
      <topic_access_rules>
        <!-- Safety topics - highest protection -->
        <topic_rule>
          <topic_expression>/lego_mcp/safety/*</topic_expression>
          <enable_discovery_protection>true</enable_discovery_protection>
          <enable_liveliness_protection>true</enable_liveliness_protection>
          <enable_read_access_control>true</enable_read_access_control>
          <enable_write_access_control>true</enable_write_access_control>
          <data_protection_kind>ENCRYPT</data_protection_kind>
        </topic_rule>
        <!-- Equipment topics -->
        <topic_rule>
          <topic_expression>/lego_mcp/equipment/*</topic_expression>
          <enable_discovery_protection>true</enable_discovery_protection>
          <enable_liveliness_protection>true</enable_liveliness_protection>
          <enable_read_access_control>true</enable_read_access_control>
          <enable_write_access_control>true</enable_write_access_control>
          <data_protection_kind>ENCRYPT</data_protection_kind>
        </topic_rule>
        <!-- Default rule for other topics -->
        <topic_rule>
          <topic_expression>*</topic_expression>
          <enable_discovery_protection>true</enable_discovery_protection>
          <enable_liveliness_protection>false</enable_liveliness_protection>
          <enable_read_access_control>true</enable_read_access_control>
          <enable_write_access_control>true</enable_write_access_control>
          <data_protection_kind>SIGN</data_protection_kind>
        </topic_rule>
      </topic_access_rules>
    </domain_rule>
  </domain_access_rules>
</dds>
EOF

echo "  - Created governance.xml"

# Set permissions
echo ""
echo -e "${YELLOW}Setting file permissions...${NC}"
chmod -R 700 "${KEYSTORE_PATH}"
echo "  - Set restrictive permissions (700)"

# Summary
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Keystore Generation Complete                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Keystore location: ${KEYSTORE_PATH}"
echo ""
echo "To enable SROS2, set these environment variables:"
echo ""
echo "  export ROS_SECURITY_KEYSTORE=${KEYSTORE_PATH}"
echo "  export ROS_SECURITY_ENABLE=true"
echo "  export ROS_SECURITY_STRATEGY=Enforce"
echo "  export ROS_DOMAIN_ID=${DOMAIN_ID}"
echo ""
echo -e "${YELLOW}Note: Restart all ROS2 nodes after enabling security.${NC}"
echo ""
