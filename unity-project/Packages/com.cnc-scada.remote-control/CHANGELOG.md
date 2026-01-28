# Changelog

All notable changes to the CNC SCADA Remote Control package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-15

### Added
- Jog controller with multi-axis support
- Continuous jogging mode (hold to jog)
- Incremental jogging mode (click for fixed distance)
- Wheel/MPG jogging mode
- Configurable jog speeds with slider
- Multi-axis support (X, Y, Z, A, B, C)
- Software limit checking
- Collision detection integration
- Jog speed presets
- MDI (Manual Data Input) console
- Command input with validation
- Command history with persistence
- Auto-complete for G-code commands
- Syntax highlighting
- Command recall functionality
- Client and server-side validation
- Dangerous command filtering
- Program executor with state machine
- Program loading and selection
- Normal execution mode
- Single-step execution mode
- Dry-run simulation mode
- Pause/resume functionality
- Stop with confirmation
- Line-by-line progress tracking
- Execution progress bar
- Current line highlighting
- Error handling with auto-pause
- Emergency stop button
- Visual status indicators
- Confirmation dialog
- Hold-time requirement
- Double-click safety option
- Reset functionality with confirmation
- E-stop event logging
- Pulsing animation for active state
- Priority command queue integration
- Low-latency optimization (<20ms target)
- Binary protocol support
- Regional edge node routing
- Comprehensive event system
- Statistics and diagnostics APIs
- Unity Package Manager support
- Assembly definition for code organization

### Features
- **<20ms Latency**: Optimized command path for real-time control
- **Multi-Mode Jogging**: Flexible jogging options for different use cases
- **Safe Operation**: Multiple safety checks and confirmations
- **Command History**: Never lose executed commands
- **State Machine**: Robust program execution with error handling
- **Emergency Stop**: Quick access to machine safety controls
- **Auto-Complete**: Speed up MDI with intelligent suggestions

### Documentation
- Comprehensive README with integration guide
- Latency optimization guide
- Safety configuration best practices
- Command authorization setup
- Backend API specification
- Troubleshooting guide

### Dependencies
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json

### Known Issues
- Binary protocol requires backend support (not available in all deployments)
- High network latency (>100ms) may impact jog responsiveness

### Breaking Changes
- N/A (initial release)

### Security Considerations
- All control operations require authentication
- Command-level authorization recommended
- Rate limiting should be implemented server-side
- E-stop events should be logged for audit

## [Unreleased]

### Planned Features
- Gamepad/joystick support for jogging
- MPG (Manual Pulse Generator) integration
- Voice command support
- Macro recording and playback
- Multi-machine control
- Advanced program editor
- Touchscreen optimization
- VR control interface
- Force feedback for jogging
