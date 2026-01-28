#!/bin/bash
# micro-ROS Agent Launcher
# ========================
# Quick launcher for micro-ROS agents with different transports

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.microros.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=======================================${NC}"
    echo -e "${BLUE}  micro-ROS Agent Launcher${NC}"
    echo -e "${BLUE}=======================================${NC}"
}

print_usage() {
    echo -e "Usage: $0 [COMMAND]"
    echo ""
    echo -e "Commands:"
    echo -e "  ${GREEN}udp${NC}       Start UDP agent (port 8888) - WiFi devices"
    echo -e "  ${GREEN}tcp${NC}       Start TCP agent (port 8889) - WiFi devices"
    echo -e "  ${GREEN}serial${NC}    Start Serial agent - USB devices"
    echo -e "  ${GREEN}combined${NC}  Start UDP + TCP agents"
    echo -e "  ${GREEN}diag${NC}      Open diagnostics shell"
    echo -e "  ${GREEN}status${NC}    Show running agents"
    echo -e "  ${GREEN}logs${NC}      Follow agent logs"
    echo -e "  ${GREEN}stop${NC}      Stop all agents"
    echo -e "  ${GREEN}find${NC}      Find serial devices on Mac"
    echo -e "  ${GREEN}ip${NC}        Show your Mac's IP address"
    echo ""
    echo -e "Examples:"
    echo -e "  $0 udp       # Start UDP agent for WiFi"
    echo -e "  $0 serial    # Start Serial agent for USB"
    echo -e "  $0 logs      # Follow logs"
}

find_serial_devices() {
    echo -e "${YELLOW}Looking for serial devices...${NC}"
    echo ""
    echo -e "${GREEN}USB Serial devices:${NC}"
    ls /dev/tty.usb* /dev/cu.usb* 2>/dev/null || echo "  None found"
    echo ""
    echo -e "${GREEN}USB Modem devices (ESP32-S3 native USB):${NC}"
    ls /dev/tty.usbmodem* /dev/cu.usbmodem* 2>/dev/null || echo "  None found"
    echo ""
    echo -e "${YELLOW}Tip: Update docker-compose.microros.yml with your device path${NC}"
}

show_ip() {
    echo -e "${YELLOW}Your Mac's IP addresses:${NC}"
    echo ""
    ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "  " $2}'
    echo ""
    echo -e "${YELLOW}Update include/config.h with your IP for AGENT_IP${NC}"
}

case "$1" in
    udp)
        print_header
        echo -e "${GREEN}Starting UDP agent on port 8888...${NC}"
        docker-compose -f "$COMPOSE_FILE" up -d microros-agent-udp
        echo ""
        echo -e "${GREEN}UDP agent started!${NC}"
        echo -e "ESP32 should connect to your Mac's IP on port 8888"
        ;;
    tcp)
        print_header
        echo -e "${GREEN}Starting TCP agent on port 8889...${NC}"
        docker-compose -f "$COMPOSE_FILE" --profile tcp up -d
        echo ""
        echo -e "${GREEN}TCP agent started!${NC}"
        ;;
    serial)
        print_header
        echo -e "${YELLOW}Starting Serial agent...${NC}"
        echo -e "${YELLOW}Make sure you've updated the device path in docker-compose.microros.yml${NC}"
        echo ""
        find_serial_devices
        echo ""
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose -f "$COMPOSE_FILE" --profile serial up -d
            echo -e "${GREEN}Serial agent started!${NC}"
        fi
        ;;
    combined)
        print_header
        echo -e "${GREEN}Starting combined UDP + TCP agents...${NC}"
        docker-compose -f "$COMPOSE_FILE" --profile combined up -d
        echo ""
        echo -e "${GREEN}Agents started!${NC}"
        echo -e "  UDP: port 8888"
        echo -e "  TCP: port 8889"
        ;;
    diag)
        print_header
        echo -e "${GREEN}Opening diagnostics shell...${NC}"
        docker-compose -f "$COMPOSE_FILE" --profile diagnostics run --rm microros-diagnostics
        ;;
    status)
        print_header
        echo -e "${GREEN}Running micro-ROS containers:${NC}"
        docker ps --filter "name=microros" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    logs)
        print_header
        echo -e "${GREEN}Following agent logs (Ctrl+C to exit)...${NC}"
        docker-compose -f "$COMPOSE_FILE" logs -f
        ;;
    stop)
        print_header
        echo -e "${YELLOW}Stopping all micro-ROS agents...${NC}"
        docker-compose -f "$COMPOSE_FILE" down
        echo -e "${GREEN}All agents stopped.${NC}"
        ;;
    find)
        print_header
        find_serial_devices
        ;;
    ip)
        print_header
        show_ip
        ;;
    *)
        print_header
        print_usage
        ;;
esac
