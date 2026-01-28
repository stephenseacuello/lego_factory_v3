# micro-ROS Multi-Transport Setup for ESP32-S3

Complete micro-ROS setup supporting **Serial, WiFi/UDP, and WiFi/TCP** transports.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Your Mac                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐      ┌──────────────────────────────────────┐ │
│  │   ESP32-S3      │      │        Docker                        │ │
│  │                 │      │  ┌──────────────────────────────┐   │ │
│  │  WiFi UDP ──────────────►│ microros-agent-udp  :8888    │   │ │
│  │  WiFi TCP ──────────────►│ microros-agent-tcp  :8889    │   │ │
│  │  USB Serial ────────────►│ microros-agent-serial        │   │ │
│  │                 │      │  └──────────────┬───────────────┘   │ │
│  │  Publishes:     │      │                 │                    │ │
│  │  /sensors/imu   │      │                 ▼                    │ │
│  │  /sensors/temp  │      │  ┌──────────────────────────────┐   │ │
│  └─────────────────┘      │  │      ROS 2 Jazzy             │   │ │
│                           │  │  ros2 topic echo /sensors/imu│   │ │
│                           │  └──────────────────────────────┘   │ │
│                           └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start (WiFi UDP - Recommended)

### 1. Configure WiFi credentials

Edit `arduino/cnc_sensor_node/include/config.h`:

```c
#define WIFI_SSID     "ISECapstone"      // Your WiFi SSID
#define WIFI_PASSWORD "j0shf1sh"         // Your WiFi password
#define AGENT_IP      "192.168.1.100"    // Your Mac's IP address
```

Find your Mac's IP:
```bash
./launch_microros.sh ip
# or
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### 2. Start micro-ROS Agent

```bash
# Using helper script
./launch_microros.sh udp

# Or using docker-compose directly
docker-compose -f docker-compose.microros.yml up -d microros-agent-udp
```

### 3. Flash ESP32-S3

```bash
cd arduino/cnc_sensor_node

# Build and upload (WiFi UDP)
pio run -e esp32s3_wifi_udp -t upload

# Monitor serial output
pio device monitor
```

### 4. Verify in ROS 2

```bash
# Open diagnostics shell
./launch_microros.sh diag

# Inside the shell:
ros2 topic list
ros2 topic echo /sensors/imu
ros2 topic hz /sensors/imu
```

## Transport Options

| Transport | Command | Agent | Use Case |
|-----------|---------|-------|----------|
| **WiFi UDP** | `pio run -e esp32s3_wifi_udp` | `./launch_microros.sh udp` | Recommended for most uses |
| **WiFi TCP** | `pio run -e esp32s3_wifi_tcp` | `./launch_microros.sh tcp` | More reliable, higher latency |
| **USB Serial** | `pio run -e esp32s3_serial` | `./launch_microros.sh serial` | Development, no WiFi needed |

## Serial Transport Setup

For USB Serial, the ESP32-S3's USB port is used for micro-ROS communication (no debug output during operation).

1. **Find your device:**
   ```bash
   ./launch_microros.sh find
   # Look for /dev/tty.usbmodem* (ESP32-S3 native USB)
   ```

2. **Update docker-compose.microros.yml** with your device path:
   ```yaml
   devices:
     - /dev/tty.usbmodem14101:/dev/ttyUSB0
   ```

3. **Flash and run:**
   ```bash
   pio run -e esp32s3_serial -t upload
   ./launch_microros.sh serial
   ```

## File Structure

```
micro_ros_examples/
├── docker-compose.microros.yml     # Docker agents for all transports
├── launch_microros.sh              # Helper script
├── README.md                       # This file
└── arduino/
    └── cnc_sensor_node/
        ├── platformio.ini          # Build configurations
        ├── include/
        │   └── config.h            # WiFi & agent settings
        └── src/
            └── main.cpp            # Multi-transport sensor node
```

## PlatformIO Environments

| Environment | Board | Transport |
|-------------|-------|-----------|
| `esp32s3_wifi_udp` | ESP32-S3 DevKitC | WiFi UDP (default) |
| `esp32s3_wifi_tcp` | ESP32-S3 DevKitC | WiFi TCP |
| `esp32s3_serial` | ESP32-S3 DevKitC | USB Serial |
| `esp32_wifi_udp` | ESP32 DevKit | WiFi UDP |
| `esp32_serial` | ESP32 DevKit | USB Serial |

## Helper Script Commands

```bash
./launch_microros.sh udp       # Start UDP agent
./launch_microros.sh tcp       # Start TCP agent
./launch_microros.sh serial    # Start Serial agent
./launch_microros.sh combined  # Start UDP + TCP
./launch_microros.sh status    # Show running agents
./launch_microros.sh logs      # Follow agent logs
./launch_microros.sh stop      # Stop all agents
./launch_microros.sh diag      # Open ROS 2 diagnostics shell
./launch_microros.sh find      # Find serial devices
./launch_microros.sh ip        # Show your Mac's IP
```

## Troubleshooting

### ESP32 not connecting to agent

1. **Check WiFi connection:**
   - Monitor serial output: `pio device monitor`
   - Verify SSID/password in `config.h`

2. **Check agent IP:**
   - Run `./launch_microros.sh ip`
   - Update `AGENT_IP` in `config.h`

3. **Check agent is running:**
   - Run `./launch_microros.sh status`
   - Check logs: `./launch_microros.sh logs`

4. **Firewall:**
   - Ensure ports 8888 (UDP) and 8889 (TCP) are open

### Serial agent not starting

1. **Find correct device path:**
   ```bash
   ./launch_microros.sh find
   ```

2. **Update docker-compose.microros.yml** with the correct path

3. **Check permissions:**
   - On Mac, Docker Desktop should have USB access by default

### Topics not appearing in ROS 2

1. **Verify agent sees connection:**
   ```bash
   ./launch_microros.sh logs
   # Look for "session established" messages
   ```

2. **Check topic list:**
   ```bash
   ./launch_microros.sh diag
   # Then: ros2 topic list
   ```

### LED Behavior

| Pattern | Meaning |
|---------|---------|
| Slow blink (500ms) | Waiting for agent |
| Fast toggle | Connected, publishing |
| Very fast blink (100ms) | Error state |

## Adding Custom Messages

To use `cnc_interfaces` messages on ESP32:

1. Generate micro-ROS headers for your custom messages
2. Copy to `arduino/cnc_sensor_node/lib/`
3. Include in your code:
   ```cpp
   #include <cnc_interfaces/msg/sensor_reading.h>
   ```

## Performance

| Transport | Typical Latency | Throughput |
|-----------|-----------------|------------|
| Serial | ~1ms | High |
| WiFi UDP | 5-20ms | Medium |
| WiFi TCP | 10-50ms | Medium |

For 50 Hz sensor data, WiFi UDP works well. For higher rates or lower latency, use Serial.
