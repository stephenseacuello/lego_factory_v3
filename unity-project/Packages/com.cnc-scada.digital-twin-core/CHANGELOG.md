# Changelog

All notable changes to the CNC SCADA Digital Twin Core package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-15

### Added
- ISO 23247 compliant state handling with 60Hz updates
- Binary protocol support with FlatBuffers serialization
- State interpolation and velocity-based prediction
- 6-axis kinematics animator (X, Y, Z, A, B, C)
- Smooth interpolation with configurable animation speed
- Axis limit detection and violation warnings
- Toolpath visualizer with G-code rendering
- LOD (Level of Detail) optimization for large toolpaths
- Frustum culling for off-screen path segments
- Motion type coloring (rapid, linear, arc CW/CCW)
- Feedrate-based gradient coloring
- Progress tracking with completed segment highlighting
- Sensor overlay renderer for real-time data
- Thermal heatmap generation with GPU texture updates
- Vibration particle system visualization
- Cutting force vector display
- Quality indicator overlays
- Multi-sensor data fusion support
- NetworkUtility for standardized HTTP communication
- Retry logic with exponential backoff
- Comprehensive event system for all components
- Statistics and diagnostics APIs
- Unity Package Manager support
- Assembly definition for proper code organization

### Features
- **60Hz Real-Time Updates**: Smooth visualization with minimal latency
- **ISO 23247 Standard**: International digital twin compliance
- **Performance Optimized**: LOD, culling, and efficient rendering
- **Extensible Architecture**: Event-driven design for easy integration
- **Visual Debugging**: Gizmo visualization for development
- **Platform Agnostic**: Works with any backend following API spec

### Documentation
- Comprehensive README with quick start guide
- API reference for all public methods
- Configuration examples for common scenarios
- Backend API requirements specification
- Troubleshooting guide
- Example usage patterns

### Dependencies
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Newtonsoft.Json

### Known Issues
- None at release

### Breaking Changes
- N/A (initial release)

## [Unreleased]

### Planned Features
- WebGL binary protocol support
- Advanced shader effects for sensor overlays
- Time-series data visualization
- Historical state playback
- Multi-machine synchronization
- VR/AR specific optimizations
