"""
Author: Viquar Khan (ORCID 0009-0008-3592-4162).

WCE Estimator - AI-adjusted software effort estimation from a multi-tab workbook.

Implements the paper "No Silver Estimate: An Amdahl-Bounded Framework for
AI-Adjusted Software Effort Estimation, an Industry Ceiling Map, and a Pattern
Language" by Viquar Khan (ORCID 0009-0008-3592-4162).

Public API:
    from wce_estimator import read_workbook, estimate, build_excel_report, build_html_report
"""

from .engine import WorkItem, EstimationResult, estimate
from .reader import read_workbook
from .report import (
    build_excel_report, build_html_report, build_html_report_multi,
    build_comparison_report,
)

__all__ = [
    "WorkItem", "EstimationResult", "estimate",
    "read_workbook", "build_excel_report", "build_html_report",
    "build_html_report_multi", "build_comparison_report",
]
__version__ = "1.0.0"
