"""
Static Analysis Integration

Integrates multiple static analysis tools for comprehensive
code quality and safety verification.

Reference: DO-178C, IEC 61508 SIL 2+, MISRA C++:2023
"""

import logging
import subprocess
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Issue severity levels (aligned with MISRA)."""
    ERROR = "error"           # Must fix - safety violation
    WARNING = "warning"       # Should fix - potential issue
    STYLE = "style"          # Code style violation
    PERFORMANCE = "performance"  # Performance concern
    PORTABILITY = "portability"  # Portability issue
    INFORMATION = "information"  # Informational


class Category(Enum):
    """Issue category classification."""
    MEMORY = "memory"         # Memory safety
    CONCURRENCY = "concurrency"  # Thread safety
    RESOURCE = "resource"     # Resource management
    UNDEFINED = "undefined"   # Undefined behavior
    MISRA = "misra"          # MISRA rule violation
    SECURITY = "security"     # Security vulnerability
    LOGIC = "logic"          # Logic error
    STYLE = "style"          # Style/convention


@dataclass
class CodeLocation:
    """Location in source code."""
    file: str
    line: int
    column: int = 0
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


@dataclass
class AnalysisResult:
    """Result from static analysis."""
    tool: str
    severity: Severity
    category: Category
    message: str
    location: CodeLocation
    rule_id: Optional[str] = None
    cwe_id: Optional[str] = None      # Common Weakness Enumeration
    misra_rule: Optional[str] = None  # MISRA rule reference
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool": self.tool,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "location": str(self.location),
            "file": self.location.file,
            "line": self.location.line,
            "rule_id": self.rule_id,
            "cwe_id": self.cwe_id,
            "misra_rule": self.misra_rule,
            "suggestion": self.suggestion
        }


@dataclass
class AnalysisReport:
    """Complete analysis report."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    results: List[AnalysisResult] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    files_analyzed: int = 0
    analysis_time_seconds: float = 0.0
    tools_used: List[str] = field(default_factory=list)
    passed: bool = True

    def add_result(self, result: AnalysisResult) -> None:
        """Add an analysis result."""
        self.results.append(result)
        self.summary[result.severity.value] = self.summary.get(result.severity.value, 0) + 1
        if result.severity in (Severity.ERROR,):
            self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "passed": self.passed,
            "files_analyzed": self.files_analyzed,
            "analysis_time_seconds": self.analysis_time_seconds,
            "tools_used": self.tools_used,
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results]
        }


class ClangAnalyzer:
    """
    Clang Static Analyzer integration.

    Uses Clang's scan-build for deep static analysis.
    """

    def __init__(self, clang_path: str = "clang"):
        self.clang_path = clang_path
        self.checkers = [
            "core",
            "deadcode",
            "security",
            "unix",
            "cplusplus",
            "optin.performance",
            "optin.portability"
        ]

    def analyze(
        self,
        source_files: List[str],
        include_paths: Optional[List[str]] = None,
        defines: Optional[Dict[str, str]] = None
    ) -> List[AnalysisResult]:
        """Run Clang static analysis."""
        results = []
        include_paths = include_paths or []
        defines = defines or {}

        for source_file in source_files:
            if not os.path.exists(source_file):
                continue

            cmd = [
                self.clang_path,
                "--analyze",
                "-Xanalyzer", "-analyzer-output=text",
                *[f"-I{p}" for p in include_paths],
                *[f"-D{k}={v}" for k, v in defines.items()],
                source_file
            ]

            for checker in self.checkers:
                cmd.extend(["-Xanalyzer", f"-analyzer-checker={checker}"])

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                # Parse Clang output
                results.extend(self._parse_output(proc.stderr, source_file))

            except subprocess.TimeoutExpired:
                logger.warning(f"Clang analysis timed out for {source_file}")
            except Exception as e:
                logger.error(f"Clang analysis failed: {e}")

        return results

    def _parse_output(self, output: str, default_file: str) -> List[AnalysisResult]:
        """Parse Clang analyzer output."""
        results = []

        # Pattern: file:line:col: severity: message
        pattern = r"([^:]+):(\d+):(\d+): (warning|error|note): (.+)"

        for match in re.finditer(pattern, output):
            file_path, line, col, severity_str, message = match.groups()

            severity = Severity.ERROR if severity_str == "error" else Severity.WARNING

            # Categorize based on message content
            category = Category.LOGIC
            if "memory" in message.lower() or "leak" in message.lower():
                category = Category.MEMORY
            elif "null" in message.lower() or "nullptr" in message.lower():
                category = Category.UNDEFINED
            elif "thread" in message.lower() or "race" in message.lower():
                category = Category.CONCURRENCY

            results.append(AnalysisResult(
                tool="clang-analyzer",
                severity=severity,
                category=category,
                message=message,
                location=CodeLocation(
                    file=file_path,
                    line=int(line),
                    column=int(col)
                )
            ))

        return results


