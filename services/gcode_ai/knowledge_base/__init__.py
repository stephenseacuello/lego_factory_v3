"""
Knowledge Base for G-code AI

Contains manufacturing knowledge including:
- materials: Material properties and cutting parameters
- tooling: Tool catalog and specifications
- machining_rules: Best practices and rules
"""

from .materials import MaterialDatabase, Material, CuttingParameters
from .tooling import ToolCatalog, Tool, ToolType
from .machining_rules import MachiningRules, Rule, RuleCategory

__all__ = [
    # Materials
    "MaterialDatabase",
    "Material",
    "CuttingParameters",
    # Tooling
    "ToolCatalog",
    "Tool",
    "ToolType",
    # Rules
    "MachiningRules",
    "Rule",
    "RuleCategory",
]
