# Changelog

All notable changes to the CNC SCADA Scheduling UI package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-15

### Added
- Interactive Gantt chart with timeline visualization
- Dynamic machine row generation
- Job block rendering with color coding
- Timeline header with date/time markers
- Configurable time range and zoom controls
- Drag-and-drop job rescheduling
- Ghost image feedback during drag
- Grid snapping for precise positioning
- Real-time conflict detection
- Server-side validation integration
- Machine change support with validation
- Undo/redo for reschedule operations
- OR-Tools optimization integration
- Multiple algorithm support (CP-SAT, Genetic, Simulated Annealing)
- Multi-objective optimization (makespan, tardiness, utilization)
- Constraint configuration (dependencies, skills, machine changes)
- Progress tracking with animated status updates
- Machine capacity visualization
- Real-time utilization gauges
- Bottleneck detection and highlighting
- Capacity trending over time
- Color-coded utilization levels
- Auto-refresh with configurable intervals
- Job selection and details display
- Schedule statistics and analytics
- Comprehensive event system
- Export capabilities for schedules
- Unity Package Manager support
- Assembly definition for code organization

### Features
- **Interactive Scheduling**: Drag-drop interface for intuitive rescheduling
- **Advanced Optimization**: OR-Tools integration for intelligent scheduling
- **Real-Time Updates**: Live schedule and capacity monitoring
- **Conflict Prevention**: Automatic validation prevents scheduling errors
- **Performance Optimized**: Virtualization for large schedules (100+ jobs)
- **Flexible Configuration**: Support for custom constraints and objectives
- **Multi-Machine Support**: Visualize and manage entire production floors

### Documentation
- Comprehensive README with integration guide
- OR-Tools algorithm comparison
- Optimization best practices
- Configuration examples
- Backend API specification
- Troubleshooting guide

### Dependencies
- Unity 2021.3+
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json

### Known Issues
- Performance may degrade with >200 visible jobs without virtualization
- Complex dependency chains may slow drag validation

### Breaking Changes
- N/A (initial release)

## [Unreleased]

### Planned Features
- Gantt chart export to PDF/PNG
- Advanced filtering and search
- Job templates and recurring schedules
- Resource constraints (tools, materials)
- Multi-site scheduling coordination
- What-if scenario analysis
- Machine learning schedule recommendations
