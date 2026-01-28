"""
G-code AI Service

Intelligent G-code analysis, generation, and optimization using Claude AI.

Modules:
- analyzer: G-code analysis with Claude for issue detection
- generator: Natural language to G-code generation
- optimizer: AI-driven feed/speed optimization
- validator: Safety validation before execution
- templates: Pre-built machining operation templates
- knowledge_base: Materials, tooling, and machining rules
"""

from .analyzer import GCodeAnalyzer, AnalysisResult, ToolpathIssue
from .generator import GCodeGenerator, GenerationRequest, GeneratedProgram
from .optimizer import GCodeOptimizer, OptimizationSuggestion
from .validator import SafetyValidator, ValidationResult, SafetyIssue

__all__ = [
    # Analyzer
    "GCodeAnalyzer",
    "AnalysisResult",
    "ToolpathIssue",
    # Generator
    "GCodeGenerator",
    "GenerationRequest",
    "GeneratedProgram",
    # Optimizer
    "GCodeOptimizer",
    "OptimizationSuggestion",
    # Validator
    "SafetyValidator",
    "ValidationResult",
    "SafetyIssue",
]
