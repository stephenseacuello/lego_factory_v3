# Changelog

All notable changes to the CNC SCADA Predictive Overlay package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-15

### Added
- AR maintenance calendar with 3D event markers
- Event type visualization (urgent, scheduled, preventive, predicted)
- Confidence-based filtering for predictions
- Animated marker appearance and pulsing effects
- Click handling for event details
- Event list UI with scrolling
- Summary statistics display
- Tool wear indicator with visual feedback
- 3D tool visualization with material blending
- Wear particle effects
- Remaining useful life (RUL) prediction
- Confidence intervals for predictions
- Tool change trigger functionality
- Wear history tracking
- Threshold-based warnings (caution, critical)
- Anomaly marker system
- Severity-based visualization (low, medium, high, critical)
- Anomaly type filtering (vibration, temperature, force, quality, predicted)
- Auto-acknowledgment with timeout
- Pulsing effects for critical anomalies
- Rotating marker animations
- Active anomaly tracking
- Health score display system
- Overall health gauge with smooth animations
- Subsystem health gauges (mechanical, electrical, thermal, vibration)
- Color-coded health indicators
- 3D health hologram visualization
- Health history tracking
- Multi-factor health analysis
- Status summary with issues display
- Warning panel for critical health
- Statistics APIs for all components
- Comprehensive event system
- AR Foundation integration
- Unity Package Manager support
- Assembly definition for code organization

### Features
- **AR Visualization**: Augmented reality overlays for maintenance insights
- **Predictive Analytics**: ML-driven predictions for proactive maintenance
- **Multi-Factor Health**: Comprehensive machine health monitoring
- **Real-Time Anomalies**: Instant detection and visualization of abnormalities
- **Tool Life Management**: Prevent failures with wear prediction
- **Confidence Filtering**: Focus on high-confidence predictions
- **Interactive 3D**: Clickable markers with detailed information

### Documentation
- Comprehensive README with integration guide
- ML prediction interpretation guide
- AR setup instructions
- Configuration examples
- Backend API specification
- Troubleshooting guide

### Dependencies
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- AR Foundation 4.2.7+ (for AR features)
- Newtonsoft.Json

### Known Issues
- AR features require ARCore (Android) or ARKit (iOS)
- Health hologram may cause performance issues on low-end devices

### Breaking Changes
- N/A (initial release)

## [Unreleased]

### Planned Features
- Computer vision for tool wear measurement
- Advanced anomaly pattern recognition
- Maintenance cost tracking
- Spare parts inventory integration
- Maintenance technician AR guidance
- Historical trend analysis
- Predictive maintenance calendar sync
- Integration with CMMS systems
