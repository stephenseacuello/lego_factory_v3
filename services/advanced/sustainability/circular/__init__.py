"""
Circular Economy Module for LegoMCP v5.0

PhD-Level Research Implementation:
- Material Flow Analysis (MFA) based on ISO 14040/14044
- Recycling Rate Optimization using multi-objective algorithms
- Design for Disassembly (DfD) scoring and optimization
- Circular Economy Indicators (CEI) per Ellen MacArthur Foundation

Research Contributions:
- Novel closed-loop material recovery optimization
- Integration of circularity metrics with production scheduling
- Real-time circular economy performance dashboards

Standards Compliance:
- ISO 14040/14044 (Life Cycle Assessment)
- ISO 14006 (Eco-design)
- BS 8001 (Circular Economy Framework)
"""

from .material_flow import MaterialFlowAnalyzer, MaterialNode, MaterialFlow
from .recycling_optimizer import RecyclingOptimizer, RecyclingScenario
from .design_for_disassembly import DfDAnalyzer, DfDScore, DisassemblyStep

__all__ = [
    'MaterialFlowAnalyzer',
    'MaterialNode',
    'MaterialFlow',
    'RecyclingOptimizer',
    'RecyclingScenario',
    'DfDAnalyzer',
    'DfDScore',
    'DisassemblyStep'
]
