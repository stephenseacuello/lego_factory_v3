"""
FMEA Report Generator - Automated report generation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Report output formats."""
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"


class ReportType(Enum):
    """Types of FMEA reports."""
    FULL_FMEA = "full_fmea"
    EXECUTIVE_SUMMARY = "executive_summary"
    HIGH_RPN_FOCUS = "high_rpn_focus"
    CORRECTIVE_ACTIONS = "corrective_actions"
    TREND_ANALYSIS = "trend_analysis"


@dataclass
class FMEAEntry:
    """Single FMEA table entry."""
    item_id: str
    item_name: str
    function: str
    failure_mode: str
    effects: List[str]
    severity: int
    causes: List[str]
    occurrence: int
    current_controls: List[str]
    detection: int
    rpn: int
    recommended_actions: List[str]
    responsibility: str = ""
    target_date: Optional[datetime] = None
    action_taken: str = ""
    new_severity: Optional[int] = None
    new_occurrence: Optional[int] = None
    new_detection: Optional[int] = None
    new_rpn: Optional[int] = None


@dataclass
class FMEAReport:
    """Complete FMEA report."""
    report_id: str
    title: str
    report_type: ReportType
    project_name: str
    revision: str
    prepared_by: str
    date: datetime
    entries: List[FMEAEntry]
    summary: Dict[str, Any]
    content: str  # Generated content