class CppcheckAnalyzer:
    """
    Cppcheck static analyzer integration.

    Reference: Cppcheck Manual
    """

    def __init__(self, cppcheck_path: str = "cppcheck"):
        self.cppcheck_path = cppcheck_path

    def analyze(
        self,
        source_files: List[str],
        include_paths: Optional[List[str]] = None,
        std: str = "c++20",
        misra: bool = True
    ) -> List[AnalysisResult]:
        """Run Cppcheck analysis."""
        results = []
        include_paths = include_paths or []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            output_file = f.name

        try:
            cmd = [
                self.cppcheck_path,
                "--enable=all",
                f"--std={std}",
                "--xml",
                f"--output-file={output_file}",
                "--suppress=missingIncludeSystem",
                *[f"-I{p}" for p in include_paths],
                *source_files
            ]

            if misra:
                cmd.append("--addon=misra")

            subprocess.run(cmd, capture_output=True, timeout=600)

            # Parse XML output
            results = self._parse_xml(output_file)

        except subprocess.TimeoutExpired:
            logger.warning("Cppcheck analysis timed out")
        except Exception as e:
            logger.error(f"Cppcheck analysis failed: {e}")
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

        return results

    def _parse_xml(self, xml_file: str) -> List[AnalysisResult]:
        """Parse Cppcheck XML output."""
        results = []

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for error in root.findall(".//error"):
                error_id = error.get("id", "")
                severity_str = error.get("severity", "style")
                message = error.get("msg", "")
                cwe = error.get("cwe")

                # Map severity
                severity_map = {
                    "error": Severity.ERROR,
                    "warning": Severity.WARNING,
                    "style": Severity.STYLE,
                    "performance": Severity.PERFORMANCE,
                    "portability": Severity.PORTABILITY,
                    "information": Severity.INFORMATION
                }
                severity = severity_map.get(severity_str, Severity.WARNING)

                # Get location
                location_elem = error.find("location")
                if location_elem is not None:
                    location = CodeLocation(
                        file=location_elem.get("file", ""),
                        line=int(location_elem.get("line", 0)),
                        column=int(location_elem.get("column", 0))
                    )
                else:
                    location = CodeLocation(file="unknown", line=0)

                # Categorize
                category = Category.LOGIC
                if "misra" in error_id.lower():
                    category = Category.MISRA
                elif "memory" in error_id.lower() or "leak" in message.lower():
                    category = Category.MEMORY
                elif "nullPointer" in error_id:
                    category = Category.UNDEFINED
                elif "thread" in error_id.lower():
                    category = Category.CONCURRENCY

                # Extract MISRA rule if present
                misra_rule = None
                misra_match = re.search(r"misra-c\+\+-(\d+)-(\d+)-(\d+)", error_id)
                if misra_match:
                    misra_rule = f"Rule {misra_match.group(1)}.{misra_match.group(2)}.{misra_match.group(3)}"

                results.append(AnalysisResult(
                    tool="cppcheck",
                    severity=severity,
                    category=category,
                    message=message,
                    location=location,
                    rule_id=error_id,
                    cwe_id=f"CWE-{cwe}" if cwe else None,
                    misra_rule=misra_rule
                ))

        except ET.ParseError as e:
            logger.error(f"Failed to parse Cppcheck XML: {e}")

        return results


