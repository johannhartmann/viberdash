"""Terminal UI for ViberDash using Rich."""

from datetime import datetime
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class DashboardUI:
    """Handles the terminal UI display using Rich."""

    def __init__(self, thresholds: dict[str, dict[str, float]] | None = None):
        """Initialize UI with optional threshold configuration."""
        self.console = Console()
        # Merge provided thresholds with defaults
        default_thresholds = self._default_thresholds()
        if thresholds:
            # Update defaults with provided thresholds
            default_thresholds.update(thresholds)
        self.thresholds = default_thresholds

    def _default_thresholds(self) -> dict[str, dict[str, float]]:
        """Return default threshold values."""
        return {
            "cyclomatic_complexity": {"good": 5.0, "bad": 10.0},
            "maintainability_index": {"good": 85.0, "bad": 65.0},
            "test_coverage": {"good": 80.0, "bad": 60.0},
            "code_duplication": {"good": 5.0, "bad": 15.0},
            "dead_code": {"good": 5.0, "bad": 15.0},
            "style_violations": {"good": 10.0, "bad": 25.0},
            "doc_coverage": {"good": 80.0, "bad": 60.0},
        }

    def display_dashboard(
        self, latest_metrics: dict[str, Any], history: list[dict[str, Any]]
    ) -> None:
        """Display the main dashboard with current metrics and trends.

        Args:
            latest_metrics: Most recent metrics data
            history: List of historical metrics (newest first)

        """
        # Clear terminal
        self.console.clear()

        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(self._create_header(latest_metrics), size=4),
            Layout(self._create_metrics_table(latest_metrics, history)),
            Layout(self._create_footer(), size=3),
        )

        # Print layout using height-1 to prevent using the last line
        self.console.print(layout, height=self.console.height - 1)

    def _create_header(self, metrics: dict[str, Any]) -> Panel:
        """Create dashboard header."""
        timestamp = metrics.get("timestamp", datetime.now().isoformat())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except Exception:
                timestamp = datetime.now()

        header_text = Text()
        header_text.append("ViberDash", style="bold cyan")
        header_text.append(" - Live Code Quality Metrics\n", style="white")
        header_text.append(
            f"Last updated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            style="dim white",
        )

        return Panel(Align.center(header_text), box=box.DOUBLE, style="cyan")

    def _create_metrics_table(
        self, latest: dict[str, Any], history: list[dict[str, Any]]
    ) -> Table:
        """Create the main metrics table."""
        table = Table(
            title="Code Quality Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            title_style="bold white",
        )

        # Add columns
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Current Value", justify="right", width=15)
        table.add_column("Change (�)", justify="right", width=12)
        table.add_column("Trend", width=30)
        table.add_column("Status", justify="center", width=10)

        # Get previous metrics for delta calculation
        previous = history[1] if len(history) > 1 else None

        # Add rows for each metric
        self._add_metric_row(
            table,
            "Cyclomatic Complexity",
            latest.get("avg_complexity", 0),
            previous.get("avg_complexity", 0) if previous else None,
            [h.get("avg_complexity", 0) for h in reversed(history)],
            "cyclomatic_complexity",
            lower_is_better=True,
        )

        self._add_metric_row(
            table,
            "Maintainability Index",
            latest.get("maintainability_index", 0),
            previous.get("maintainability_index", 0) if previous else None,
            [h.get("maintainability_index", 0) for h in reversed(history)],
            "maintainability_index",
            lower_is_better=False,
        )

        self._add_metric_row(
            table,
            "Test Coverage",
            latest.get("test_coverage", 0),
            previous.get("test_coverage", 0) if previous else None,
            [h.get("test_coverage", 0) for h in reversed(history)],
            "test_coverage",
            lower_is_better=False,
            suffix="%",
        )

        self._add_metric_row(
            table,
            "Code Duplication",
            latest.get("code_duplication", 0),
            previous.get("code_duplication", 0) if previous else None,
            [h.get("code_duplication", 0) for h in reversed(history)],
            "code_duplication",
            lower_is_better=True,
            suffix="%",
        )

        self._add_metric_row(
            table,
            "Dead Code",
            latest.get("dead_code", 0),
            previous.get("dead_code", 0) if previous else None,
            [h.get("dead_code", 0) for h in reversed(history)],
            "dead_code",
            lower_is_better=True,
            suffix="%",
        )

        self._add_metric_row(
            table,
            "Style Violations",
            latest.get("style_violations", 0),
            previous.get("style_violations", 0) if previous else None,
            [h.get("style_violations", 0) for h in reversed(history)],
            "style_violations",
            lower_is_better=True,
            suffix="%",
        )

        self._add_metric_row(
            table,
            "Documentation Coverage",
            latest.get("doc_coverage", 100),
            previous.get("doc_coverage", 100) if previous else None,
            [h.get("doc_coverage", 100) for h in reversed(history)],
            "doc_coverage",
            lower_is_better=False,
            suffix="%",
        )

        # Add separator
        table.add_row("", "", "", "", "")

        # Add summary stats
        table.add_row(
            "Total Functions",
            str(latest.get("total_functions", 0)),
            self._format_int_delta(
                latest.get("total_functions", 0),
                previous.get("total_functions", 0) if previous else None,
            ),
            "",
            "",
        )

        table.add_row(
            "Total Classes",
            str(latest.get("total_classes", 0)),
            self._format_int_delta(
                latest.get("total_classes", 0),
                previous.get("total_classes", 0) if previous else None,
            ),
            "",
            "",
        )

        table.add_row(
            "Total Lines",
            str(latest.get("total_lines", 0)),
            self._format_int_delta(
                latest.get("total_lines", 0),
                previous.get("total_lines", 0) if previous else None,
            ),
            "",
            "",
        )

        table.add_row(
            "Style Issues",
            str(latest.get("style_issues", 0)),
            self._format_int_delta(
                latest.get("style_issues", 0),
                previous.get("style_issues", 0) if previous else None,
            ),
            "",
            "",
        )

        return table

    def _add_metric_row(
        self,
        table: Table,
        name: str,
        current: float,
        previous: float | None,
        trend_data: list[float],
        threshold_key: str,
        lower_is_better: bool = True,
        suffix: str = "",
    ) -> None:
        """Add a metric row to the table with formatting."""
        # Format current value
        current_str = f"{current:.1f}{suffix}"

        # Calculate and format delta
        delta_str = self._format_delta(current, previous, lower_is_better)

        # Convert trend data to quality scores
        quality_scores = self._convert_to_quality_scores(
            trend_data, threshold_key, lower_is_better
        )

        # Create sparkline trend based on quality
        trend = self._create_sparkline(quality_scores)

        # Determine status and color
        status, color = self._get_status(current, threshold_key, lower_is_better)

        # Add row with appropriate styling
        table.add_row(
            name,
            f"[{color}]{current_str}[/{color}]",
            delta_str,
            f"[{color}]{trend}[/{color}]",
            f"[{color}]{status}[/{color}]",
        )

    def _format_delta(
        self, current: float, previous: float | None, lower_is_better: bool
    ) -> str:
        """Format the change between current and previous values."""
        if previous is None or previous == 0:
            return "-"

        delta = current - previous
        if abs(delta) < 0.01:
            return "→ 0.0"

        # Determine color based on whether improvement or not
        is_improvement = (delta < 0 and lower_is_better) or (
            delta > 0 and not lower_is_better
        )
        color = "green" if is_improvement else "red"
        arrow = "↓" if delta < 0 else "↑"

        return f"[{color}]{arrow} {abs(delta):.1f}[/{color}]"

    def _format_int_delta(self, current: int, previous: int | None) -> str:
        """Format integer delta."""
        if previous is None:
            return "-"

        delta = current - previous
        if delta == 0:
            return "→ 0"

        color = "yellow"  # Neutral for count changes
        arrow = "↓" if delta < 0 else "↑"

        return f"[{color}]{arrow} {abs(delta)}[/{color}]"

    def _get_status(
        self, value: float, threshold_key: str, lower_is_better: bool
    ) -> tuple[str, str]:
        """Determine status and color based on thresholds."""
        thresholds = self.thresholds.get(threshold_key, {})
        good = thresholds.get("good", 0)
        bad = thresholds.get("bad", 0)

        if lower_is_better:
            if value <= good:
                return "✓ Good", "green"
            elif value >= bad:
                return "✗ Bad", "red"
            else:
                return "~ OK", "yellow"
        else:
            if value >= good:
                return "✓ Good", "green"
            elif value <= bad:
                return "✗ Bad", "red"
            else:
                return "~ OK", "yellow"

    def _convert_to_quality_scores(
        self, values: list[float], threshold_key: str, lower_is_better: bool
    ) -> list[float]:
        """Convert raw values to quality scores (0=bad, 1=good)."""
        if not values:
            return []

        thresholds = self.thresholds.get(threshold_key, {})
        good_threshold = thresholds.get("good", 0)
        bad_threshold = thresholds.get("bad", 0)

        quality_scores = []
        for value in values:
            if lower_is_better:
                # For metrics where lower is better (e.g., complexity)
                if value <= good_threshold:
                    score = 1.0  # Good
                elif value >= bad_threshold:
                    score = 0.0  # Bad
                else:
                    # Linear interpolation between good and bad
                    score = 1.0 - (value - good_threshold) / (
                        bad_threshold - good_threshold
                    )
            else:
                # For metrics where higher is better (e.g., coverage)
                if value >= good_threshold:
                    score = 1.0  # Good
                elif value <= bad_threshold:
                    score = 0.0  # Bad
                else:
                    # Linear interpolation between bad and good
                    score = (value - bad_threshold) / (good_threshold - bad_threshold)

            quality_scores.append(score)

        return quality_scores

    def _create_sparkline(self, data: list[float]) -> str:
        """Create a simple sparkline visualization."""
        if not data or len(data) < 2:
            return ""

        # Normalize data to 0-7 range for spark characters
        spark_chars = "▁▂▃▄▅▆▇█"

        # For quality scores, we want to invert the display
        # so that good (1.0) shows as low bars and bad (0.0) shows as high bars
        sparkline = ""
        for value in data:
            # Invert: good quality (1.0) -> low bar, bad quality (0.0) -> high bar
            inverted = 1.0 - value
            index = int(inverted * (len(spark_chars) - 1))
            index = max(0, min(index, len(spark_chars) - 1))  # Ensure valid index
            sparkline += spark_chars[index]

        return sparkline

    def _create_footer(self) -> Panel:
        """Create dashboard footer."""
        footer_text = Text()
        footer_text.append("Press Ctrl+C to exit", style="dim white")
        footer_text.append(" | ", style="dim white")
        footer_text.append("Updates every 180 seconds", style="dim white")

        return Panel(Align.center(footer_text), box=box.ROUNDED, style="dim white")

    def show_scanning(self) -> None:
        """Show scanning status."""
        self.console.print(
            Panel(
                Align.center(Text("Scanning code...", style="bold green")),
                box=box.ROUNDED,
                style="green",
            )
        )