class FMEAReportGenerator:
    """
    Automated FMEA report generation.

    Features:
    - Multiple output formats
    - Executive summaries
    - RPN analysis
    - Action tracking
    - Trend visualization data
    """

    def __init__(self):
        self._templates: Dict[str, str] = {}
        self._rpn_threshold = 100  # High-priority threshold
        self._load_templates()

    def _load_templates(self) -> None:
        """Load report templates."""
        self._templates['html_header'] = """
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; }}
        h2 {{ color: #666; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .high-rpn {{ background-color: #ffcccc !important; }}
        .medium-rpn {{ background-color: #ffffcc !important; }}
        .summary-box {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .metric {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
        .warning {{ color: #ff6600; }}
        .critical {{ color: #cc0000; font-weight: bold; }}
    </style>
</head>
<body>
"""
        self._templates['html_footer'] = """
</body>
</html>
"""

    def generate(self,
                 entries: List[FMEAEntry],
                 project_name: str,
                 report_type: ReportType = ReportType.FULL_FMEA,
                 format: ReportFormat = ReportFormat.HTML,
                 prepared_by: str = "LEGO MCP System",
                 revision: str = "1.0") -> FMEAReport:
        """
        Generate FMEA report.

        Args:
            entries: FMEA entries to include
            project_name: Project/product name
            report_type: Type of report to generate
            format: Output format
            prepared_by: Author name
            revision: Document revision

        Returns:
            Complete FMEA report
        """
        report_id = f"FMEA-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Generate summary statistics
        summary = self._generate_summary(entries)

        # Generate content based on format and type
        if format == ReportFormat.HTML:
            content = self._generate_html(
                entries, project_name, report_type, summary, prepared_by, revision
            )
        elif format == ReportFormat.MARKDOWN:
            content = self._generate_markdown(
                entries, project_name, report_type, summary, prepared_by, revision
            )
        elif format == ReportFormat.JSON:
            content = self._generate_json(
                entries, project_name, report_type, summary, prepared_by, revision
            )
        else:  # CSV
            content = self._generate_csv(entries)

        title = f"{project_name} - {report_type.value.replace('_', ' ').title()}"

        return FMEAReport(
            report_id=report_id,
            title=title,
            report_type=report_type,
            project_name=project_name,
            revision=revision,
            prepared_by=prepared_by,
            date=datetime.utcnow(),
            entries=entries,
            summary=summary,
            content=content
        )

    def _generate_summary(self, entries: List[FMEAEntry]) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not entries:
            return {'total_entries': 0}

        rpn_values = [e.rpn for e in entries]
        severities = [e.severity for e in entries]

        high_rpn_count = sum(1 for rpn in rpn_values if rpn >= self._rpn_threshold)
        critical_severity = sum(1 for s in severities if s >= 9)

        # Top failure modes by RPN
        sorted_entries = sorted(entries, key=lambda e: e.rpn, reverse=True)
        top_5_rpn = [(e.failure_mode, e.rpn) for e in sorted_entries[:5]]

        # RPN distribution
        rpn_distribution = {
            'low (1-49)': sum(1 for rpn in rpn_values if rpn < 50),
            'medium (50-99)': sum(1 for rpn in rpn_values if 50 <= rpn < 100),
            'high (100-199)': sum(1 for rpn in rpn_values if 100 <= rpn < 200),
            'critical (200+)': sum(1 for rpn in rpn_values if rpn >= 200)
        }

        # Improvement potential
        improvement_entries = [e for e in entries if e.new_rpn is not None]
        if improvement_entries:
            original_total = sum(e.rpn for e in improvement_entries)
            new_total = sum(e.new_rpn for e in improvement_entries)
            improvement_percent = ((original_total - new_total) / original_total * 100
                                  if original_total > 0 else 0)
        else:
            improvement_percent = None

        return {
            'total_entries': len(entries),
            'average_rpn': sum(rpn_values) / len(rpn_values),
            'max_rpn': max(rpn_values),
            'min_rpn': min(rpn_values),
            'high_rpn_count': high_rpn_count,
            'critical_severity_count': critical_severity,
            'top_5_rpn': top_5_rpn,
            'rpn_distribution': rpn_distribution,
            'improvement_percent': improvement_percent,
            'actions_pending': sum(1 for e in entries if e.recommended_actions and not e.action_taken)
        }

    def _generate_html(self,
                      entries: List[FMEAEntry],
                      project_name: str,
                      report_type: ReportType,
                      summary: Dict[str, Any],
                      prepared_by: str,
                      revision: str) -> str:
        """Generate HTML report."""
        html = [self._templates['html_header'].format(title=f"{project_name} FMEA")]

        # Header
        html.append(f"<h1>{project_name} - FMEA Report</h1>")
        html.append(f"<p><strong>Prepared by:</strong> {prepared_by} | ")
        html.append(f"<strong>Date:</strong> {datetime.utcnow().strftime('%Y-%m-%d')} | ")
        html.append(f"<strong>Revision:</strong> {revision}</p>")

        # Executive Summary
        html.append("<h2>Executive Summary</h2>")
        html.append("<div class='summary-box'>")
        html.append(f"<p><span class='metric'>{summary['total_entries']}</span> failure modes analyzed</p>")
        html.append(f"<p>Average RPN: <span class='metric'>{summary['average_rpn']:.1f}</span></p>")

        if summary['high_rpn_count'] > 0:
            html.append(f"<p class='critical'>High Priority Items (RPN >= {self._rpn_threshold}): "
                       f"{summary['high_rpn_count']}</p>")

        if summary['critical_severity_count'] > 0:
            html.append(f"<p class='critical'>Critical Severity Items (S >= 9): "
                       f"{summary['critical_severity_count']}</p>")

        html.append("</div>")

        # RPN Distribution
        html.append("<h2>RPN Distribution</h2>")
        html.append("<table><tr><th>Category</th><th>Count</th></tr>")
        for category, count in summary['rpn_distribution'].items():
            html.append(f"<tr><td>{category}</td><td>{count}</td></tr>")
        html.append("</table>")

        # Top 5 High-Risk Items
        if summary['top_5_rpn']:
            html.append("<h2>Top 5 High-Risk Items</h2>")
            html.append("<table><tr><th>Failure Mode</th><th>RPN</th></tr>")
            for fm, rpn in summary['top_5_rpn']:
                row_class = 'high-rpn' if rpn >= self._rpn_threshold else ''
                html.append(f"<tr class='{row_class}'><td>{fm}</td><td>{rpn}</td></tr>")
            html.append("</table>")

        # Full FMEA Table (if full report)
        if report_type in [ReportType.FULL_FMEA, ReportType.HIGH_RPN_FOCUS]:
            html.append("<h2>FMEA Analysis</h2>")
            html.append(self._generate_fmea_table_html(entries, report_type))

        # Corrective Actions (if requested)
        if report_type in [ReportType.CORRECTIVE_ACTIONS, ReportType.FULL_FMEA]:
            html.append("<h2>Recommended Corrective Actions</h2>")
            html.append(self._generate_actions_table_html(entries))

        html.append(self._templates['html_footer'])
        return '\n'.join(html)

    def _generate_fmea_table_html(self,
                                  entries: List[FMEAEntry],
                                  report_type: ReportType) -> str:
        """Generate FMEA table in HTML."""
        # Filter for high RPN if focus report
        if report_type == ReportType.HIGH_RPN_FOCUS:
            entries = [e for e in entries if e.rpn >= self._rpn_threshold]

        html = ["<table>"]
        html.append("<tr>")
        html.append("<th>Item</th><th>Function</th><th>Failure Mode</th>")
        html.append("<th>Effects</th><th>S</th><th>Causes</th><th>O</th>")
        html.append("<th>Current Controls</th><th>D</th><th>RPN</th>")
        html.append("</tr>")

        for entry in sorted(entries, key=lambda e: e.rpn, reverse=True):
            row_class = 'high-rpn' if entry.rpn >= self._rpn_threshold else (
                'medium-rpn' if entry.rpn >= 50 else ''
            )
            html.append(f"<tr class='{row_class}'>")
            html.append(f"<td>{entry.item_name}</td>")
            html.append(f"<td>{entry.function}</td>")
            html.append(f"<td>{entry.failure_mode}</td>")
            html.append(f"<td>{'; '.join(entry.effects[:2])}</td>")
            html.append(f"<td>{entry.severity}</td>")
            html.append(f"<td>{'; '.join(entry.causes[:2])}</td>")
            html.append(f"<td>{entry.occurrence}</td>")
            html.append(f"<td>{'; '.join(entry.current_controls[:2])}</td>")
            html.append(f"<td>{entry.detection}</td>")
            html.append(f"<td><strong>{entry.rpn}</strong></td>")
            html.append("</tr>")

        html.append("</table>")
        return '\n'.join(html)

    def _generate_actions_table_html(self, entries: List[FMEAEntry]) -> str:
        """Generate corrective actions table."""
        # Filter entries with actions
        action_entries = [e for e in entries if e.recommended_actions]

        if not action_entries:
            return "<p>No corrective actions defined.</p>"

        html = ["<table>"]
        html.append("<tr><th>Failure Mode</th><th>RPN</th><th>Recommended Actions</th>")
        html.append("<th>Responsibility</th><th>Target Date</th><th>Status</th></tr>")

        for entry in sorted(action_entries, key=lambda e: e.rpn, reverse=True):
            status = "Complete" if entry.action_taken else "Pending"
            status_class = "" if entry.action_taken else "warning"
            target = entry.target_date.strftime('%Y-%m-%d') if entry.target_date else "TBD"

            html.append("<tr>")
            html.append(f"<td>{entry.failure_mode}</td>")
            html.append(f"<td>{entry.rpn}</td>")
            html.append(f"<td>{'<br>'.join(entry.recommended_actions)}</td>")
            html.append(f"<td>{entry.responsibility or 'Unassigned'}</td>")
            html.append(f"<td>{target}</td>")
            html.append(f"<td class='{status_class}'>{status}</td>")
            html.append("</tr>")

        html.append("</table>")
        return '\n'.join(html)

    def _generate_markdown(self,
                          entries: List[FMEAEntry],
                          project_name: str,
                          report_type: ReportType,
                          summary: Dict[str, Any],
                          prepared_by: str,
                          revision: str) -> str:
        """Generate Markdown report."""
        md = [f"# {project_name} - FMEA Report\n"]
        md.append(f"**Prepared by:** {prepared_by}  ")
        md.append(f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d')}  ")
        md.append(f"**Revision:** {revision}\n")

        md.append("## Executive Summary\n")
        md.append(f"- **Total Failure Modes:** {summary['total_entries']}")
        md.append(f"- **Average RPN:** {summary['average_rpn']:.1f}")
        md.append(f"- **High Priority Items:** {summary['high_rpn_count']}")
        md.append(f"- **Critical Severity Items:** {summary['critical_severity_count']}\n")

        md.append("## Top 5 High-Risk Items\n")
        md.append("| Failure Mode | RPN |")
        md.append("|--------------|-----|")
        for fm, rpn in summary['top_5_rpn']:
            md.append(f"| {fm} | {rpn} |")
        md.append("")

        if report_type == ReportType.FULL_FMEA:
            md.append("## FMEA Analysis\n")
            md.append("| Item | Failure Mode | S | O | D | RPN |")
            md.append("|------|--------------|---|---|---|-----|")
            for entry in sorted(entries, key=lambda e: e.rpn, reverse=True)[:20]:
                md.append(f"| {entry.item_name} | {entry.failure_mode} | "
                         f"{entry.severity} | {entry.occurrence} | {entry.detection} | "
                         f"**{entry.rpn}** |")

        return '\n'.join(md)

    def _generate_json(self,
                      entries: List[FMEAEntry],
                      project_name: str,
                      report_type: ReportType,
                      summary: Dict[str, Any],
                      prepared_by: str,
                      revision: str) -> str:
        """Generate JSON report."""
        report_data = {
            'project_name': project_name,
            'report_type': report_type.value,
            'prepared_by': prepared_by,
            'revision': revision,
            'date': datetime.utcnow().isoformat(),
            'summary': summary,
            'entries': [
                {
                    'item_id': e.item_id,
                    'item_name': e.item_name,
                    'function': e.function,
                    'failure_mode': e.failure_mode,
                    'effects': e.effects,
                    'severity': e.severity,
                    'causes': e.causes,
                    'occurrence': e.occurrence,
                    'current_controls': e.current_controls,
                    'detection': e.detection,
                    'rpn': e.rpn,
                    'recommended_actions': e.recommended_actions,
                    'responsibility': e.responsibility,
                    'action_taken': e.action_taken,
                    'new_rpn': e.new_rpn
                }
                for e in entries
            ]
        }
        return json.dumps(report_data, indent=2, default=str)

    def _generate_csv(self, entries: List[FMEAEntry]) -> str:
        """Generate CSV report."""
        headers = [
            "Item ID", "Item Name", "Function", "Failure Mode",
            "Effects", "Severity", "Causes", "Occurrence",
            "Current Controls", "Detection", "RPN",
            "Recommended Actions", "Responsibility", "Action Taken", "New RPN"
        ]

        rows = [','.join(headers)]

        for e in entries:
            row = [
                e.item_id,
                f'"{e.item_name}"',
                f'"{e.function}"',
                f'"{e.failure_mode}"',
                f'"{"; ".join(e.effects)}"',
                str(e.severity),
                f'"{"; ".join(e.causes)}"',
                str(e.occurrence),
                f'"{"; ".join(e.current_controls)}"',
                str(e.detection),
                str(e.rpn),
                f'"{"; ".join(e.recommended_actions)}"',
                e.responsibility,
                f'"{e.action_taken}"',
                str(e.new_rpn) if e.new_rpn else ""
            ]
            rows.append(','.join(row))

        return '\n'.join(rows)

    def generate_trend_data(self,
                           historical_reports: List[FMEAReport]) -> Dict[str, Any]:
        """Generate trend analysis data for visualization."""
        if not historical_reports:
            return {}

        trend_data = {
            'dates': [],
            'average_rpn': [],
            'high_rpn_count': [],
            'total_entries': [],
            'improvement_tracking': []
        }

        for report in sorted(historical_reports, key=lambda r: r.date):
            trend_data['dates'].append(report.date.isoformat())
            trend_data['average_rpn'].append(report.summary.get('average_rpn', 0))
            trend_data['high_rpn_count'].append(report.summary.get('high_rpn_count', 0))
            trend_data['total_entries'].append(report.summary.get('total_entries', 0))

        return trend_data

    def set_rpn_threshold(self, threshold: int) -> None:
        """Set high-priority RPN threshold."""
        self._rpn_threshold = threshold
        logger.info(f"RPN threshold set to {threshold}")
