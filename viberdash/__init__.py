"""ViberDash - Real-time code quality monitoring dashboard."""

__version__ = "0.1.0"

from .analyzer import CodeAnalyzer
from .storage import MetricsStorage
from .tui import DashboardUI
from .vibescan import ViberDashRunner, main

__all__ = [
    "CodeAnalyzer",
    "MetricsStorage",
    "DashboardUI",
    "ViberDashRunner",
    "main",
]