class MISRAChecker:
    """
    MISRA C++ Compliance Checker.

    Verifies compliance with MISRA C++:2023 guidelines.
    Reference: MISRA C++:2023
    """

    # Critical MISRA rules to check
    CRITICAL_RULES = {
        "0-1-1": "A project shall not contain infeasible paths",
        "0-1-2": "A project shall not contain dead code",
        "5-0-3": "A cvalue expression shall not be implicitly converted",
        "5-0-15": "Array indexing shall be the only form of pointer arithmetic",
        "6-4-1": "An if-else-if chain shall be terminated with an else clause",
        "6-6-1": "Any label referenced by a goto shall be declared in the same block",
        "7-1-1": "A variable shall have the same type across all declarations",
        "8-4-4": "A function identifier shall only be used with either a call or address operator",
        "9-3-1": "const shall be used for function parameters passed by reference",
        "15-0-2": "An exception object shall not have pointer type",
        "18-0-1": "The C library shall not be used",
        "18-0-3": "The library functions abort, exit, getenv and system shall not be used",
    }

    def __init__(self):
        self.violations: List[AnalysisResult] = []

    def check_file(self, source_file: str) -> List[AnalysisResult]:
        """Check a file for MISRA compliance."""
        results = []

        try:
            with open(source_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')

            # Check various MISRA rules
            results.extend(self._check_goto_usage(lines, source_file))
            results.extend(self._check_c_library_usage(lines, source_file))
            results.extend(self._check_dynamic_memory(lines, source_file))
            results.extend(self._check_exception_handling(lines, source_file))
            results.extend(self._check_pointer_arithmetic(lines, source_file))

        except Exception as e:
            logger.error(f"MISRA check failed for {source_file}: {e}")

        return results

    def _check_goto_usage(self, lines: List[str], file: str) -> List[AnalysisResult]:
        """MISRA Rule 6-6-1: goto restrictions."""
        results = []
        for i, line in enumerate(lines, 1):
            if re.search(r'\bgoto\b', line) and not line.strip().startswith('//'):
                results.append(AnalysisResult(
                    tool="misra-checker",
                    severity=Severity.ERROR,
                    category=Category.MISRA,
                    message="Use of 'goto' is restricted",
                    location=CodeLocation(file=file, line=i),
                    misra_rule="Rule 6-6-1",
                    suggestion="Refactor to use structured control flow"
                ))
        return results

    def _check_c_library_usage(self, lines: List[str], file: str) -> List[AnalysisResult]:
        """MISRA Rule 18-0-1: C library restrictions."""
        results = []
        c_headers = ['<cstdlib>', '<cstdio>', '<cstring>', '<cmath>']

        for i, line in enumerate(lines, 1):
            for header in c_headers:
                if header in line and '#include' in line:
                    results.append(AnalysisResult(
                        tool="misra-checker",
                        severity=Severity.WARNING,
                        category=Category.MISRA,
                        message=f"C library header {header} usage is restricted",
                        location=CodeLocation(file=file, line=i),
                        misra_rule="Rule 18-0-1",
                        suggestion="Use C++ equivalents instead"
                    ))

            # Check for banned functions
            banned_funcs = ['abort', 'exit', 'getenv', 'system']
            for func in banned_funcs:
                if re.search(rf'\b{func}\s*\(', line):
                    results.append(AnalysisResult(
                        tool="misra-checker",
                        severity=Severity.ERROR,
                        category=Category.MISRA,
                        message=f"Use of '{func}' is not permitted",
                        location=CodeLocation(file=file, line=i),
                        misra_rule="Rule 18-0-3"
                    ))

        return results

    def _check_dynamic_memory(self, lines: List[str], file: str) -> List[AnalysisResult]:
        """Check dynamic memory usage patterns."""
        results = []
        for i, line in enumerate(lines, 1):
            # Raw new/delete usage
            if re.search(r'\bnew\b(?!\s*\()', line) and 'unique_ptr' not in line and 'shared_ptr' not in line:
                if not line.strip().startswith('//'):
                    results.append(AnalysisResult(
                        tool="misra-checker",
                        severity=Severity.WARNING,
                        category=Category.MEMORY,
                        message="Prefer smart pointers over raw new",
                        location=CodeLocation(file=file, line=i),
                        suggestion="Use std::make_unique or std::make_shared"
                    ))

            if re.search(r'\bdelete\b', line) and not line.strip().startswith('//'):
                results.append(AnalysisResult(
                    tool="misra-checker",
                    severity=Severity.WARNING,
                    category=Category.MEMORY,
                    message="Prefer smart pointers over raw delete",
                    location=CodeLocation(file=file, line=i),
                    suggestion="Use smart pointers for automatic memory management"
                ))

        return results

    def _check_exception_handling(self, lines: List[str], file: str) -> List[AnalysisResult]:
        """MISRA Rule 15-0-2: Exception type restrictions."""
        results = []
        for i, line in enumerate(lines, 1):
            # Check for throwing pointers
            if re.search(r'throw\s+new\b', line):
                results.append(AnalysisResult(
                    tool="misra-checker",
                    severity=Severity.ERROR,
                    category=Category.MISRA,
                    message="Exception object shall not have pointer type",
                    location=CodeLocation(file=file, line=i),
                    misra_rule="Rule 15-0-2",
                    suggestion="Throw by value, catch by reference"
                ))
        return results

    def _check_pointer_arithmetic(self, lines: List[str], file: str) -> List[AnalysisResult]:
        """MISRA Rule 5-0-15: Pointer arithmetic restrictions."""
        results = []
        for i, line in enumerate(lines, 1):
            # Check for pointer arithmetic (simplified)
            if re.search(r'\*\s*\w+\s*[+\-]\s*\d+', line) and not line.strip().startswith('//'):
                results.append(AnalysisResult(
                    tool="misra-checker",
                    severity=Severity.WARNING,
                    category=Category.MISRA,
                    message="Array indexing should be the only form of pointer arithmetic",
                    location=CodeLocation(file=file, line=i),
                    misra_rule="Rule 5-0-15",
                    suggestion="Use array indexing syntax instead"
                ))
        return results


class StaticAnalyzer:
    """
    Unified Static Analysis Pipeline.

    Coordinates multiple static analysis tools and
    aggregates results.

    Usage:
        >>> analyzer = StaticAnalyzer()
        >>> report = analyzer.analyze_directory("src/")
        >>> print(report.passed)
    """

    def __init__(
        self,
        clang_path: str = "clang",
        cppcheck_path: str = "cppcheck",
        enable_misra: bool = True
    ):
        """
        Initialize static analyzer.

        Args:
            clang_path: Path to Clang compiler
            cppcheck_path: Path to Cppcheck
            enable_misra: Enable MISRA checking
        """
        self.clang = ClangAnalyzer(clang_path)
        self.cppcheck = CppcheckAnalyzer(cppcheck_path)
        self.misra = MISRAChecker() if enable_misra else None
        self.enable_misra = enable_misra

        logger.info("StaticAnalyzer initialized")

    def analyze_file(
        self,
        source_file: str,
        include_paths: Optional[List[str]] = None
    ) -> AnalysisReport:
        """Analyze a single file."""
        return self.analyze_files([source_file], include_paths)

    def analyze_files(
        self,
        source_files: List[str],
        include_paths: Optional[List[str]] = None
    ) -> AnalysisReport:
        """Analyze multiple files."""
        import time
        start_time = time.time()

        report = AnalysisReport()
        report.files_analyzed = len(source_files)

        # Filter to existing C++ files
        cpp_files = [f for f in source_files
                     if os.path.exists(f) and f.endswith(('.cpp', '.hpp', '.h', '.cc'))]

        if not cpp_files:
            return report

        # Run Clang analyzer
        try:
            clang_results = self.clang.analyze(cpp_files, include_paths)
            for result in clang_results:
                report.add_result(result)
            report.tools_used.append("clang-analyzer")
        except Exception as e:
            logger.warning(f"Clang analysis skipped: {e}")

        # Run Cppcheck
        try:
            cppcheck_results = self.cppcheck.analyze(
                cpp_files, include_paths, misra=self.enable_misra
            )
            for result in cppcheck_results:
                report.add_result(result)
            report.tools_used.append("cppcheck")
        except Exception as e:
            logger.warning(f"Cppcheck analysis skipped: {e}")

        # Run MISRA checker
        if self.misra:
            for source_file in cpp_files:
                try:
                    misra_results = self.misra.check_file(source_file)
                    for result in misra_results:
                        report.add_result(result)
                except Exception as e:
                    logger.warning(f"MISRA check failed for {source_file}: {e}")
            report.tools_used.append("misra-checker")

        report.analysis_time_seconds = time.time() - start_time
        return report

    def analyze_directory(
        self,
        directory: str,
        include_paths: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> AnalysisReport:
        """Analyze all C++ files in a directory."""
        exclude_patterns = exclude_patterns or ["test", "build", "third_party"]

        source_files = []
        for root, dirs, files in os.walk(directory):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs
                       if not any(p in d for p in exclude_patterns)]

            for file in files:
                if file.endswith(('.cpp', '.hpp', '.h', '.cc')):
                    source_files.append(os.path.join(root, file))

        logger.info(f"Analyzing {len(source_files)} files in {directory}")
        return self.analyze_files(source_files, include_paths)

    def generate_sarif(self, report: AnalysisReport) -> Dict[str, Any]:
        """
        Generate SARIF (Static Analysis Results Interchange Format) output.

        Reference: SARIF 2.1.0 Specification
        """
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "LEGO MCP Static Analyzer",
                            "version": "2.0.0",
                            "informationUri": "https://lego-mcp.example.com"
                        }
                    },
                    "results": [
                        {
                            "ruleId": r.rule_id or "unknown",
                            "level": self._severity_to_sarif_level(r.severity),
                            "message": {"text": r.message},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": r.location.file},
                                        "region": {
                                            "startLine": r.location.line,
                                            "startColumn": r.location.column
                                        }
                                    }
                                }
                            ]
                        }
                        for r in report.results
                    ]
                }
            ]
        }
        return sarif

    def _severity_to_sarif_level(self, severity: Severity) -> str:
        """Map severity to SARIF level."""
        mapping = {
            Severity.ERROR: "error",
            Severity.WARNING: "warning",
            Severity.STYLE: "note",
            Severity.PERFORMANCE: "note",
            Severity.PORTABILITY: "warning",
            Severity.INFORMATION: "note"
        }
        return mapping.get(severity, "note")
